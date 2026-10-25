"""El croquis y el organigrama de los formularios SCI.

El SCI-201 pide un «mapa situacional o croquis» (punto 14) y un «organigrama actual»
(punto 17); el SCI-202 pide «graficar» el organigrama del periodo (punto 15). Eran
cuadros de texto. Ahora son dos componentes reutilizables —un lienzo de dibujo y un
editor de cajas— que se declaran en el esquema con un tipo de campo, de modo que
cualquier formulario futuro los obtiene sin copiar nada.

Estas pruebas cubren lo que el servidor debe garantizar aunque el navegador falle o
alguien mande una petición a mano: qué se acepta, qué se guarda, qué se imprime.
"""

import base64
import re
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.urls import reverse

from dashboard.pdf import _croquis_pdf, _organigrama_pdf
from dashboard.services import datos_informe_emergencia

from . import graficos_sci as g
from .esquemas_sci import (CROQUIS, ESQUEMAS_SCI, MODO_BLANCO, MODO_LECTURA, ORGANIGRAMA,
                           conservar_campos_retirados, extraer_datos, secciones_completadas,
                           secciones_con_valores)
from .models import Emergencia, FormularioSCI
from .test_validacion_sci import BaseValidacion
from .views import hoja_de_solo_lectura

# Un PNG mínimo y válido de 1×1 píxel.
PNG_1X1 = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


FIRMA_PNG = b"\x89PNG\r\n\x1a\n"


def organigrama(*cajas, enlaces=()):
    import json
    return json.dumps({
        "nodos": [{"id": i, "x": x, "y": y, "t": t} for i, x, y, t in cajas],
        "enlaces": [{"de": a, "a": b} for a, b in enlaces],
    })


ORGANIGRAMA_BASICO = organigrama(
    ("ci", 305, 20, "Comandante del Incidente"),
    ("ops", 20, 300, "Operaciones"),
    enlaces=[("ci", "ops")],
)


# ──────────────────────────────────────────────────────────────────────
# 1. Lo que llega del navegador no se da por bueno
# ──────────────────────────────────────────────────────────────────────

class LimpiezaDelCroquisTests(SimpleTestCase):
    def test_un_png_valido_se_acepta(self):
        self.assertEqual(g.limpiar_croquis(PNG_1X1), PNG_1X1)

    def test_lo_que_no_es_un_png_se_descarta(self):
        casos = {
            "vacío": "",
            "nulo": None,
            "otro tipo de imagen": PNG_1X1.replace("image/png", "image/jpeg"),
            "un script": "javascript:alert(1)",
            "una URL": "https://ejemplo.com/croquis.png",
            "base64 roto": "data:image/png;base64,@@@@no es base64@@@@",
            "base64 válido pero no es un PNG": "data:image/png;base64,"
            + base64.b64encode(b"<script>alert(1)</script>").decode(),
        }
        for nombre, valor in casos.items():
            with self.subTest(nombre):
                self.assertEqual(g.limpiar_croquis(valor), "")

    def test_un_dibujo_desmesurado_se_descarta(self):
        """Con la firma de un PNG de verdad: lo que lo frena es el tamaño, no el contenido."""
        crudo = FIRMA_PNG + b"0" * g.MAX_CROQUIS
        enorme = g.PREFIJO_PNG + base64.b64encode(crudo).decode()
        self.assertGreater(len(enorme), g.MAX_CROQUIS)
        self.assertEqual(g.limpiar_croquis(enorme), "")

    def test_se_acepta_un_dibujo_grande_pero_dentro_del_tope(self):
        crudo = FIRMA_PNG + b"0" * 500_000
        grande = g.PREFIJO_PNG + base64.b64encode(crudo).decode()
        self.assertEqual(g.limpiar_croquis(grande), grande)


