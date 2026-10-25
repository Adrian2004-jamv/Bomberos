"""Generador del informe PDF institucional de emergencias finalizadas.

Usa ReportLab directamente (sin HTML intermedio) para garantizar control
preciso del diseño, paginación y caracteres especiales en español.

Paleta institucional:
  Rojo corporativo  #B5121B  — encabezados y líneas divisorias
  Azul marino       #071B3D  — texto de títulos de sección
  Gris claro        #F3F4F6  — fondo de filas alternadas y cabeceras de tabla
  Blanco            #FFFFFF
"""

import base64
import io
from datetime import datetime

from django.utils.timezone import localtime, now
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.graphics.shapes import Drawing, PolyLine, Rect, String
from reportlab.platypus import (
    BaseDocTemplate, Frame, HRFlowable, Image, KeepTogether, NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

from emergencias.graficos_sci import (CAJA_ALTO, CAJA_ANCHO, LIENZO_ALTO, LIENZO_ANCHO,
                                      PREFIJO_PNG, cargar_organigrama, lineas_de_caja,
                                      puntos_de_conexion)

# ── Paleta ──────────────────────────────────────────────────────────────────
ROJO   = colors.HexColor("#B5121B")
MARINO = colors.HexColor("#071B3D")
GRIS   = colors.HexColor("#F3F4F6")
GRIS_M = colors.HexColor("#D1D5DB")
BLANCO = colors.white
NEGRO  = colors.HexColor("#111827")

# ── Márgenes ────────────────────────────────────────────────────────────────
MARGEN_IZQ   = 2.0 * cm
MARGEN_DER   = 1.8 * cm
MARGEN_SUP   = 2.0 * cm
MARGEN_INF   = 2.0 * cm
ANCHO_PAGINA = A4[0] - MARGEN_IZQ - MARGEN_DER   # ~17 cm


# ── Estilos de párrafo ───────────────────────────────────────────────────────
def _estilos():
    base = getSampleStyleSheet()

    def _p(name, parent="Normal", **kw):
        s = ParagraphStyle(name, parent=base[parent], **kw)
        return s

    return {
        # Encabezado de página (institución)
        "inst":       _p("inst",   fontName="Helvetica-Bold",   fontSize=11,
                         textColor=MARINO, alignment=TA_CENTER, spaceAfter=1),
        "subtitulo":  _p("subt",   fontName="Helvetica",        fontSize=9,
                         textColor=ROJO,   alignment=TA_CENTER, spaceAfter=2),
        # Título del documento
        "titulo_doc": _p("tdoc",   fontName="Helvetica-Bold",   fontSize=14,
                         textColor=MARINO, alignment=TA_CENTER, spaceAfter=4),
        "codigo_doc": _p("cdoc",   fontName="Helvetica-Bold",   fontSize=10,
                         textColor=ROJO,   alignment=TA_CENTER, spaceAfter=2),
        # Secciones
        "seccion":    _p("secc",   fontName="Helvetica-Bold",   fontSize=9,
                         textColor=BLANCO, alignment=TA_LEFT,
                         spaceBefore=8, spaceAfter=2,
                         backColor=MARINO,
                         leftIndent=4, rightIndent=4,
                         borderPadding=(3, 4, 3, 4)),
        # Cuerpo
        "normal":     _p("norm",   fontName="Helvetica",        fontSize=8.5,
                         textColor=NEGRO,  leading=12,
                         spaceBefore=1, spaceAfter=1),
        "negrita":    _p("neg",    fontName="Helvetica-Bold",   fontSize=8.5,
                         textColor=NEGRO,  leading=12),
        "etiqueta":   _p("etiq",   fontName="Helvetica-Bold",   fontSize=7.5,
                         textColor=MARINO, leading=10),
        "valor":      _p("val",    fontName="Helvetica",        fontSize=8.5,
                         textColor=NEGRO,  leading=11),
        "pie":        _p("pie",    fontName="Helvetica",        fontSize=7,
                         textColor=colors.HexColor("#6B7280"),
                         alignment=TA_CENTER),
        "resumen":    _p("res",    fontName="Helvetica",        fontSize=9,
                         textColor=NEGRO,  leading=13,
                         spaceBefore=3, spaceAfter=3,
                         leftIndent=6, rightIndent=6),
        "advertencia":_p("adv",    fontName="Helvetica-Oblique",fontSize=8,
                         textColor=colors.HexColor("#92400E"),
                         backColor=colors.HexColor("#FFFBEB"),
                         borderPadding=(3,4,3,4),
                         spaceBefore=4, spaceAfter=4),
    }


# ── Cabecera y pie de cada página ────────────────────────────────────────────
class _Plantilla(BaseDocTemplate):
    """Extiende BaseDocTemplate para inyectar cabecera/pie en cada página."""

    def __init__(self, buffer, datos, **kw):
        self._datos = datos
        super().__init__(buffer, **kw)
        self._construir_plantillas()

    def _construir_plantillas(self):
        marco = Frame(
            MARGEN_IZQ, MARGEN_INF,
            ANCHO_PAGINA, A4[1] - MARGEN_SUP - MARGEN_INF,
            leftPadding=0, rightPadding=0,
            topPadding=0, bottomPadding=0,
        )
        self.addPageTemplates([
            PageTemplate(id="todas", frames=[marco],
                         onPage=self._dibujar_pagina),
        ])

    def _dibujar_pagina(self, canvas, doc):
        canvas.saveState()
        ancho, alto = A4

        # ── Línea roja superior ──────────────────────────────────────
        canvas.setStrokeColor(ROJO)
        canvas.setLineWidth(3)
        canvas.line(MARGEN_IZQ, alto - 14 * mm,
                    ancho - MARGEN_DER, alto - 14 * mm)

        # ── Institución ──────────────────────────────────────────────
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(MARINO)
        canvas.drawCentredString(
            ancho / 2, alto - 11 * mm,
            self._datos.get("institucion", "Cuerpo de Bomberos de Cotopaxi").upper()
        )

        # ── Línea roja inferior ──────────────────────────────────────
        canvas.setStrokeColor(ROJO)
        canvas.setLineWidth(1)
        canvas.line(MARGEN_IZQ, MARGEN_INF - 4 * mm,
                    ancho - MARGEN_DER, MARGEN_INF - 4 * mm)

        # ── Pie de página ────────────────────────────────────────────
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawString(
            MARGEN_IZQ, MARGEN_INF - 8 * mm,
            f"Informe generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        canvas.drawRightString(
            ancho - MARGEN_DER, MARGEN_INF - 8 * mm,
            f"Página {doc.page}"
        )

        canvas.restoreState()


# ── Helpers de construcción ──────────────────────────────────────────────────
def _croquis_pdf(dibujo, ancho_max=ANCHO_PAGINA * 0.8):
    """El croquis dibujado en el SCI-201 como imagen del tamaño de la hoja, o ``None``."""
    if not dibujo or not dibujo.startswith(PREFIJO_PNG):
        return None
    try:
        imagen = Image(io.BytesIO(base64.b64decode(dibujo[len(PREFIJO_PNG):])))
    except Exception:  # una imagen ilegible no debe impedir el informe
        return None
    proporcion = imagen.imageHeight / imagen.imageWidth
    imagen.drawWidth = ancho_max
    imagen.drawHeight = ancho_max * proporcion
    return imagen


def _organigrama_pdf(grafico_json, ancho=ANCHO_PAGINA):
    """El organigrama del SCI-201 como dibujo vectorial, o ``None`` si no hay.

    Usa las mismas cajas y el mismo trazado que la hoja impresa
    (``emergencias.graficos_sci``); solo cambia el sistema de coordenadas, porque en
    ReportLab el eje vertical crece hacia arriba.
    """
    grafico = cargar_organigrama(grafico_json)
    if not grafico:
        return None
    escala = ancho / LIENZO_ANCHO
    dibujo = Drawing(ancho, LIENZO_ALTO * escala)

    def punto(x, y):
        return x * escala, (LIENZO_ALTO - y) * escala

    por_id = {caja["id"]: caja for caja in grafico["nodos"]}
    for enlace in grafico["enlaces"]:
        vertices = [c for xy in puntos_de_conexion(por_id[enlace["de"]], por_id[enlace["a"]])
                    for c in punto(*xy)]
        dibujo.add(PolyLine(vertices, strokeColor=colors.HexColor("#475569"), strokeWidth=1.2))
    for caja in grafico["nodos"]:
        x, y = punto(caja["x"], caja["y"] + CAJA_ALTO)
        dibujo.add(Rect(x, y, CAJA_ANCHO * escala, CAJA_ALTO * escala, rx=3, ry=3,
                        fillColor=BLANCO, strokeColor=MARINO, strokeWidth=1.2))
        lineas = lineas_de_caja(caja["t"])
        arriba = (LIENZO_ALTO - caja["y"] - CAJA_ALTO / 2) * escala + (len(lineas) - 1) * 4.5
        for numero, linea in enumerate(lineas):
            dibujo.add(String((caja["x"] + CAJA_ANCHO / 2) * escala, arriba - numero * 9 - 3,
                              linea, textAnchor="middle", fontSize=7.5, fillColor=NEGRO))
    return dibujo


def _hr(color=GRIS_M, width=0.5):
    return HRFlowable(width="100%", thickness=width, color=color,
                      spaceAfter=4, spaceBefore=2)


def _seccion(texto, est):
    """Título de sección con fondo marino."""
    return Paragraph(f"&nbsp;&nbsp;{texto.upper()}", est["seccion"])


def _par(texto, est, estilo="normal"):
    """Párrafo seguro: convierte None y escapa caracteres."""
    if texto is None:
        texto = "No registrado"
    texto = str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(texto, est[estilo])


def _fila_dato(etiqueta, valor, est, col1=5*cm, col2=None):
    """Fila de dos columnas: etiqueta + valor."""
    col2 = col2 or (ANCHO_PAGINA - col1)
    tabla = Table(
        [[_par(etiqueta, est, "etiqueta"), _par(valor or "No registrado", est, "valor")]],
        colWidths=[col1, col2],
    )
    tabla.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 4),
        ("TOPPADDING",  (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING",(0,0), (-1, -1), 1),
    ]))
    return tabla


def _tabla_datos(filas_dict, est, col1=5*cm):
    """Bloque de múltiples etiqueta→valor."""
    bloques = []
    for etiqueta, valor in filas_dict.items():
        bloques.append(_fila_dato(etiqueta, valor, est, col1))
    return bloques


def _tabla_generica(cabeceras, filas, est, col_widths=None):
    """Tabla con cabecera marina y filas alternadas."""
    if not filas:
        return [_par("Sin registros.", est, "normal")]

    data = [cabeceras] + filas
    n_col = len(cabeceras)
    col_widths = col_widths or [ANCHO_PAGINA / n_col] * n_col

    # Convertir a Paragraph para control tipográfico
    datos_p = []
    for i, fila in enumerate(data):
        estilo_p = "etiqueta" if i == 0 else "normal"
        datos_p.append([
            _par(str(celda) if celda is not None else "—", est, estilo_p)
            for celda in fila
        ])

    tabla = Table(datos_p, colWidths=col_widths, repeatRows=1)
    estilos_t = [
        ("BACKGROUND",   (0, 0), (-1, 0),  MARINO),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  BLANCO),
        ("GRID",         (0, 0), (-1, -1), 0.35, GRIS_M),
        ("ROWBACKGROUNDS",(0, 1),(-1, -1), [BLANCO, GRIS]),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING",   (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
    ]
    tabla.setStyle(TableStyle(estilos_t))
    return [tabla]