class LimpiezaDelOrganigramaTests(SimpleTestCase):
    def test_un_organigrama_normal_se_conserva(self):
        limpio = g.cargar_organigrama(ORGANIGRAMA_BASICO)
        self.assertEqual([c["id"] for c in limpio["nodos"]], ["ci", "ops"])
        self.assertEqual(limpio["enlaces"], [{"de": "ci", "a": "ops"}])

    def test_lo_ilegible_o_vacio_no_deja_nada(self):
        for valor in ("", None, "no es json", "[]", '{"nodos": []}', '{"nodos": "x"}', "{" * 50):
            with self.subTest(valor=valor):
                self.assertEqual(g.limpiar_organigrama(valor), "")

    def test_las_cajas_se_acotan_al_lienzo(self):
        limpio = g.cargar_organigrama(organigrama(("a", -500, 99999, "Fuera")))
        caja = limpio["nodos"][0]
        self.assertEqual(caja["x"], 0)
        self.assertEqual(caja["y"], g.LIENZO_ALTO - g.CAJA_ALTO)

    def test_el_texto_de_una_caja_tiene_tope_y_se_compacta(self):
        limpio = g.cargar_organigrama(organigrama(("a", 0, 0, "  Jefe   de\n\n sección " + "x" * 200)))
        texto = limpio["nodos"][0]["t"]
        self.assertLessEqual(len(texto), g.MAX_TEXTO_CAJA)
        self.assertNotIn("\n", texto)
        self.assertTrue(texto.startswith("Jefe de sección"))

    def test_se_descartan_conexiones_imposibles(self):
        """A una caja que no existe, de una caja consigo misma o repetidas."""
        crudo = organigrama(
            ("a", 0, 0, "A"), ("b", 200, 0, "B"),
            enlaces=[("a", "b"), ("a", "b"), ("a", "a"), ("a", "fantasma"), ("fantasma", "b")],
        )
        self.assertEqual(g.cargar_organigrama(crudo)["enlaces"], [{"de": "a", "a": "b"}])

    def test_un_id_repetido_o_con_caracteres_raros_no_pasa(self):
        crudo = organigrama(("a", 0, 0, "A"), ("a", 50, 50, "Otra"), ("<b>", 10, 10, "C"))
        ids = [c["id"] for c in g.cargar_organigrama(crudo)["nodos"]]
        self.assertEqual(ids, ["a", "b"])  # el repetido sale; «<b>» queda como «b»

    def test_hay_un_maximo_de_cajas_y_de_conexiones(self):
        cajas = [(f"n{i}", 0, 0, "x") for i in range(g.MAX_CAJAS + 25)]
        enlaces = [(f"n{i}", f"n{i + 1}") for i in range(g.MAX_CAJAS + 24)]
        limpio = g.cargar_organigrama(organigrama(*cajas, enlaces=enlaces))
        self.assertEqual(len(limpio["nodos"]), g.MAX_CAJAS)
        self.assertLessEqual(len(limpio["enlaces"]), g.MAX_CONEXIONES)

    def test_un_json_gigante_se_rechaza_sin_procesarlo(self):
        self.assertEqual(g.limpiar_organigrama(" " * (g.MAX_JSON + 1)), "")


class DibujoDelOrganigramaTests(SimpleTestCase):
    def test_sin_cajas_no_hay_svg(self):
        self.assertEqual(g.organigrama_svg(""), "")

    def test_cada_caja_y_cada_conexion_se_dibujan(self):
        svg = g.organigrama_svg(ORGANIGRAMA_BASICO)
        self.assertEqual(svg.count("<rect"), 2)
        self.assertEqual(svg.count("<path"), 1)
        self.assertIn("Comandante del", svg)

    def test_el_texto_del_usuario_se_escapa(self):
        """El SVG se marca seguro para incrustarlo: solo vale si nada del usuario entra crudo."""
        svg = g.organigrama_svg(organigrama(("a", 0, 0, '<script>alert("x")</script>')))
        self.assertNotIn("<script", svg)
        self.assertIn("&lt;script", svg)

    def test_una_cadena_sin_espacios_se_parte_y_no_se_sale_de_la_caja(self):
        lineas = g.lineas_de_caja("X" * 70)
        self.assertLessEqual(len(lineas), g.LINEAS_POR_CAJA)
        self.assertTrue(all(len(linea) <= g.CARACTERES_POR_LINEA for linea in lineas))
        self.assertTrue(lineas[-1].endswith("…"))

    def test_las_conexiones_van_en_angulos_rectos(self):
        arriba = {"x": 300, "y": 20}
        abajo = {"x": 20, "y": 300}
        lado = {"x": 500, "y": 30}
        # Hacia abajo: sale del borde inferior y llega al superior.
        puntos = g.puntos_de_conexion(arriba, abajo)
        self.assertEqual(puntos[0], (375, 20 + g.CAJA_ALTO))
        self.assertEqual(puntos[-1], (95, 300))
        # A la misma altura: de lado a lado.
        puntos = g.puntos_de_conexion(arriba, lado)
        self.assertEqual(puntos[0][0], 300 + g.CAJA_ANCHO)
        self.assertEqual(puntos[-1][0], 500)
        # Hacia arriba.
        puntos = g.puntos_de_conexion(abajo, arriba)
        self.assertEqual(puntos[0][1], 300)
        self.assertEqual(puntos[-1][1], 20 + g.CAJA_ALTO)


# ──────────────────────────────────────────────────────────────────────
# 2. Los campos gráficos dentro de los formularios
# ──────────────────────────────────────────────────────────────────────

class EsquemaTests(SimpleTestCase):
    def test_donde_se_usa_cada_componente(self):
        """La auditoría contra los formularios oficiales (.docx/.xlsx de «Total de
        Formularios SCI»): el croquis solo lo pide el SCI-201; el organigrama, el 201
        y el 202 («Grafique el organigrama para el PO»). El 203 es el organigrama en
        forma de lista, y ningún otro formulario pide un dibujo."""
        usados = {
            codigo: sorted((s["nombre"], s["tipo"]) for s in esquema["secciones"]
                           if s["tipo"] in (CROQUIS, ORGANIGRAMA))
            for codigo, esquema in ESQUEMAS_SCI.items()
        }
        usados = {codigo: lo for codigo, lo in usados.items() if lo}
        self.assertEqual(usados, {
            "201": [("croquis", CROQUIS), ("organigrama", ORGANIGRAMA)],
            "202": [("organigrama", ORGANIGRAMA)],
        })

    def test_ningun_campo_grafico_quedo_como_cuadro_de_texto(self):
        for codigo in ("201", "202"):
            for seccion in ESQUEMAS_SCI[codigo]["secciones"]:
                if seccion["nombre"] in ("croquis", "organigrama"):
                    self.assertIn(seccion["tipo"], (CROQUIS, ORGANIGRAMA), (codigo, seccion["nombre"]))