# ── Constructor del documento ────────────────────────────────────────────────
def generar_pdf_emergencia(datos: dict) -> bytes:
    """
    Recibe el dict de ``datos_informe_emergencia()`` y devuelve los bytes del PDF.

    Estructura del documento:
      Portada / Resumen ejecutivo
      1. Identificación
      2. Ubicación
      3. Mando y personal
      4. Cronología
      5. Descripción operativa
      6. Recursos desplegados
      7. Afectaciones (pacientes / SCI-207)
      8. Actividades (SCI-214)
      9. Pie de firma
    """
    buffer = io.BytesIO()
    est = _estilos()
    e = datos  # alias corto

    doc = _Plantilla(
        buffer, datos,
        pagesize=A4,
        leftMargin=MARGEN_IZQ,
        rightMargin=MARGEN_DER,
        topMargin=MARGEN_SUP + 6 * mm,   # espacio extra para cabecera
        bottomMargin=MARGEN_INF + 6 * mm,
        title=f"Informe Emergencia {e['codigo']}",
        author=e.get("institucion", "Cuerpo de Bomberos de Cotopaxi"),
        subject="Informe Resumen de Emergencia",
    )

    historia = []

    # ── PORTADA ──────────────────────────────────────────────────────
    historia.append(Spacer(1, 8 * mm))
    historia.append(_par(e.get("institucion", "").upper(), est, "inst"))
    historia.append(_par("SISTEMA DE GESTIÓN OPERATIVA · COTOPAXI", est, "subtitulo"))
    historia.append(_hr(ROJO, 1.5))
    historia.append(Spacer(1, 4 * mm))
    historia.append(_par("INFORME RESUMEN DE EMERGENCIA", est, "titulo_doc"))
    historia.append(_par(f"Incidente {e['codigo']} · {e['estado'].upper()}", est, "codigo_doc"))
    historia.append(Spacer(1, 3 * mm))
    historia.append(_hr())

    # ── RESUMEN EJECUTIVO ────────────────────────────────────────────
    historia.append(Spacer(1, 3 * mm))
    historia.append(_seccion("Resumen ejecutivo", est))
    historia.append(Spacer(1, 2 * mm))

    partes_resumen = [
        f"El {e['hora_notificacion']} se reportó un incidente de tipo "
        f"<b>{e['tipo']}</b> (prioridad {e['prioridad']}) en <b>{e['direccion']}</b>.",
    ]
    if e.get("ci_nombre") != "No registrado":
        partes_resumen.append(
            f"El Comandante del Incidente fue <b>{e['ci_nombre']}</b>."
        )
    if e["total_unidades"]:
        partes_resumen.append(
            f"Se desplegaron <b>{e['total_unidades']}</b> unidad(es) al lugar del incidente."
        )
    if e.get("tiempo_respuesta") and e["tiempo_respuesta"] != "No calculable":
        partes_resumen.append(f"Tiempo de respuesta: <b>{e['tiempo_respuesta']}</b>.")
    if e.get("duracion_total") and e["duracion_total"] != "No calculable":
        partes_resumen.append(f"Duración total de las operaciones: <b>{e['duracion_total']}</b>.")
    if e["total_pacientes"]:
        partes_resumen.append(
            f"Se atendieron <b>{e['total_pacientes']}</b> paciente(s) registrados en el SCI-207."
        )
    partes_resumen.append(
        f"El incidente fue cerrado el <b>{e['hora_cierre']}</b>."
    )

    resumen_texto = "  ".join(partes_resumen)
    resumen_texto = resumen_texto.replace("&", "&amp;").replace("<b>", "<b>").replace("</b>", "</b>")
    historia.append(Paragraph(resumen_texto, est["resumen"]))
    historia.append(_hr())

    # ─── 1. IDENTIFICACIÓN ───────────────────────────────────────────
    historia.append(_seccion("1. Identificación de la emergencia", est))
    historia.append(Spacer(1, 2 * mm))
    for t in _tabla_datos({
        "Código del incidente:":  e["codigo"],
        "Tipo de emergencia:":    e["tipo"],
        "Prioridad:":             e["prioridad"],
        "Estado final:":          e["estado"],
        "Fecha de reporte:":      e["hora_notificacion"],
        "Fecha de cierre:":       e["hora_cierre"],
        "Institución responsable:": e["institucion"],
        "Estación responsable:":  e["estacion"],
        "Registrado por:":        e["registrado_por"],
    }, est):
        historia.append(t)
    historia.append(_hr())

    # ─── 2. UBICACIÓN ────────────────────────────────────────────────
    historia.append(_seccion("2. Ubicación del incidente", est))
    historia.append(Spacer(1, 2 * mm))
    for t in _tabla_datos({
        "Provincia:":             e["provincia"],
        "Cantón:":                e["canton"],
        "Dirección / referencia:":e["direccion"],
        "Coordenadas GPS:":       e["coordenadas"],
    }, est):
        historia.append(t)
    historia.append(_hr())

    # ─── 3. MANDO Y PERSONAL ─────────────────────────────────────────
    historia.append(_seccion("3. Mando y personal responsable", est))
    historia.append(Spacer(1, 2 * mm))
    for t in _tabla_datos({
        "Comandante del Incidente:": e["ci_nombre"],
    }, est):
        historia.append(t)

    if e["representantes"]:
        historia.append(Spacer(1, 2 * mm))
        historia.append(_par("Representantes institucionales:", est, "etiqueta"))
        for rep in e["representantes"]:
            historia.append(_par(f"• {rep}", est, "normal"))

    if e["personal_sci"]:
        historia.append(Spacer(1, 2 * mm))
        historia.append(_par("Personal registrado en SCI-214:", est, "etiqueta"))
        for p in e["personal_sci"]:
            historia.append(_par(f"• {p}", est, "normal"))
    historia.append(_hr())

    # ─── 4. CRONOLOGÍA ───────────────────────────────────────────────
    historia.append(_seccion("4. Cronología y tiempos de respuesta", est))
    historia.append(Spacer(1, 2 * mm))

    cronologia = [
        ["Evento", "Fecha y hora"],
        ["Notificación de la emergencia",    e["hora_notificacion"]],
        ["Primera salida de unidades",       e["hora_primera_salida"]],
        ["Primera llegada al lugar",         e["hora_primera_llegada"]],
        ["Cierre de la emergencia",          e["hora_cierre"]],
        ["Desmovilización estimada (SCI-221)", e["hora_desmoviliz"]],
    ]
    for row in _tabla_generica(
        cronologia[0], cronologia[1:], est,
        col_widths=[ANCHO_PAGINA * 0.65, ANCHO_PAGINA * 0.35]
    ):
        historia.append(row)

    historia.append(Spacer(1, 2 * mm))
    for t in _tabla_datos({
        "Tiempo de respuesta:":              e["tiempo_respuesta"],
        "Duración de las operaciones:":      e["duracion_operaciones"],
        "Duración total (notificación–cierre):": e["duracion_total"],
    }, est):
        historia.append(t)
    historia.append(_hr())

    # ─── 5. DESCRIPCIÓN OPERATIVA ────────────────────────────────────
    historia.append(_seccion("5. Descripción y acciones operativas", est))
    historia.append(Spacer(1, 2 * mm))

    # El punto 4 del SCI-201 va por sub-puntos, cada uno con su título.
    evaluacion = e.get("evaluacion_items") or [("Evaluación inicial", "No registrado")]
    for etiq, texto in evaluacion:
        historia.append(_par(
            f"Evaluación inicial (SCI-201) — {etiq}:" if len(evaluacion) > 1
            else "Evaluación inicial (SCI-201):",
            est, "etiqueta",
        ))
        historia.append(_par(texto, est, "normal"))
        historia.append(Spacer(1, 2 * mm))

    for etiq, campo in [
        ("Objetivos operativos (SCI-201):", "objetivos"),
        ("Estrategias (SCI-201):", "estrategias"),
        ("Tácticas (SCI-201):", "tacticas"),
        ("Mensaje de seguridad:", "mensaje_seguridad"),
    ]:
        historia.append(_par(etiq, est, "etiqueta"))
        historia.append(_par(e.get(campo, "No registrado"), est, "normal"))
        historia.append(Spacer(1, 2 * mm))

    # El croquis y el organigrama del SCI-201, si se dibujaron.
    croquis = _croquis_pdf(e.get("croquis_dibujo"))
    if croquis:
        historia.append(KeepTogether([_par("Croquis del incidente (SCI-201):", est, "etiqueta"), croquis]))
        historia.append(Spacer(1, 2 * mm))
    organigrama = _organigrama_pdf(e.get("organigrama_grafico"))
    if organigrama:
        historia.append(KeepTogether([_par("Organigrama (SCI-201):", est, "etiqueta"), organigrama]))
        historia.append(Spacer(1, 2 * mm))

    # Tabla de acciones cronológicas SCI-201
    if e["acciones_201"]:
        historia.append(_par("Resumen cronológico de acciones (SCI-201):", est, "etiqueta"))
        filas_acc = [
            [a.get("fecha_hora", "—"), a.get("accion", "—")]
            for a in e["acciones_201"]
        ]
        for row in _tabla_generica(
            ["Fecha y hora", "Acción"], filas_acc, est,
            col_widths=[ANCHO_PAGINA * 0.28, ANCHO_PAGINA * 0.72]
        ):
            historia.append(row)
    historia.append(_hr())

    # ─── 6. RECURSOS DESPLEGADOS ─────────────────────────────────────
    historia.append(_seccion("6. Recursos desplegados", est))
    historia.append(Spacer(1, 2 * mm))

    historia.append(_par(
        f"Total de despliegues registrados: <b>{e['total_unidades']}</b>",
        est, "normal"
    ))
    historia.append(Spacer(1, 2 * mm))

    if e["despliegues"]:
        filas_desp = []
        vistos = set()
        for d in e["despliegues"]:
            uid = d.pk
            if uid in vistos:
                continue
            vistos.add(uid)
            filas_desp.append([
                d.unidad.codigo_interno,
                d.unidad.tipo.nombre if d.unidad.tipo else "—",
                d.estacion_procedencia.nombre if d.estacion_procedencia else "—",
                d.get_estado_display(),
                d.fecha_llegada.strftime("%d/%m %H:%M") if d.fecha_llegada else "—",
                d.fecha_retorno.strftime("%d/%m %H:%M") if d.fecha_retorno else "—",
            ])
        anchos = [
            ANCHO_PAGINA*0.13, ANCHO_PAGINA*0.20, ANCHO_PAGINA*0.22,
            ANCHO_PAGINA*0.15, ANCHO_PAGINA*0.15, ANCHO_PAGINA*0.15,
        ]
        for row in _tabla_generica(
            ["Código", "Tipo", "Estación", "Estado", "Llegada", "Retorno"],
            filas_desp, est, col_widths=anchos
        ):
            historia.append(row)
    else:
        historia.append(_par("No se registraron despliegues de unidades.", est, "normal"))

    # SCI-211 si existe
    if e["registros_211"]:
        historia.append(Spacer(1, 3 * mm))
        historia.append(_par("Registro y Control de Recursos (SCI-211):", est, "etiqueta"))
        filas_211 = []
        vistos_211 = set()
        for r in e["registros_211"]:
            rid = (r.matricula_identificacion, r.institucion_procedencia)
            if rid in vistos_211:
                continue
            vistos_211.add(rid)
            filas_211.append([
                r.matricula_identificacion or "—",
                r.clase_recurso or "—",
                r.institucion_procedencia or "—",
                r.get_estado_recurso_display(),
                r.fecha_hora_arribo.strftime("%d/%m %H:%M") if r.fecha_hora_arribo else "—",
            ])
        anchos211 = [
            ANCHO_PAGINA*0.18, ANCHO_PAGINA*0.22, ANCHO_PAGINA*0.28,
            ANCHO_PAGINA*0.17, ANCHO_PAGINA*0.15,
        ]
        for row in _tabla_generica(
            ["Matrícula", "Clase", "Institución", "Estado", "Arribo"],
            filas_211, est, col_widths=anchos211
        ):
            historia.append(row)
    historia.append(_hr())

    # ─── 7. AFECTACIONES ─────────────────────────────────────────────
    historia.append(_seccion("7. Afectaciones y resultados (SCI-207)", est))
    historia.append(Spacer(1, 2 * mm))

    if e["pacientes"]:
        for t in _tabla_datos({
            "Total de pacientes atendidos:": str(e["total_pacientes"]),
            "Pacientes trasladados:":        str(e["evacuados"]),
        }, est):
            historia.append(t)
        historia.append(Spacer(1, 2 * mm))
        filas_pac = [
            [
                p.get("nombre", "—"),
                p.get("sexo",   "—"),
                str(p.get("edad", "—")),
                p.get("clasificacion", "—"),
                p.get("lugar_traslado", "—"),
            ]
            for p in e["pacientes"]
        ]
        anchos_pac = [
            ANCHO_PAGINA*0.28, ANCHO_PAGINA*0.08, ANCHO_PAGINA*0.08,
            ANCHO_PAGINA*0.22, ANCHO_PAGINA*0.34,
        ]
        for row in _tabla_generica(
            ["Nombre", "Sexo", "Edad", "Clasificación", "Lugar de traslado"],
            filas_pac, est, col_widths=anchos_pac
        ):
            historia.append(row)
    else:
        historia.append(_par(
            "No se registraron pacientes o víctimas en el SCI-207 para este incidente.",
            est, "normal"
        ))
    historia.append(_hr())

    # ─── 8. ACTIVIDADES (SCI-214) ────────────────────────────────────
    if e["actividades"]:
        historia.append(_seccion("8. Registro de actividades (SCI-214)", est))
        historia.append(Spacer(1, 2 * mm))
        filas_act = [
            [a.get("hora", "—"), a.get("evento", "—")]
            for a in e["actividades"]
        ]
        for row in _tabla_generica(
            ["Hora", "Evento"], filas_act, est,
            col_widths=[ANCHO_PAGINA * 0.15, ANCHO_PAGINA * 0.85]
        ):
            historia.append(row)
        historia.append(_hr())

    # ─── 9. PIE DE FIRMA ─────────────────────────────────────────────
    historia.append(Spacer(1, 8 * mm))
    historia.append(_seccion("Responsable del informe", est))
    historia.append(Spacer(1, 4 * mm))

    firma_tabla = Table(
        [[
            _par("___________________________\nComandante del Incidente\n"
                 + e["ci_nombre"], est, "normal"),
            _par("___________________________\nGenerado por\n"
                 + e["registrado_por"], est, "normal"),
            _par("___________________________\nFecha de emisión\n"
                 + datetime.now().strftime("%d/%m/%Y %H:%M"), est, "normal"),
        ]],
        colWidths=[ANCHO_PAGINA / 3] * 3,
    )
    firma_tabla.setStyle(TableStyle([
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
    ]))
    historia.append(firma_tabla)
    historia.append(Spacer(1, 6 * mm))
    historia.append(_par(
        "Documento generado automáticamente por el Sistema de Gestión Operativa "
        "de los Cuerpos de Bomberos de la Provincia de Cotopaxi. "
        "Los datos corresponden a la información registrada en el sistema al momento de la generación.",
        est, "pie"
    ))

    doc.build(historia)
    return buffer.getvalue()