class GuardarGraficosTests(BaseValidacion):
    def editar(self, codigo, emergencia):
        return reverse("emergencias:sci_editar", args=[codigo, emergencia.pk])

    def enviar(self, codigo, emergencia, datos):
        self.client.force_login(self.usuario)
        return self.client.post(self.editar(codigo, emergencia), datos)

    def datos(self, emergencia, codigo="201"):
        return FormularioSCI.objects.get(emergencia=emergencia, codigo_sci=codigo).datos

    def test_se_guardan_el_dibujo_y_el_organigrama(self):
        emergencia = self.crear_emergencia("GRA-001")
        self.enviar("201", emergencia, {
            "croquis__dibujo": PNG_1X1, "organigrama__grafico": ORGANIGRAMA_BASICO,
            "croquis": "Acceso por la calle Quito", "organigrama": "CI: Mayor Andrade",
        })
        datos = self.datos(emergencia)
        self.assertEqual(datos["croquis__dibujo"], PNG_1X1)
        self.assertEqual(len(g.cargar_organigrama(datos["organigrama__grafico"])["nodos"]), 2)
        # La nota de texto de siempre sigue en su clave: lo ya escrito no se pierde.
        self.assertEqual(datos["croquis"], "Acceso por la calle Quito")
        self.assertEqual(datos["organigrama"], "CI: Mayor Andrade")

    def test_una_peticion_a_mano_con_basura_no_guarda_basura(self):
        emergencia = self.crear_emergencia("GRA-002")
        self.enviar("201", emergencia, {
            "croquis__dibujo": "javascript:alert(1)",
            "organigrama__grafico": '{"nodos": [{"id": "a", "x": "NaN", "y": 1e99, "t": "<img onerror=x>"}]}',
        })
        datos = self.datos(emergencia)
        self.assertEqual(datos["croquis__dibujo"], "")
        caja = g.cargar_organigrama(datos["organigrama__grafico"])["nodos"][0]
        self.assertEqual((caja["x"], caja["y"]), (0, g.LIENZO_ALTO - g.CAJA_ALTO))

    def test_el_202_guarda_su_organigrama(self):
        emergencia = self.crear_emergencia("GRA-202")
        self.enviar("202", emergencia, {"organigrama__grafico": ORGANIGRAMA_BASICO})
        self.assertTrue(self.datos(emergencia, "202")["organigrama__grafico"])

    def test_vaciar_el_dibujo_lo_borra(self):
        emergencia = self.crear_emergencia("GRA-003")
        self.crear_formulario(emergencia, "201", {"croquis__dibujo": PNG_1X1})
        self.enviar("201", emergencia, {"croquis__dibujo": ""})
        self.assertEqual(self.datos(emergencia)["croquis__dibujo"], "")

    def test_una_pagina_vieja_que_no_manda_los_gráficos_no_los_borra(self):
        """Una pestaña abierta antes de estos campos no manda las claves: eso no es «borrar»."""
        emergencia = self.crear_emergencia("GRA-004")
        self.crear_formulario(emergencia, "201", {
            "croquis__dibujo": PNG_1X1, "organigrama__grafico": g.limpiar_organigrama(ORGANIGRAMA_BASICO),
        })
        self.enviar("201", emergencia, {"lugar_incidente": "Otro lugar"})
        datos = self.datos(emergencia)
        self.assertEqual(datos["lugar_incidente"], "Otro lugar")
        self.assertEqual(datos["croquis__dibujo"], PNG_1X1)
        self.assertTrue(datos["organigrama__grafico"])

    def test_un_gráfico_cuenta_como_seccion_completada(self):
        esquema = ESQUEMAS_SCI["201"]
        sin, _ = secciones_completadas(esquema, {})
        con, _ = secciones_completadas(esquema, {"croquis__dibujo": PNG_1X1})
        self.assertEqual(con, sin + 1)


class EditorTests(BaseValidacion):
    def abrir(self, codigo, emergencia):
        self.client.force_login(self.usuario)
        return self.client.get(reverse("emergencias:sci_editar", args=[codigo, emergencia.pk]))

    def test_el_201_ofrece_el_lienzo_y_el_editor_de_organigrama(self):
        respuesta = self.abrir("201", self.crear_emergencia("EDI-001"))
        self.assertContains(respuesta, "data-sci-croquis")
        self.assertContains(respuesta, 'name="croquis__dibujo"')
        self.assertContains(respuesta, "data-sci-organigrama")
        self.assertContains(respuesta, 'name="organigrama__grafico"')
        self.assertContains(respuesta, "emergencias/js/sci_croquis.js")
        self.assertContains(respuesta, "emergencias/js/sci_organigrama.js")

    def test_el_202_solo_ofrece_el_organigrama(self):
        respuesta = self.abrir("202", self.crear_emergencia("EDI-002"))
        self.assertContains(respuesta, "data-sci-organigrama")
        self.assertNotContains(respuesta, "data-sci-croquis")

    def test_un_formulario_sin_campos_graficos_no_carga_nada_extra_en_su_html(self):
        respuesta = self.abrir("204", self.crear_emergencia("EDI-004"))
        self.assertNotContains(respuesta, "data-sci-croquis")
        self.assertNotContains(respuesta, "data-sci-organigrama")

    def test_el_editor_vuelve_a_cargar_lo_guardado(self):
        emergencia = self.crear_emergencia("EDI-003")
        self.crear_formulario(emergencia, "201", {
            "croquis__dibujo": PNG_1X1, "organigrama__grafico": g.limpiar_organigrama(ORGANIGRAMA_BASICO),
            "croquis": "Una nota vieja",
        })
        respuesta = self.abrir("201", emergencia)
        self.assertContains(respuesta, PNG_1X1)
        self.assertContains(respuesta, "Comandante del Incidente")
        # El texto que ya existía sigue visible y editable.
        self.assertContains(respuesta, "Una nota vieja")


class HojaImpresaTests(BaseValidacion):
    def visualizar(self, codigo, emergencia):
        self.client.force_login(self.usuario)
        return self.client.get(reverse("emergencias:sci_visualizar", args=[codigo, emergencia.pk]))

    def test_sin_dibujo_el_recuadro_queda_en_blanco(self):
        """Para dibujarlo a mano: ni un texto de relleno estorbando en ese espacio."""
        emergencia = self.crear_emergencia("IMP-001")
        self.crear_formulario(emergencia, "201", {})
        respuesta = self.visualizar("201", emergencia)
        self.assertContains(respuesta, "sci-grafico--blanco")
        self.assertNotContains(respuesta, "Espacio para el")
        self.assertNotContains(respuesta, "<img src=\"data:image/png")

    def test_con_dibujo_se_imprime_la_imagen(self):
        emergencia = self.crear_emergencia("IMP-002")
        self.crear_formulario(emergencia, "201", {"croquis__dibujo": PNG_1X1})
        self.assertContains(self.visualizar("201", emergencia), f'<img src="{PNG_1X1}"')

    def test_con_organigrama_se_imprime_el_svg_sin_ejecutar_nada(self):
        emergencia = self.crear_emergencia("IMP-003")
        self.crear_formulario(emergencia, "201", {"organigrama__grafico": g.limpiar_organigrama(ORGANIGRAMA_BASICO)})
        respuesta = self.visualizar("201", emergencia)
        self.assertContains(respuesta, 'class="sci-organigrama__svg"')
        self.assertContains(respuesta, "Comandante del")

    def test_la_nota_de_texto_de_antes_se_imprime_debajo(self):
        emergencia = self.crear_emergencia("IMP-004")
        self.crear_formulario(emergencia, "201", {"croquis": "Descripción de siempre"})
        respuesta = self.visualizar("201", emergencia)
        self.assertContains(respuesta, "Descripción de siempre")
        self.assertContains(respuesta, "sci-grafico--blanco")  # y el recuadro sigue libre

    def test_el_202_imprime_su_organigrama_y_no_la_instruccion_de_edicion(self):
        emergencia = self.crear_emergencia("IMP-005")
        self.crear_formulario(emergencia, "202", {"organigrama__grafico": g.limpiar_organigrama(ORGANIGRAMA_BASICO)})
        respuesta = self.visualizar("202", emergencia)
        self.assertContains(respuesta, 'class="sci-organigrama__svg"')
        self.assertNotContains(respuesta, "Arrastre las cajas")

    def test_el_catalogo_en_blanco_deja_los_dos_recuadros_libres(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:sci_catalogo_visualizar", args=["201"]))
        self.assertContains(respuesta, "sci-grafico--blanco")
        self.assertNotContains(respuesta, "Espacio para el")


class DocumentoContinuoYResumenTests(BaseValidacion):
    def test_un_periodo_cerrado_muestra_los_graficos_como_solo_lectura(self):
        emergencia = self.crear_emergencia("CON-001")
        formulario = self.crear_formulario(emergencia, "201", {
            "croquis__dibujo": PNG_1X1,
            "organigrama__grafico": g.limpiar_organigrama(ORGANIGRAMA_BASICO),
        })
        bloque = hoja_de_solo_lectura(ESQUEMAS_SCI["201"], formulario)
        por_nombre = {s["nombre"]: s for s in bloque["secciones"]}
        self.assertFalse(por_nombre["croquis"]["vacia"])
        self.assertFalse(por_nombre["organigrama"]["vacia"])
        html = render_to_string("emergencias/fragmentos/sci_periodo_cerrado.html", {
            "bloque": bloque, "codigo": "201", "emergencia": emergencia,
        })
        self.assertIn(PNG_1X1, html)
        self.assertIn("sci-organigrama__svg", html)
        # Solo se dibuja: no hay un campo que pueda reenviar un periodo cerrado.
        self.assertNotIn("<input", html)
        self.assertNotIn("data-sci-croquis", html)

    def test_un_periodo_sin_graficos_dice_que_no_se_anoto(self):
        formulario = self.crear_formulario(self.crear_emergencia("CON-002"), "201", {})
        bloque = hoja_de_solo_lectura(ESQUEMAS_SCI["201"], formulario)
        por_nombre = {s["nombre"]: s for s in bloque["secciones"]}
        self.assertTrue(por_nombre["croquis"]["vacia"])
        self.assertTrue(por_nombre["organigrama"]["vacia"])

    def test_el_resumen_de_la_emergencia_muestra_los_graficos(self):
        emergencia = self.crear_emergencia("RES-001")
        self.crear_formulario(emergencia, "201", {
            "croquis__dibujo": PNG_1X1,
            "organigrama__grafico": g.limpiar_organigrama(ORGANIGRAMA_BASICO),
        })
        Emergencia.objects.filter(pk=emergencia.pk).update(estado=Emergencia.Estado.CERRADA)
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("dashboard:resumen_emergencia", args=[emergencia.pk]))
        self.assertContains(respuesta, "Croquis del incidente")
        self.assertContains(respuesta, "sci-organigrama__svg")

    def test_el_resumen_parte_los_textos_sin_espacios(self):
        """Estrategias y Tácticas con una cadena larguísima se salían de su recuadro."""
        plantilla = (Path(settings.BASE_DIR) / "templates" / "dashboard" / "resumen_emergencia.html"
                     ).read_text(encoding="utf-8")
        regla = re.search(r"\.texto-operativo\{([^}]*)\}", plantilla).group(1)
        for requisito in ("overflow-wrap:anywhere", "word-wrap:break-word", "word-break:break-word",
                          "white-space:pre-wrap", "max-width:100%"):
            self.assertIn(requisito, regla, requisito)

    def test_el_resumen_lleva_los_graficos_al_informe(self):
        emergencia = self.crear_emergencia("RES-002")
        self.crear_formulario(emergencia, "201", {
            "croquis__dibujo": PNG_1X1,
            "organigrama__grafico": g.limpiar_organigrama(ORGANIGRAMA_BASICO),
        })
        datos = datos_informe_emergencia(emergencia)
        self.assertEqual(datos["croquis_dibujo"], PNG_1X1)
        self.assertIn("<svg", datos["organigrama_svg"])


class InformePdfTests(SimpleTestCase):
    def test_el_croquis_entra_al_pdf_con_la_proporcion_de_la_hoja(self):
        imagen = _croquis_pdf(PNG_1X1)
        self.assertIsNotNone(imagen)
        self.assertAlmostEqual(imagen.drawHeight / imagen.drawWidth, 1.0, places=2)

    def test_un_croquis_ilegible_no_rompe_el_informe(self):
        self.assertIsNone(_croquis_pdf(""))
        self.assertIsNone(_croquis_pdf("data:image/png;base64,AAAA"))

    def test_el_organigrama_se_dibuja_con_las_mismas_cajas(self):
        dibujo = _organigrama_pdf(g.limpiar_organigrama(ORGANIGRAMA_BASICO))
        figuras = [type(f).__name__ for f in dibujo.contents]
        self.assertEqual(figuras.count("Rect"), 2)
        self.assertEqual(figuras.count("PolyLine"), 1)
        self.assertIsNone(_organigrama_pdf(""))


# ──────────────────────────────────────────────────────────────────────
# 3. El componente es uno: los archivos, sus versiones y la geometría duplicada
# ──────────────────────────────────────────────────────────────────────

class ComponenteTests(SimpleTestCase):
    def fuente(self, ruta):
        return (Path(settings.BASE_DIR) / ruta).read_text(encoding="utf-8")

    def test_la_geometria_del_js_es_la_del_servidor(self):
        """El organigrama se dibuja en dos sitios (el editor y la hoja impresa) y las
        cifras están duplicadas a propósito: si se cambia una, la hoja impresa dejaría
        de parecerse a lo que se dibujó."""
        js = self.fuente("static/emergencias/js/sci_organigrama.js")
        esperado = {
            "ANCHO": g.LIENZO_ANCHO, "ALTO": g.LIENZO_ALTO,
            "CAJA_ANCHO": g.CAJA_ANCHO, "CAJA_ALTO": g.CAJA_ALTO,
            "CARACTERES": g.CARACTERES_POR_LINEA, "LINEAS": g.LINEAS_POR_CAJA,
            "MAX_TEXTO": g.MAX_TEXTO_CAJA, "MAX_CAJAS": g.MAX_CAJAS,
        }
        for nombre, valor in esperado.items():
            hallado = re.search(rf"\b{nombre} = (\d+)", js)
            self.assertIsNotNone(hallado, nombre)
            self.assertEqual(int(hallado.group(1)), valor, nombre)

    def test_el_lienzo_del_croquis_mide_lo_que_declara_el_servidor(self):
        plantilla = self.fuente("templates/emergencias/fragmentos/croquis_editor.html")
        self.assertIn(f'data-ancho="{g.CROQUIS_ANCHO}"', plantilla)
        self.assertIn(f'data-alto="{g.CROQUIS_ALTO}"', plantilla)

    def test_los_dos_componentes_no_dependen_de_la_red(self):
        """Es una PWA que debe abrirse en el campo: nada de CDN ni de peticiones."""
        for ruta in ("static/emergencias/js/sci_croquis.js", "static/emergencias/js/sci_organigrama.js"):
            js = self.fuente(ruta)
            self.assertNotIn("http://", js.replace("http://www.w3.org/2000/svg", ""), ruta)
            self.assertNotIn("https://", js, ruta)
            self.assertNotIn("fetch(", js, ruta)
            self.assertNotIn("XMLHttpRequest", js, ruta)

    def test_los_controles_miden_al_menos_44_px(self):
        css = self.fuente("static/emergencias/css/sci_graficos.css")
        regla = re.search(r"\.sci-grafico__boton, \.sci-grafico__color, \.sci-grafico__grosor \{([^}]*)\}", css).group(1)
        self.assertIn("min-height: 2.75rem", regla)
        self.assertIn("min-width: 2.75rem", regla)

    def test_lo_que_el_editor_oculta_de_verdad_se_oculta(self):
        """La clase de los botones da «display», y eso gana al atributo «hidden»: los
        botones de eliminar se veían siempre, aunque no hubiera nada elegido."""
        css = self.fuente("static/emergencias/css/sci_graficos.css")
        self.assertIn(".sci-grafico__boton[hidden] { display: none; }", css)
        self.assertIn(".sci-organigrama__campo[hidden] { display: none; }", css)
        self.assertIn(".sci-organigrama__panel[hidden] { display: none; }", css)

    def test_cada_pagina_que_usa_los_componentes_enlaza_sus_archivos(self):
        raiz = Path(settings.BASE_DIR) / "templates"
        editores = ("emergencias/sci_editar.html", "emergencias/sci_editar_201.html")
        for plantilla in editores:
            fuente = (raiz / plantilla).read_text(encoding="utf-8")
            for archivo in ("sci_graficos.css", "sci_croquis.js", "sci_organigrama.js"):
                self.assertIn(archivo, fuente, f"{plantilla} no enlaza {archivo}")
        lectura = ("emergencias/sci_preview.html", "emergencias/sci_preview_201.html",
                   "dashboard/resumen_emergencia.html")
        for plantilla in lectura:
            self.assertIn("sci_graficos.css", (raiz / plantilla).read_text(encoding="utf-8"), plantilla)

    def test_la_hoja_impresa_no_dibuja_ni_edita_nada_con_javascript(self):
        raiz = Path(settings.BASE_DIR) / "templates" / "emergencias" / "fragmentos"
        for nombre in ("croquis_lectura.html", "organigrama_lectura.html"):
            self.assertNotIn("<script", (raiz / nombre).read_text(encoding="utf-8"), nombre)
