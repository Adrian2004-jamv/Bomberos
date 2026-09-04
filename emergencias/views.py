import csv
import json
import re
from collections import defaultdict
from datetime import timedelta
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import (Case, Count, Exists, IntegerField, OuterRef,
                              ProtectedError, Q, Value, When)
from django.http import Http404, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from inventario.models import Recurso
from inventario.permissions import estaciones_permitidas, recursos_permitidos

from .forms import (DespachoUnidadForm, EmergenciaEdicionForm, EmergenciaForm,
                    FiltroIncidentesForm)
from .models import DespliegueUnidad, Emergencia
from .models import FormularioSCI, FormularioSCI211
from .forms_sci import (FormularioSCI211Form, RegistroRecursoSCI211FormSet,
                        agrupar_recursos, etiqueta_de_recurso)
from .permissions import (conduce_el_despliegue, despliegues_asignados,
                          despliegues_conducidos,
                          es_chofer, estacion_autorizada, solo_es_chofer,
                          puede_consultar_emergencias,
                          puede_consultar_sci, puede_editar_sci,
                          puede_gestionar_emergencias)
from .codigos import generar_codigo_emergencia
from .esquemas_sci import (ESQUEMAS_SCI, FORMULARIOS_SCI_CONTINUOS,
                          ORIGEN_EN_EL_LUGAR, ORIGEN_INVENTARIO,
                          campos_periodo, extraer_datos, obtener_esquema,
                          obtener_esquema_catalogo, secciones_completadas,
                          secciones_con_valores)
from .services import (TRANSICIONES_VALIDAS, cambiar_estado_despliegue,
                       detener_transmision,
                       cambiar_estado_emergencia, desplegar_unidad,
                       registrar_posicion_unidad, transiciones_disponibles)
from .services_sci import (crear_sci211_desde_emergencia,
                          desplegar_recursos_del_sci211, finalizar_sci,
                          finalizar_sci211, registrar_solicitud_en_sci211,
                          tiene_contenido)

_ORIENTACION = {"vertical": "Vertical", "horizontal": "Horizontal"}

# ==========================================
# MÓDULO: CATÁLOGO Y FLUJO DE FORMULARIOS SCI
# ==========================================

def entrada_catalogo(codigo, esquema):
    paginas = esquema["paginas"]
    return {
        "codigo": codigo,
        "nombre": esquema["nombre"],
        "formato": f"{_ORIENTACION[esquema['orientacion']]} · {paginas} página{'s' if paginas > 1 else ''}",
        "estructura": esquema["proposito"],
        "implementado": True,
    }

ORDEN_FORMULARIOS_SCI = (
    "201", "207", "211",  # Fase 1: entender la situación.
    "202", "203",         # Fase 2: objetivos y organización.
    "204", "205", "206", "215",  # Fase 3: desarrollar el PAI.
    "214",                 # Ejecución y registro continuo.
    "221",                 # Desmovilización.
    "222",                 # Comando de Área, cuando aplique.
)
ETAPA_FORMULARIO_SCI = {
    "201": "Entender la situación", "207": "Entender la situación",
    "211": "Entender la situación", "202": "Objetivos y estrategias",
    "203": "Organización del periodo", "204": "Desarrollar el PAI",
    "205": "Desarrollar el PAI", "206": "Desarrollar el PAI",
    "215": "Seguridad del PAI", "214": "Ejecutar, evaluar y revisar",
    "221": "Desmovilización", "222": "Comando de Área (si aplica)",
}
_POSICION_FORMULARIO_SCI = {
    codigo: posicion for posicion, codigo in enumerate(ORDEN_FORMULARIOS_SCI)
}

def registro_en_uso(formulario):
    """Si el registro ya se está escribiendo, sea cuadrícula propia o JSON.

    El SCI-211 guarda sus filas en un modelo aparte; los demás, en el JSON del
    formulario. «tiene_contenido» descarta las filas en blanco, de modo que un
    formulario abierto y vacío no cuenta como empezado.
    """
    if formulario is None:
        return False
    if hasattr(formulario, "registros"):
        return formulario.registros.exists()
    return tiene_contenido(formulario.datos)

def formularios_sci_finalizados(emergencia):
    """Códigos SCI que ya no detienen a los siguientes.

    Son los finalizados y, siempre, las bitácoras: por definición no se cierran
    hasta que la emergencia termina.
    """
    genericos = list(emergencia.formularios_sci.all())
    finalizados = {
        formulario.codigo_sci for formulario in genericos
        if formulario.estado == FormularioSCI.Estado.FINALIZADO
    }
    # Una bitácora nunca detiene a las que vienen detrás. No puede cerrarse
    # hasta que la emergencia termine, de modo que exigir su cierre —o siquiera
    # que tenga algo escrito— dejaba al SCI-221 con un candado y el mensaje
    # «finalice el paso anterior», que es una instrucción imposible: el sistema
    # prohíbe finalizarlo. Y la desmovilización se verifica mientras la
    # bitácora sigue recibiendo anotaciones, no después.
    finalizados.update(FORMULARIOS_SCI_CONTINUOS)
    return finalizados

def desbloqueado_con(codigo, finalizados):
    """Regla de desbloqueo, sin tocar la base.

    La comparten la pantalla que dibuja el candado y la vista que decide si
    deja entrar. Cuando cada una tenía la suya, una tarjeta podía mostrarse
    cerrada mientras el formulario ya era accesible.
    """
    if codigo not in _POSICION_FORMULARIO_SCI:
        return False
    # Una bitácora no espera turno. Se escribe mientras ocurren las cosas: la
    # unidad sale antes de que nadie redacte el resumen del incidente, y las
    # actividades del periodo empiezan mucho antes de que el plan de acción
    # esté escrito. Abrirlas al llegar su número las volvería inservibles como
    # registro, que es justamente para lo que existen.
    #
    # Conservan su lugar en el orden recomendado, que sigue guiando la
    # documentación, y siguen siendo requisito de los que vienen después.
    if codigo in FORMULARIOS_SCI_CONTINUOS:
        return True
    anteriores = ORDEN_FORMULARIOS_SCI[:_POSICION_FORMULARIO_SCI[codigo]]
    return all(anterior in finalizados for anterior in anteriores)

def formulario_sci_desbloqueado(emergencia, codigo):
    """Solo permite avanzar cuando todos los formularios anteriores finalizaron."""
    if codigo not in _POSICION_FORMULARIO_SCI:
        return False
    return desbloqueado_con(codigo, formularios_sci_finalizados(emergencia))

def redirigir_si_sci_bloqueado(request, emergencia, codigo):
    if codigo not in _POSICION_FORMULARIO_SCI:
        raise Http404
    if formulario_sci_desbloqueado(emergencia, codigo):
        return None
    posicion = _POSICION_FORMULARIO_SCI[codigo]
    anterior = ORDEN_FORMULARIOS_SCI[posicion - 1]
    messages.warning(
        request,
        f"Finalice primero el formulario SCI-{anterior} para desbloquear SCI-{codigo}.",
    )
    return redirect(
        reverse("emergencias:detalle", args=[emergencia.pk]) + "#formularios-sci"
    )

CATALOGO_FORMULARIOS_SCI = tuple(sorted(
    [entrada_catalogo(codigo, esquema) for codigo, esquema in ESQUEMAS_SCI.items()] + [{
        "codigo": "211",
        "nombre": "Registro y Control de Recursos",
        "formato": "Horizontal · 2 páginas",
        "estructura": "Fuente maestra de recursos: solicitud, arribo, institución, estado, "
                      "asignación y desmovilización de cada recurso del incidente.",
        "implementado": True,
    }],
    key=lambda entrada: _POSICION_FORMULARIO_SCI[entrada["codigo"]],
))

# ==========================================
# MÓDULO: REGISTRO DE EMERGENCIAS
# ==========================================

def emergencias_permitidas(usuario):
    return Emergencia.objects.filter(
        estacion_responsable__in=estaciones_permitidas(usuario)
    ).select_related(
        "estacion_responsable",
        "estacion_responsable__cuerpo_bomberos",
        "registrado_por",
    ).annotate(
        cantidad_formularios_genericos=Count("formularios_sci", distinct=True),
        tiene_sci211=Exists(
            FormularioSCI211.objects.filter(emergencia_id=OuterRef("pk"))
        ),
        sci211_finalizado=Exists(
            FormularioSCI211.objects.filter(
                emergencia_id=OuterRef("pk"),
                estado=FormularioSCI211.Estado.FINALIZADO,
            )
        ),
    ).annotate(
        # El total de formularios se calcula en la base porque la etapa
        # documental es ahora un filtro, y filtrar en Python obligaria a traer
        # el padron completo para descartar casi todo.
        formularios_registrados=Count("formularios_sci", distinct=True) + Case(
            When(tiene_sci211=True, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
    # Al agrupar por la anotación, Django deja de aplicar el orden declarado en
    # el modelo, y paginar sin orden explícito devuelve resultados inestables.
    ).order_by("-fecha_reporte", "-pk")

ESTADOS_TERMINADOS = (Emergencia.Estado.CERRADA, Emergencia.Estado.CANCELADA)
TOTAL_FORMULARIOS_SCI = len(CATALOGO_FORMULARIOS_SCI)
INCIDENTES_POR_PAGINA = 12

def filtrar_por_texto(emergencias, termino):
    """Busca en codigo, tipo, estacion, direccion y etiqueta del estado.

    El estado se guarda como clave, de modo que se traduce el termino a las
    claves cuyas etiquetas lo contienen antes de consultar.
    """
    estados = [
        valor for valor, etiqueta in Emergencia.Estado.choices
        if termino.lower() in etiqueta.lower()
    ]
    condicion = (
        Q(codigo__icontains=termino)
        | Q(tipo_emergencia__icontains=termino)
        | Q(estacion_responsable__nombre__icontains=termino)
        | Q(direccion__icontains=termino)
    )
    if estados:
        condicion |= Q(estado__in=estados)
    return emergencias.filter(condicion)

def filtrar_por_etapa(emergencias, etapa):
    if etapa == "sin_iniciar":
        return emergencias.filter(formularios_registrados=0)
    if etapa == "completa":
        return emergencias.filter(formularios_registrados=TOTAL_FORMULARIOS_SCI)
    return emergencias.filter(
        formularios_registrados__gt=0,
        formularios_registrados__lt=TOTAL_FORMULARIOS_SCI,
    )

def estado_documental_por_emergencia(emergencias):
    """Qué formularios tiene cerrados y cuáles en borrador cada emergencia.

    Se resuelve en dos consultas para todo el listado. Preguntarlo por fila
    costaría dos por emergencia, y esta pantalla se pagina de veinte en veinte.
    """
    identificadores = [emergencia.pk for emergencia in emergencias]
    finalizados = defaultdict(set)
    borradores = defaultdict(set)
    bitacoras = defaultdict(set)
    if not identificadores:
        return finalizados, borradores, bitacoras

    for emergencia_id, codigo, estado, datos in FormularioSCI.objects.filter(
        emergencia_id__in=identificadores
    ).values_list("emergencia_id", "codigo_sci", "estado", "datos"):
        destino = (finalizados if estado == FormularioSCI.Estado.FINALIZADO
                   else borradores)
        destino[emergencia_id].add(codigo)
        if codigo in FORMULARIOS_SCI_CONTINUOS and tiene_contenido(datos):
            bitacoras[emergencia_id].add(codigo)

    for emergencia_id, estado, registros in FormularioSCI211.objects.filter(
        emergencia_id__in=identificadores
    ).annotate(registros_anotados=Count("registros")).values_list(
        "emergencia_id", "estado", "registros_anotados"
    ):
        destino = (finalizados if estado == FormularioSCI211.Estado.FINALIZADO
                   else borradores)
        destino[emergencia_id].add("211")
        if "211" in FORMULARIOS_SCI_CONTINUOS and registros:
            bitacoras[emergencia_id].add("211")

    return finalizados, borradores, bitacoras

def formulario_en_curso(cerrados, empezados, bitacoras_en_uso):
    """El primer formulario del orden oficial que aún queda por llenar.

    Las bitácoras ya en uso no cuentan: el SCI-211 y el SCI-214 siguen
    abiertos hasta que la emergencia termina, de modo que señalarlas dejaría
    la columna clavada en ellas por más formularios que se llenaran después.

    Devuelve ``(codigo, empezado)``, o ``(None, False)`` cuando no queda
    ninguno. Es el mismo criterio con el que la ficha anuncia el paso
    siguiente, para que las dos pantallas señalen el mismo formulario.
    """
    for codigo in ORDEN_FORMULARIOS_SCI:
        if codigo in bitacoras_en_uso:
            continue
        if codigo not in cerrados:
            return codigo, codigo in empezados
    return None, False

def preparar_avance_documental(emergencias):
    finalizados, borradores, bitacoras = estado_documental_por_emergencia(emergencias)
    for emergencia in emergencias:
        emergencia.formularios_completados = emergencia.formularios_registrados
        emergencia.porcentaje_formularios = round(
            emergencia.formularios_completados / TOTAL_FORMULARIOS_SCI * 100
        )
        abiertas = sorted(bitacoras[emergencia.pk])
        codigo, empezado = formulario_en_curso(
            finalizados[emergencia.pk], borradores[emergencia.pk], abiertas
        )
        # Antes esta línea nombraba siempre al SCI-211, aunque se estuviera
        # llenando otro: el listado decía «SCI-211 en borrador» al lado de una
        # emergencia cuyo 211 ya estaba cerrado hacía rato.
        emergencia.formulario_actual = f"SCI-{codigo}" if codigo else ""
        emergencia.formulario_actual_empezado = empezado
        emergencia.bitacoras_abiertas = [f"SCI-{item}" for item in abiertas]

        if emergencia.formularios_completados == 0:
            emergencia.etapa_formularios = "Sin iniciar"
            emergencia.clave_etapa_formularios = "sin_iniciar"
        elif codigo is None:
            # «Completa» se decide por lo que queda por llenar y no por cuántos
            # formularios existen: una fila podía anunciarse completa mientras
            # debajo se leía que el SCI-201 seguía en borrador.
            emergencia.etapa_formularios = "Completa"
            emergencia.clave_etapa_formularios = "completa"
        else:
            emergencia.etapa_formularios = f"{emergencia.formulario_actual} en curso"
            emergencia.clave_etapa_formularios = "en_elaboracion"
    return emergencias

def consulta_filtrada(request):
    """Aplica busqueda, tipo y etapa documental, sin la fase.

    La comparten el listado y la exportacion, para que el archivo contenga
    exactamente lo que la pantalla dice estar mostrando.
    """
    formulario = FiltroIncidentesForm(request.GET or None)
    filtros = formulario.cleaned_data if formulario.is_valid() else {}
    emergencias = emergencias_permitidas(request.user)
    if filtros.get("q"):
        emergencias = filtrar_por_texto(emergencias, filtros["q"])
    if filtros.get("tipo"):
        # Se usa coincidencia parcial porque el registro admite descripciones
        # mas especificas, por ejemplo «Rescate en altura».
        emergencias = emergencias.filter(
            tipo_emergencia__icontains=filtros["tipo"]
        )
    if filtros.get("etapa"):
        emergencias = filtrar_por_etapa(emergencias, filtros["etapa"])
    # __date convierte la marca de tiempo a la zona horaria configurada antes de
    # comparar, de modo que el rango corresponde a los días locales que el
    # usuario eligió y no a los del UTC almacenado. Ambos extremos se incluyen.
    if filtros.get("desde"):
        emergencias = emergencias.filter(fecha_reporte__date__gte=filtros["desde"])
    if filtros.get("hasta"):
        emergencias = emergencias.filter(fecha_reporte__date__lte=filtros["hasta"])
    return formulario, filtros, emergencias

def aplicar_fase(emergencias, fase):
    if fase == "curso":
        return emergencias.exclude(estado__in=ESTADOS_TERMINADOS)
    if fase == "terminada":
        return emergencias.filter(estado__in=ESTADOS_TERMINADOS)
    return emergencias

@login_required
@require_GET
def lista(request):
    """Registro de incidentes con filtros y paginacion resueltos en la base.

    Los conteos de cada fase se calculan sobre la consulta ya filtrada por
    texto y etapa, pero sin la fase: son las cifras que rotulan los botones y
    deben corresponder a lo que se veria al pulsarlos.
    """
    # El chofer aterriza aquí al iniciar sesión, porque es la página de destino
    # configurada. En vez de negarle el paso se le lleva a la suya.
    if solo_es_chofer(request.user):
        return redirect("emergencias:mi_unidad")
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied

    formulario, filtros, emergencias = consulta_filtrada(request)

    total_en_curso = emergencias.exclude(estado__in=ESTADOS_TERMINADOS).count()
    total_terminadas = emergencias.filter(estado__in=ESTADOS_TERMINADOS).count()

    fase = filtros.get("fase") or "all"
    emergencias = aplicar_fase(emergencias, fase)

    # El mapa dibuja todos los incidentes autorizados, no solo los de la pagina.
    # Se le entrega el conjunto que si pasa el filtro para que atenue el resto,
    # en lugar de repetir la logica de filtrado en JavaScript.
    ids_en_filtro = list(emergencias.values_list("pk", flat=True))

    pagina = Paginator(emergencias, INCIDENTES_POR_PAGINA).get_page(
        request.GET.get("pagina")
    )
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    sin_fase = parametros.copy()
    sin_fase.pop("fase", None)
    contexto = {
        "form": formulario,
        "emergencias": preparar_avance_documental(pagina.object_list),
        "pagina": pagina,
        "querystring": parametros.urlencode(),
        "querystring_sin_fase": sin_fase.urlencode(),
        "fase_activa": fase,
        "total_en_curso": total_en_curso,
        "total_terminadas": total_terminadas,
        "total_filtrado": total_en_curso + total_terminadas,
        "hay_filtros": bool(
            filtros.get("q") or filtros.get("tipo")
            or filtros.get("etapa") or filtros.get("fase")
            or filtros.get("desde") or filtros.get("hasta")
            # Un rango mal escrito debe seguir ofreciendo «Limpiar»: sin esto la
            # única salida sería borrar la dirección a mano.
            or formulario.errors
        ),
        "puede_crear": puede_gestionar_emergencias(request.user),
        "puede_eliminar": request.user.is_staff or puede_gestionar_emergencias(request.user),
        "ids_en_filtro_json": json.dumps(ids_en_filtro),
    }

    return render(request, "emergencias/lista.html", contexto)

COLUMNAS_EXPORTACION = (
    "Código", "Tipo de emergencia", "Prioridad", "Estado", "Fase operativa",
    "Fecha de reporte", "Fecha de cierre", "Institución", "Estación responsable",
    "Dirección", "Latitud", "Longitud", "Unidades desplegadas",
    "Unidades activas", "Formularios SCI", "SCI-211", "Registrado por",
)

def fila_exportacion(emergencia):
    if emergencia.sci211_finalizado:
        sci211 = "Finalizado"
    elif emergencia.tiene_sci211:
        sci211 = "Borrador"
    else:
        sci211 = "Pendiente"
    return (
        emergencia.codigo,
        emergencia.tipo_emergencia,
        emergencia.get_prioridad_display(),
        emergencia.get_estado_display(),
        emergencia.fase_operativa,
        timezone.localtime(emergencia.fecha_reporte).strftime("%d/%m/%Y %H:%M"),
        timezone.localtime(emergencia.fecha_cierre).strftime("%d/%m/%Y %H:%M")
        if emergencia.fecha_cierre else "",
        emergencia.estacion_responsable.cuerpo_bomberos.nombre,
        emergencia.estacion_responsable.nombre,
        emergencia.direccion,
        emergencia.latitud if emergencia.latitud is not None else "",
        emergencia.longitud if emergencia.longitud is not None else "",
        emergencia.total_despliegues,
        emergencia.despliegues_activos,
        f"{emergencia.formularios_registrados}/{TOTAL_FORMULARIOS_SCI}",
        sci211,
        emergencia.registrado_por.get_full_name() or emergencia.registrado_por.username,
    )

class _Eco:
    """Sustituye al archivo que espera ``csv.writer`` y devuelve cada linea."""

    def write(self, valor):
        return valor

@login_required
@require_GET
def exportar(request):
    """Descarga en CSV el registro completo que corresponde a los filtros.

    No se exporta desde el navegador porque el listado esta paginado: la tabla
    solo tiene doce filas y el archivo debe traer todas. Se transmite por
    tramos para no armar el padron entero en memoria.
    """
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied

    _, filtros, emergencias = consulta_filtrada(request)
    emergencias = aplicar_fase(emergencias, filtros.get("fase") or "all").annotate(
        total_despliegues=Count("despliegues", distinct=True),
        despliegues_activos=Count(
            "despliegues",
            filter=Q(despliegues__estado__in=DespliegueUnidad.ESTADOS_ACTIVOS),
            distinct=True,
        ),
    )

    escritor = csv.writer(_Eco(), delimiter=";")

    def tramos():
        # Excel abre el archivo con la codificacion del sistema si no encuentra
        # la marca de orden de bytes, y los acentos llegan rotos.
        yield "\ufeff"
        yield escritor.writerow(COLUMNAS_EXPORTACION)
        for emergencia in emergencias.iterator():
            yield escritor.writerow(fila_exportacion(emergencia))

    momento = timezone.localtime().strftime("%Y%m%d-%H%M")
    respuesta = StreamingHttpResponse(tramos(), content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = (
        f'attachment; filename="incidentes-{momento}.csv"'
    )
    return respuesta

COLUMNAS_RECURSOS = (
    "Emergencia", "Tipo de emergencia", "Prioridad", "Fecha de reporte",
    "Estación responsable", "Dirección", "Unidad", "Nombre de la unidad",
    "Tipo de recurso", "Categoría", "Estación de procedencia",
    "Estado del despliegue", "Asignada", "Salida", "En sitio", "Cierre",
    "Responsable de la unidad", "Despachada por", "Posiciones registradas",
)

def fila_recurso(despliegue):
    """Una fila por unidad desplegada, no por emergencia.

    El reporte anterior contaba cuántas unidades salieron; este dice cuáles,
    de dónde, cuándo y quién las conducía, que es lo que se revisa después de
    una intervención.
    """
    def momento(valor):
        return timezone.localtime(valor).strftime("%d/%m/%Y %H:%M") if valor else ""

    emergencia = despliegue.emergencia
    conductor = despliegue.responsable_unidad
    return [
        emergencia.codigo, emergencia.tipo_emergencia,
        emergencia.get_prioridad_display(), momento(emergencia.fecha_reporte),
        emergencia.estacion_responsable.nombre, emergencia.direccion,
        despliegue.unidad.codigo_interno, despliegue.unidad.nombre,
        despliegue.unidad.tipo.nombre, despliegue.unidad.tipo.categoria.nombre,
        despliegue.estacion_procedencia.nombre,
        despliegue.get_estado_display(),
        momento(despliegue.fecha_asignacion), momento(despliegue.fecha_salida),
        momento(despliegue.fecha_llegada), momento(despliegue.fecha_retorno),
        conductor.get_full_name() or conductor.username if conductor else "",
        despliegue.despachado_por.get_full_name() or despliegue.despachado_por.username,
        despliegue.posiciones_registradas,
    ]

@login_required
def exportar_recursos(request):
    """Reporte detallado de los recursos desplegados, con los mismos filtros.

    Comparte la consulta del listado, de modo que el rango de fechas, el tipo
    y la emergencia que estén aplicados en pantalla se llevan al archivo sin
    tener que elegirlos otra vez.
    """
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied

    _, filtros, emergencias = consulta_filtrada(request)
    emergencias = aplicar_fase(emergencias, filtros.get("fase") or "all")
    despliegues = DespliegueUnidad.objects.filter(
        emergencia__in=emergencias.values("pk")
    ).select_related(
        "emergencia", "emergencia__estacion_responsable",
        "unidad", "unidad__tipo", "unidad__tipo__categoria",
        "estacion_procedencia", "responsable_unidad", "despachado_por",
    ).annotate(
        posiciones_registradas=Count("posiciones", distinct=True)
    ).order_by("emergencia__fecha_reporte", "emergencia_id", "fecha_asignacion")

    escritor = csv.writer(_Eco(), delimiter=";")

    def tramos():
        # Excel abre el archivo con la codificación del sistema si no encuentra
        # la marca de orden de bytes, y los acentos llegan rotos.
        yield "﻿"
        yield escritor.writerow(COLUMNAS_RECURSOS)
        for despliegue in despliegues.iterator():
            yield escritor.writerow(fila_recurso(despliegue))

    momento = timezone.localtime().strftime("%Y%m%d-%H%M")
    respuesta = StreamingHttpResponse(tramos(), content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = (
        f'attachment; filename="recursos-desplegados-{momento}.csv"'
    )
    return respuesta

# ==========================================
# MÓDULO: ALTA Y EDICIÓN DE LA EMERGENCIA
# ==========================================

@login_required
def crear(request):
    if not puede_gestionar_emergencias(request.user):
        raise PermissionDenied
    formulario = EmergenciaForm(request.POST or None, usuario=request.user)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            emergencia = formulario.save(commit=False)
            emergencia.codigo = generar_codigo_emergencia(
                emergencia.tipo_emergencia, emergencia.fecha_reporte
            )
            emergencia.registrado_por = request.user
            emergencia.estado = Emergencia.Estado.REPORTADA
            emergencia.save()
        messages.success(request, "Emergencia registrada correctamente.")
        return redirect("emergencias:detalle", pk=emergencia.pk)
    contexto = {
        "form": formulario,
        "titulo": "Crear emergencia",
        "eyebrow": "Paso 1 de 2 · Registro operativo",
        "encabezado": "Datos iniciales del incidente",
        "accion": "Registrar emergencia",
        "url_cancelar": reverse("emergencias:lista") + "#registro-incidentes",
        "es_creacion": True,
    }

    return render(request, "emergencias/formulario.html", contexto)

@login_required
def editar(request, pk):
    """Corrige la información situacional de un incidente todavía en curso."""
    emergencia = get_object_or_404(emergencias_permitidas(request.user), pk=pk)
    if not estacion_autorizada(request.user, emergencia.estacion_responsable_id):
        raise PermissionDenied
    if emergencia.esta_terminada:
        messages.info(request, "Una emergencia terminada ya no se puede editar.")
        return redirect("emergencias:detalle", pk=emergencia.pk)
    formulario = EmergenciaEdicionForm(request.POST or None, instance=emergencia)
    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Emergencia actualizada correctamente.")
        return redirect("emergencias:detalle", pk=emergencia.pk)
    contexto = {
        "form": formulario,
        "emergencia": emergencia,
        "titulo": f"Editar {emergencia.codigo}",
        "eyebrow": f"{emergencia.codigo} · {emergencia.get_estado_display()}",
        "encabezado": "Situación del incidente",
        "accion": "Guardar cambios",
        "url_cancelar": reverse("emergencias:detalle", args=[emergencia.pk]),
        "es_creacion": False,
    }

    return render(request, "emergencias/formulario.html", contexto)


@login_required
@require_POST
def eliminar(request, pk):
    """Borra una emergencia que aún no tiene historia. Solo staff o gestores.

    Sirve para deshacer un registro equivocado, no para hacer desaparecer una
    intervención. Los formularios SCI y los despliegues protegen su emergencia
    a nivel de base de datos: son documentación oficial y no se destruyen. Si
    la intervención ya empezó, lo que corresponde es cancelarla.
    """
    if not (request.user.is_staff or puede_gestionar_emergencias(request.user)):
        raise PermissionDenied
    emergencia = get_object_or_404(emergencias_permitidas(request.user), pk=pk)
    codigo = emergencia.codigo

    try:
        emergencia.delete()
    except ProtectedError:
        messages.error(
            request,
            f"La emergencia {codigo} ya tiene formularios SCI o unidades "
            "despachadas y no puede eliminarse: es documentación de la "
            "intervención. Cámbiela a cancelada si se registró por error.",
        )
        return redirect("emergencias:detalle", pk=pk)
    messages.success(request, f"Emergencia {codigo} eliminada correctamente.")
    return redirect("emergencias:lista")


@login_required
@require_POST
def cambiar_estado(request, pk):
    """Avanza el ciclo operativo del incidente."""
    emergencia = get_object_or_404(emergencias_permitidas(request.user), pk=pk)
    try:
        emergencia = cambiar_estado_emergencia(
            emergencia, request.POST.get("estado", ""), request.user
        )
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(
            request, f"La emergencia pasó a {emergencia.get_estado_display().lower()}."
        )
    return redirect("emergencias:detalle", pk=emergencia.pk)

# ==========================================
# MÓDULO: DESPACHO DE UNIDADES
# ==========================================

@login_required
def despachar(request, pk):
    """Envía una unidad disponible del ámbito del usuario al incidente."""
    emergencia = get_object_or_404(emergencias_permitidas(request.user), pk=pk)
    if not estacion_autorizada(request.user, emergencia.estacion_responsable_id):
        raise PermissionDenied
    if not emergencia.admite_despliegues:
        messages.info(request, "Una emergencia terminada no admite despliegues.")
        return redirect("emergencias:detalle", pk=emergencia.pk)
    formulario = DespachoUnidadForm(
        request.POST or None, emergencia=emergencia, usuario=request.user
    )
    if request.method == "POST" and formulario.is_valid():
        try:
            despliegue = desplegar_unidad(
                emergencia,
                formulario.cleaned_data["unidad"],
                request.user,
                formulario.cleaned_data["observaciones"],
            )
        except ValidationError as error:
            formulario.add_error(None, error)
        else:
            messages.success(
                request,
                f"La unidad {despliegue.unidad.codigo_interno} fue despachada al incidente.",
            )
            return redirect("emergencias:detalle", pk=emergencia.pk)
    contexto = {
        "emergencia": emergencia,
        "form": formulario,
        "hay_unidades": formulario.fields["unidad"].queryset.exists(),
    }

    return render(request, "emergencias/despachar.html", contexto)

@login_required
@require_POST
def actualizar_despliegue(request, pk):
    """Mueve un despliegue por sus estados y libera la unidad al terminar."""
    despliegue = despliegue_alcanzable(request.user, pk)
    try:
        cambiar_estado_despliegue(
            despliegue,
            request.POST.get("estado", ""),
            request.user,
            request.POST.get("observaciones", ""),
        )
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        despliegue.refresh_from_db()
        messages.success(
            request,
            f"{despliegue.unidad.codigo_interno}: {despliegue.get_estado_display().lower()}.",
        )
    return redirect("emergencias:detalle", pk=despliegue.emergencia_id)

# ==========================================
# MÓDULO: FICHA DE LA EMERGENCIA
# ==========================================

@login_required
def detalle(request, pk):
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied
    emergencia = get_object_or_404(emergencias_permitidas(request.user), pk=pk)
    sci211 = getattr(emergencia, "formulario_sci_211", None)
    genericos = {
        formulario.codigo_sci: formulario
        for formulario in emergencia.formularios_sci.all()
    }
    catalogo_sci_estado = []
    finalizados = formularios_sci_finalizados(emergencia)
    for numero, item in enumerate(CATALOGO_FORMULARIOS_SCI, start=1):
        formulario = sci211 if item["codigo"] == "211" else genericos.get(item["codigo"])
        en_curso = False
        if item["codigo"] in FORMULARIOS_SCI_CONTINUOS and formulario is None:
            # Una bitácora sin abrir sigue siendo una bitácora: se pinta como
            # tal desde el principio, igual que su hermana ya empezada.
            clave_estado, etiqueta_estado = "open", "Registro abierto · sin anotaciones"
        elif formulario is None:
            clave_estado, etiqueta_estado = "pending", "No iniciado"
        elif formulario.estado == FormularioSCI.Estado.FINALIZADO:
            clave_estado, etiqueta_estado = "complete", "Finalizado"
        elif item["codigo"] in FORMULARIOS_SCI_CONTINUOS:
            # El azul describe qué clase de formulario es —una bitácora que
            # vive toda la emergencia—, no cuánto lleva escrito. El ámbar
            # anunciaría algo por corregir y el gris, algo que no ha empezado.
            clave_estado = "open"
            # Solo deja de señalarse como paso pendiente cuando ya tiene algo
            # anotado: una bitácora en blanco sí es lo primero que hay que
            # llenar.
            en_curso = registro_en_uso(formulario)
            etiqueta_estado = (
                "Registro abierto" if en_curso
                else "Registro abierto · sin anotaciones"
            )
        else:
            clave_estado, etiqueta_estado = "incomplete", "Incompleto"
        catalogo_sci_estado.append({
            **item,
            "numero": numero,
            "clave_estado": clave_estado,
            "etiqueta_estado": etiqueta_estado,
            "etapa_orden": ETAPA_FORMULARIO_SCI[item["codigo"]],
            "bloqueado": not desbloqueado_con(item["codigo"], finalizados),
            "en_curso": en_curso,
        })
    puede_gestionar = estacion_autorizada(request.user, emergencia.estacion_responsable_id)
    despliegues = list(emergencia.despliegues.select_related(
        "unidad", "estacion_procedencia", "despachado_por"
    ))
    for despliegue in despliegues:
        # La tabla solo ofrece cerrar el despliegue y transmitir el GPS. Cerrarlo
        # El botón de transición de estado se oculta en la vista de detalle;
        # el despliegue se finaliza automáticamente al cerrar la emergencia.
        despliegue.transiciones = []
    contexto = {
        "emergencia": emergencia,
        "despliegues": despliegues,
        "puede_gestionar_en_admin": request.user.is_staff,
        "puede_transmitir_gps": puede_gestionar_emergencias(request.user),
        "puede_gestionar": puede_gestionar,
        "sci211": sci211,
        "sci211_bloqueado": not formulario_sci_desbloqueado(emergencia, "211"),
        "puede_editar_sci": puede_editar_sci(request.user, emergencia),
        "catalogo_sci": catalogo_sci_estado,
        "formularios_imprimibles": [
            item for item in catalogo_sci_estado
            if item["clave_estado"] == "complete"
        ],
        # Un registro ya en uso no es «el paso siguiente»: seguirá abierto toda
        # la emergencia, y anunciarlo dejaría el aviso clavado en el SCI-211
        # sin señalar nunca lo que de verdad falta por llenar.
        "siguiente_formulario": next(
            (item for item in catalogo_sci_estado
             if item["clave_estado"] != "complete"
             and not item["bloqueado"] and not item["en_curso"]),
            None
        ),
    }

    return render(request, "emergencias/detalle.html", contexto)

# ==========================================
# MÓDULO: FORMULARIOS SCI
# ==========================================

def formularios_sci_permitidos(usuario):
    return FormularioSCI211.objects.filter(
        emergencia__estacion_responsable__in=estaciones_permitidas(usuario)
    ).select_related("emergencia", "creado_por", "modificado_por", "finalizado_por")

def emergencia_para_visualizar(usuario):
    # Antes se prefería un código sembrado fijo; la migración 0008 lo convirtió
    # al formato oficial, así que esa búsqueda ya no encontraba nada.
    return emergencias_permitidas(usuario).order_by("pk").first()

def preparar_expedientes_sci(usuario):
    emergencias = list(
        emergencias_permitidas(usuario)
        .select_related("formulario_sci_211")
        .prefetch_related("formularios_sci")
    )
    preparar_avance_documental(emergencias)
    catalogo = {item["codigo"]: item for item in CATALOGO_FORMULARIOS_SCI}
    for emergencia in emergencias:
        genericos = {formulario.codigo_sci: formulario for formulario in emergencia.formularios_sci.all()}
        sci211 = getattr(emergencia, "formulario_sci_211", None)
        documentos = []
        for item in CATALOGO_FORMULARIOS_SCI:
            codigo = item["codigo"]
            if codigo == "211":
                if sci211 is None:
                    continue
                finalizado = sci211.estado == FormularioSCI211.Estado.FINALIZADO
                documentos.append({
                    **catalogo[codigo],
                    "estado": "Finalizado" if finalizado else "Borrador",
                    "clave_estado": "complete" if finalizado else "draft",
                    "actualizado": sci211.fecha_actualizacion,
                    "editable": puede_editar_sci(usuario, emergencia) and not finalizado,
                    "sci211": sci211,
                })
                continue
            formulario = genericos.get(codigo)
            if formulario is None:
                continue
            secciones_llenas, secciones_totales = secciones_completadas(
                obtener_esquema(codigo), formulario.datos
            )
            completo = bool(secciones_totales) and secciones_llenas == secciones_totales
            documentos.append({
                **catalogo[codigo],
                "estado": "Completo" if completo else "En elaboración",
                "clave_estado": "complete" if completo else "draft",
                "actualizado": formulario.fecha_actualizacion,
                "editable": puede_editar_sci(usuario, emergencia),
                "formulario": formulario,
            })
        emergencia.documentos_sci = documentos
        emergencia.puede_editar_documentos = puede_editar_sci(usuario, emergencia)
    return emergencias

@login_required
def sci211_lista(request):
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied
    contexto = {
        "formularios": formularios_sci_permitidos(request.user),
        "catalogo_sci": CATALOGO_FORMULARIOS_SCI,
        "expedientes": preparar_expedientes_sci(request.user),
    }

    return render(request, "emergencias/sci211/lista.html", contexto)

@login_required
def formulario_sci_catalogo_detalle(request, codigo):
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied
    formulario_catalogo = next(
        (formulario for formulario in CATALOGO_FORMULARIOS_SCI if formulario["codigo"] == codigo),
        None,
    )
    if formulario_catalogo is None:
        raise Http404
    contexto = {
        "formulario_catalogo": formulario_catalogo,
        "emergencia_visualizacion": emergencia_para_visualizar(request.user),
    }

    return render(request, "emergencias/sci211/catalogo_detalle.html", contexto)

@login_required
def formulario_sci_catalogo_visualizar(request, codigo):
    """Muestra la estructura imprimible aun cuando no exista un incidente."""
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied
    esquema = obtener_esquema_catalogo(codigo)
    if esquema is None:
        raise Http404
    cuerpo = SimpleNamespace(nombre="Cuerpos de Bomberos de Cotopaxi")
    estacion = SimpleNamespace(nombre="Estación por asignar", cuerpo_bomberos=cuerpo)
    emergencia = SimpleNamespace(
        pk=None,
        codigo="VISTA-PREVIA",
        tipo_emergencia="Incidente por registrar",
        descripcion="Espacio destinado a la descripción y evaluación inicial del incidente.",
        fecha_reporte=timezone.now(),
        direccion="Ubicación por registrar",
        latitud=None,
        longitud=None,
        estacion_responsable=estacion,
        get_estado_display=lambda: "Sin asociar",
        get_prioridad_display=lambda: "Por definir",
    )
    contexto = {
        "emergencia": emergencia,
        "esquema": esquema,
        "codigo": codigo,
        "formulario_catalogo": next(item for item in CATALOGO_FORMULARIOS_SCI if item["codigo"] == codigo),
        "formulario_generico": None,
        "campos_periodo": [dict(campo, valor="") for campo in campos_periodo(esquema)],
        "secciones": secciones_con_valores(esquema, {}),
        "solo_vista": True,
    }

    return render(request, "emergencias/sci_preview.html", contexto)

@login_required
def formulario_sci_visualizar(request, codigo, emergencia_pk):
    emergencia = get_object_or_404(emergencias_permitidas(request.user), pk=emergencia_pk)
    if not puede_consultar_sci(request.user, emergencia):
        raise PermissionDenied
    bloqueado = redirigir_si_sci_bloqueado(request, emergencia, codigo)
    if bloqueado:
        return bloqueado
    if codigo == "211":
        formulario = FormularioSCI211.objects.filter(emergencia=emergencia).first()
        if formulario:
            return redirect("emergencias:sci211_imprimir", pk=formulario.pk)
    contexto = contexto_documento_sci(request.user, emergencia, codigo)
    contexto["puede_editar"] = puede_editar_sci(request.user, emergencia)
    return render(request, "emergencias/sci_preview.html", contexto)

def periodo_heredado(emergencia, codigo):
    """Lo que ya se escribió del periodo operacional en otro formulario.

    Nueve de los doce formularios piden el mismo periodo: su número, su inicio
    y su fin. Escribirlo veintisiete veces no aporta nada y se presta a que las
    copias no coincidan, que es peor que no tenerlo. Se toma del formulario más
    reciente que lo tenga, y el usuario puede cambiarlo si este periodo es otro.
    """
    heredado = {}
    otros = FormularioSCI.objects.filter(
        emergencia=emergencia
    ).exclude(codigo_sci=codigo).order_by("-fecha_actualizacion", "-pk")
    for formulario in otros:
        for nombre in ("periodo_numero", "periodo_inicio", "periodo_fin"):
            valor = (formulario.datos or {}).get(nombre)
            if valor and nombre not in heredado:
                heredado[nombre] = valor
        if len(heredado) == 3:
            break
    return heredado

def contexto_documento_sci(usuario, emergencia, codigo):
    # El SCI-211 se captura con su modelo propio, de modo que no figura entre
    # los esquemas editables. Mientras la emergencia no tenga uno creado no hay
    # nada a donde redirigir, y esta vista debe mostrar su cuadricula oficial en
    # blanco en lugar de responder que la pagina no existe.
    esquema = obtener_esquema_catalogo(codigo)
    if esquema is None:
        raise Http404
    formulario = FormularioSCI.objects.filter(emergencia=emergencia, codigo_sci=codigo).first()
    datos = formulario.datos if formulario else {}
    en_el_lugar = recursos_en_el_lugar(emergencia, usuario)
    heredado = periodo_heredado(emergencia, codigo)
    return {
        "emergencia": emergencia,
        "esquema": esquema,
        "codigo": codigo,
        "formulario_catalogo": next(item for item in CATALOGO_FORMULARIOS_SCI if item["codigo"] == codigo),
        "formulario_generico": formulario,
        # Un campo vacío se ofrece con lo que ya se escribió en otro formulario
        # de esta emergencia; uno con valor propio no se toca.
        "campos_periodo": [
            dict(campo,
                 valor=datos.get(campo["nombre"])
                 or heredado.get(campo["nombre"], ""),
                 heredado=not datos.get(campo["nombre"])
                 and bool(heredado.get(campo["nombre"])))
            for campo in campos_periodo(esquema)
        ],
        "secciones": secciones_con_valores(esquema, datos),
        "recursos_disponibles": recursos_disponibles_verificados(usuario),
        "recursos_agrupados": recursos_agrupados_para_sci(usuario),
        "recursos_del_lugar": en_el_lugar,
        # El nombre de quien firma se ofrece hecho: lo escribía en cada uno de
        # los doce formularios.
        "preparado_por_sugerido": usuario.get_full_name() or usuario.username,
        "recursos_del_lugar_agrupados": agrupar_recursos(en_el_lugar),
    }

def recursos_disponibles_verificados(usuario):
    """Inventario utilizable, con aviso si la confirmación no es del día.

    Se ofrece todo lo operativo y libre. La confirmación caduca a las 24 horas,
    pero eso se advierte en la etiqueta en vez de esconder la unidad.
    """
    recursos = list(
        recursos_permitidos(usuario).filter(
            activo=True,
            estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
            disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
        ).select_related("estacion", "tipo", "tipo__categoria").order_by(
            "estacion__nombre", "tipo__categoria__nombre", "nombre"
        )
    )
    for recurso in recursos:
        recurso.etiqueta_sci = etiqueta_de_recurso(recurso)
    return recursos

def recursos_en_el_lugar(emergencia, usuario):
    """Recursos que el SCI-211 ya registró en esta emergencia.

    Es el único conjunto que puede figurar como «en el lugar»: nada está en la
    escena si no pasó por el registro de recursos. Ofrecer ahí el inventario
    entero permitía anotar en el plan de acción un carro que seguía en el
    patio.
    """
    formulario = getattr(emergencia, "formulario_sci_211", None)
    if formulario is None:
        return []
    recursos = [
        registro.recurso_inventario
        for registro in formulario.registros.select_related(
            "recurso_inventario__estacion", "recurso_inventario__estacion__cuerpo_bomberos",
            "recurso_inventario__tipo", "recurso_inventario__tipo__categoria",
        ).order_by("orden", "pk")
        if registro.recurso_inventario_id
    ]
    vistos = set()
    unicos = []
    for recurso in recursos:
        if recurso.pk not in vistos:
            vistos.add(recurso.pk)
            recurso.etiqueta_sci = etiqueta_de_recurso(recurso)
            unicos.append(recurso)
    return unicos

def recursos_agrupados_para_sci(usuario):
    """El mismo inventario, repartido en encabezados para el desplegable."""
    return agrupar_recursos(recursos_disponibles_verificados(usuario))

def recursos_solicitados_en(esquema, post_validado, recursos):
    """Recursos que el formulario dejó anotados como «por solicitar»."""
    por_etiqueta = {recurso.etiqueta_sci: recurso for recurso in recursos}
    solicitados = {}
    for seccion in esquema["secciones"]:
        if seccion["tipo"] != "tabla":
            continue
        for columna in seccion["columnas"]:
            if not columna.get("recurso_inventario"):
                continue
            if columna.get("origen", ORIGEN_INVENTARIO) != ORIGEN_INVENTARIO:
                continue
            patron = re.compile(
                rf"^{re.escape(seccion['nombre'])}-\d+-{re.escape(columna['nombre'])}$"
            )
            for clave, valor in post_validado.items():
                if patron.fullmatch(clave) and valor in por_etiqueta:
                    recurso = por_etiqueta[valor]
                    solicitados[recurso.pk] = recurso
    return list(solicitados.values())

def trasladar_solicitudes_al_sci211(request, emergencia, codigo, esquema, post_validado, recursos):
    """Lleva al SCI-211 lo que el plan de acción acaba de solicitar.

    Solo del SCI-202: es el formulario donde se piden recursos. Anotarlos allí
    y no en el registro obligaba a copiarlos a mano de un formulario al otro.
    """
    if codigo != "202":
        return
    solicitados = recursos_solicitados_en(esquema, post_validado, recursos)
    creadas = registrar_solicitud_en_sci211(emergencia, solicitados, request.user)
    if not creadas:
        return
    messages.success(
        request,
        f"{creadas} recurso(s) solicitado(s) quedaron anotados en el SCI-211.",
    )
    formulario_211 = FormularioSCI211.objects.filter(emergencia=emergencia).first()
    if formulario_211 is None:
        return
    despachadas, avisos = desplegar_recursos_del_sci211(formulario_211, request.user)
    if despachadas:
        messages.success(request, f"Se despachó {despachadas} unidad(es).")
    for aviso in avisos:
        messages.warning(request, aviso)

def normalizar_recursos_sci(esquema, post, recursos, en_el_lugar=()):
    """Valida IDs seleccionados y guarda una etiqueta legible en el JSON SCI.

    Cada columna se contrasta contra el conjunto del que dice surtirse. Una
    columna de recursos «en el lugar» que aceptara cualquier identificador del
    inventario dejaría anotar en el plan de acción un carro que sigue en el
    patio, por más que el desplegable no lo ofrezca.
    """
    normalizado = post.copy()
    conjuntos = {
        ORIGEN_INVENTARIO: {
            str(recurso.pk): recurso.etiqueta_sci for recurso in recursos
        },
        ORIGEN_EN_EL_LUGAR: {
            str(recurso.pk): recurso.etiqueta_sci for recurso in en_el_lugar
        },
    }
    for seccion in esquema["secciones"]:
        if seccion["tipo"] != "tabla":
            continue
        for columna in seccion["columnas"]:
            if not columna.get("recurso_inventario"):
                continue
            permitidos = conjuntos[columna.get("origen", ORIGEN_INVENTARIO)]
            patron = re.compile(
                rf"^{re.escape(seccion['nombre'])}-\d+-{re.escape(columna['nombre'])}$"
            )
            for clave in (clave for clave in post if patron.fullmatch(clave)):
                recurso_id = post.get(clave, "")
                if not recurso_id:
                    normalizado[clave] = ""
                elif recurso_id in permitidos:
                    normalizado[clave] = permitidos[recurso_id]
                elif columna.get("origen") == ORIGEN_EN_EL_LUGAR:
                    raise ValidationError(
                        f"«{columna['etiqueta']}» solo admite recursos que el "
                        "SCI-211 haya registrado en esta emergencia."
                    )
                else:
                    raise ValidationError(
                        "El recurso seleccionado ya no pertenece al inventario "
                        "disponible de su ámbito."
                    )
    return normalizado

@login_required
def formulario_sci_editar(request, codigo, emergencia_pk):
    emergencia = get_object_or_404(emergencias_permitidas(request.user), pk=emergencia_pk)
    bloqueado = redirigir_si_sci_bloqueado(request, emergencia, codigo)
    if bloqueado:
        return bloqueado
    if codigo == "211":
        formulario = FormularioSCI211.objects.filter(emergencia=emergencia).first()
        if formulario is None:
            formulario = crear_sci211_desde_emergencia(emergencia, request.user)
        return redirect("emergencias:sci211_editar", pk=formulario.pk)
    esquema = obtener_esquema(codigo)
    if esquema is None:
        raise Http404
    if not puede_editar_sci(request.user, emergencia):
        raise PermissionDenied
    formulario, _ = FormularioSCI.objects.get_or_create(
        emergencia=emergencia, codigo_sci=codigo,
        defaults={"creado_por": request.user, "modificado_por": request.user},
    )
    if not formulario.es_editable:
        messages.info(request, f"El formulario SCI-{codigo} está finalizado y es de solo lectura.")
        return redirect("emergencias:sci_visualizar", codigo=codigo, emergencia_pk=emergencia.pk)
    if request.method == "POST":
        recursos = recursos_disponibles_verificados(request.user)
        try:
            post_validado = normalizar_recursos_sci(
                esquema, request.POST, recursos,
                recursos_en_el_lugar(emergencia, request.user),
            )
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            formulario.datos = extraer_datos(esquema, post_validado)
            formulario.preparado_por = request.POST.get("preparado_por", "").strip()[:150]
            formulario.modificado_por = request.user
            formulario.save()
            messages.success(request, f"Formulario SCI-{codigo} guardado correctamente.")
            trasladar_solicitudes_al_sci211(
                request, emergencia, codigo, esquema, post_validado, recursos
            )
            return redirect(
                reverse("emergencias:detalle", args=[emergencia.pk]) + "#formularios-sci"
            )
    contexto = contexto_documento_sci(request.user, emergencia, codigo)
    contexto["es_horizontal"] = esquema["orientacion"] == "horizontal"
    return render(request, "emergencias/sci_editar.html", contexto)

@login_required
def formulario_sci_finalizar(request, codigo, emergencia_pk):
    emergencia = get_object_or_404(emergencias_permitidas(request.user), pk=emergencia_pk)
    bloqueado = redirigir_si_sci_bloqueado(request, emergencia, codigo)
    if bloqueado:
        return bloqueado
    if not puede_editar_sci(request.user, emergencia) or obtener_esquema(codigo) is None:
        raise PermissionDenied
    formulario = get_object_or_404(FormularioSCI, emergencia=emergencia, codigo_sci=codigo)
    if request.method == "POST":
        try:
            finalizar_sci(formulario, request.user)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, f"Formulario SCI-{codigo} finalizado. Ahora es de solo lectura.")
    return redirect(
        reverse("emergencias:detalle", args=[emergencia.pk]) + "#formularios-sci"
    )

@login_required
@require_POST
def sci211_crear(request, emergencia_pk):
    emergencia = get_object_or_404(emergencias_permitidas(request.user), pk=emergencia_pk)
    bloqueado = redirigir_si_sci_bloqueado(request, emergencia, "211")
    if bloqueado:
        return bloqueado
    if not puede_editar_sci(request.user, emergencia):
        raise PermissionDenied
    formulario = FormularioSCI211.objects.filter(emergencia=emergencia).first()
    if formulario is None:
        formulario = crear_sci211_desde_emergencia(emergencia, request.user)
        messages.success(request, "Formulario SCI-211 creado como borrador.")
    return redirect("emergencias:sci211_editar" if formulario.es_editable else "emergencias:sci211_detalle", pk=formulario.pk)

@login_required
def sci211_editar(request, pk):
    formulario = get_object_or_404(formularios_sci_permitidos(request.user), pk=pk)
    bloqueado = redirigir_si_sci_bloqueado(
        request, formulario.emergencia, "211"
    )
    if bloqueado:
        return bloqueado
    if not puede_editar_sci(request.user, formulario.emergencia):
        raise PermissionDenied
    if not formulario.es_editable:
        messages.info(request, "El formulario finalizado es de solo lectura.")
        return redirect("emergencias:sci211_detalle", pk=pk)
    cabecera = FormularioSCI211Form(request.POST or None, instance=formulario)
    registros = RegistroRecursoSCI211FormSet(
        request.POST or None, instance=formulario,
        form_kwargs={"usuario": request.user},
    )
    if request.method == "POST" and cabecera.is_valid() and registros.is_valid():
        cabecera.save(commit=False)
        formulario.modificado_por = request.user
        formulario.save()
        instancias = registros.save(commit=False)
        for borrado in registros.deleted_objects:
            borrado.delete()
        for orden, instancia in enumerate(instancias, start=1):
            instancia.orden = orden
            instancia.save()
        # Anotar una unidad en el SCI-211 es la decisión de enviarla, así que el
        # despacho ocurre aquí y no en una pantalla aparte.
        despachadas, avisos = desplegar_recursos_del_sci211(formulario, request.user)
        if despachadas:
            messages.success(
                request,
                f"Se despachó {despachadas} unidad(es) desde el SCI-211."
            )
        for aviso in avisos:
            messages.warning(request, aviso)
        accion = request.POST.get("accion")
        if accion == "finalizar":
            messages.success(request, "Borrador guardado. Confirme para finalizar.")
            return redirect("emergencias:sci211_finalizar", pk=pk)
        if accion == "guardar_recurso":
            # El botón de cada tarjeta guarda de verdad y devuelve al editor con
            # lo ya anotado plegado, para seguir añadiendo recursos. Antes solo
            # minimizaba la tarjeta: quien lo pulsaba y cerraba la pestaña
            # perdía el recurso creyendo haberlo guardado.
            messages.success(request, "Recurso guardado en el SCI-211.")
            return redirect(
                reverse("emergencias:sci211_editar", args=[pk]) + "?plegar=1"
            )
        messages.success(request, "Borrador SCI-211 guardado.")
        return redirect(
            reverse("emergencias:detalle", args=[formulario.emergencia_id]) + "#formularios-sci"
        )
    # Si el inventario no ofrece nada, la lista sale con una sola opción vacía y
    # no se entiende por qué. Conviene decirlo antes de que alguien lo busque.
    hay_recursos = registros.forms[0].fields["recurso_inventario"].queryset.exists()
    contexto = {
        "formulario_sci": formulario, "cabecera": cabecera, "registros": registros,
        "sin_recursos_disponibles": not hay_recursos,
        "plegar_guardados": request.GET.get("plegar") == "1",
    }

    return render(request, "emergencias/sci211/formulario.html", contexto)

@login_required
def sci211_detalle(request, pk):
    formulario = get_object_or_404(formularios_sci_permitidos(request.user), pk=pk)
    bloqueado = redirigir_si_sci_bloqueado(
        request, formulario.emergencia, "211"
    )
    if bloqueado:
        return bloqueado
    contexto = {
        "formulario_sci": formulario,
        "puede_editar": formulario.es_editable and puede_editar_sci(request.user, formulario.emergencia),
    }

    return render(request, "emergencias/sci211/detalle.html", contexto)

@login_required
def sci211_finalizar(request, pk):
    formulario = get_object_or_404(formularios_sci_permitidos(request.user), pk=pk)
    bloqueado = redirigir_si_sci_bloqueado(
        request, formulario.emergencia, "211"
    )
    if bloqueado:
        return bloqueado
    if not puede_editar_sci(request.user, formulario.emergencia) or not formulario.es_editable:
        raise PermissionDenied
    if request.method == "POST":
        # También se despacha aquí. A esta pantalla se puede llegar sin haber
        # guardado el editor —desde la ficha de la emergencia o por la propia
        # dirección—, y sin este paso la unidad quedaba anotada en el formulario
        # pero nunca salía. El servicio ignora lo ya despachado.
        despachadas, avisos = desplegar_recursos_del_sci211(formulario, request.user)
        for aviso in avisos:
            messages.warning(request, aviso)
        try:
            finalizar_sci211(formulario, request.user)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
            return redirect("emergencias:sci211_editar", pk=pk)
        if despachadas:
            messages.success(
                request, f"Se despachó {despachadas} unidad(es) desde el SCI-211."
            )
        messages.success(request, "Formulario SCI-211 finalizado. Ahora es de solo lectura.")
        return redirect(
            reverse("emergencias:detalle", args=[formulario.emergencia_id]) + "#formularios-sci"
        )
    contexto = {"formulario_sci": formulario}

    return render(request, "emergencias/sci211/finalizar.html", contexto)

@login_required
def sci211_imprimir(request, pk):
    formulario = get_object_or_404(formularios_sci_permitidos(request.user), pk=pk)
    bloqueado = redirigir_si_sci_bloqueado(
        request, formulario.emergencia, "211"
    )
    if bloqueado:
        return bloqueado
    contexto = {
        "formulario": formulario,
        "filas_vacias": range(max(0, 24 - formulario.registros.count())),
        # La vista imprimible es también donde se descubre que el formulario
        # quedó a medias, así que desde aquí se vuelve a llenarlo. El de los
        # formularios genéricos ya ofrecía este camino; el SCI-211 no.
        "puede_editar": (
            puede_editar_sci(request.user, formulario.emergencia)
            and formulario.es_editable
        ),
    }

    return render(request, "emergencias/sci211/pdf.html", contexto)

# ==========================================
# MÓDULO: SEGUIMIENTO GPS
# ==========================================

def despliegues_permitidos(usuario):
    return DespliegueUnidad.objects.filter(
        estacion_procedencia__in=estaciones_permitidas(usuario)
    ).select_related("emergencia", "unidad", "estacion_procedencia")

@login_required
@ensure_csrf_cookie
def transmitir_gps(request, pk):
    # El chofer llega aquí por su propia unidad; el resto, por su estación y
    # solo si puede gestionarla: esta consola no es de consulta.
    despliegue = despliegue_alcanzable(request.user, pk, exigir_gestion=True)
    if not despliegue.activo or not despliegue.emergencia.admite_despliegues:
        raise PermissionDenied("El despliegue no admite transmisión GPS.")
    contexto = {"despliegue": despliegue}

    return render(request, "emergencias/transmitir_gps.html", contexto)

def despliegue_alcanzable(usuario, pk, exigir_gestion=False):
    """Devuelve el despliegue si el usuario lo conduce o alcanza su estación.

    ``exigir_gestion`` reproduce la barrera de las pantallas que no son de
    consulta: un operador de consulta ve la última posición de una unidad, pero
    no abre la consola desde la que se transmite.
    """
    despliegue = DespliegueUnidad.objects.filter(pk=pk).select_related(
        "unidad", "emergencia"
    ).first()
    if despliegue is not None and conduce_el_despliegue(usuario, despliegue):
        return despliegue
    if exigir_gestion and not puede_gestionar_emergencias(usuario):
        raise PermissionDenied
    return get_object_or_404(despliegues_permitidos(usuario), pk=pk)

def error_json(mensaje, estado, codigo):
    return JsonResponse({"error": mensaje, "codigo": codigo}, status=estado)

@require_POST
def detener_transmision_gps(request, pk):
    """Apaga el seguimiento en vivo de una unidad y la retira del mapa."""
    if not request.user.is_authenticated:
        return error_json("Autenticación requerida.", 401, "no_autenticado")
    if not (puede_gestionar_emergencias(request.user) or es_chofer(request.user)):
        return error_json("No tiene autorización sobre esta unidad.", 403, "sin_autorizacion")
    despliegue = despliegue_alcanzable(request.user, pk)
    try:
        detener_transmision(despliegue, request.user)
    except ValidationError as error:
        return error_json(" ".join(error.messages), 400, "no_valido")
    return JsonResponse({"transmitiendo": False})

@require_POST
def registrar_posicion(request, pk):
    if not request.user.is_authenticated:
        return error_json("Autenticación requerida.", 401, "no_autenticado")
    if request.content_type != "application/json":
        return error_json("El contenido debe ser JSON.", 415, "contenido_no_valido")
    if not (puede_gestionar_emergencias(request.user) or es_chofer(request.user)):
        return error_json("No tiene autorización para reportar posiciones.", 403, "sin_autorizacion")
    try:
        datos = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return error_json("El cuerpo JSON no es válido.", 400, "json_no_valido")
    if not isinstance(datos, dict):
        return error_json("El cuerpo JSON debe ser un objeto.", 400, "datos_no_validos")
    despliegue = despliegue_alcanzable(request.user, pk)
    fecha_dispositivo = datos.get("fecha_dispositivo")
    if fecha_dispositivo:
        fecha_dispositivo = parse_datetime(str(fecha_dispositivo))
        if fecha_dispositivo is None:
            return error_json("La fecha del dispositivo no es válida.", 400, "datos_no_validos")
        if timezone.is_naive(fecha_dispositivo):
            fecha_dispositivo = timezone.make_aware(fecha_dispositivo)
    try:
        posicion = registrar_posicion_unidad(
            despliegue, request.user,
            latitud=datos.get("latitud"), longitud=datos.get("longitud"),
            precision=datos.get("precision"), velocidad=datos.get("velocidad"),
            rumbo=datos.get("rumbo"), altitud=datos.get("altitud"),
            fecha_dispositivo=fecha_dispositivo,
        )
    except ValidationError as error:
        mensaje = next(iter(error.messages), "Los datos enviados no son válidos.")
        codigo = "despliegue_inactivo" if "activo" in mensaje or "seguimiento" in mensaje else "datos_no_validos"
        return error_json(mensaje, 409 if codigo == "despliegue_inactivo" else 400, codigo)
    return JsonResponse({
        "id": posicion.pk,
        "fecha_recepcion": posicion.fecha_recepcion.isoformat(),
        "mensaje": "Posición recibida.",
    }, status=201)

@require_GET
def ultima_posicion(request, pk):
    if not request.user.is_authenticated:
        return error_json("Autenticación requerida.", 401, "no_autenticado")
    if not puede_consultar_emergencias(request.user):
        return error_json("No tiene autorización para consultar el despliegue.", 403, "sin_autorizacion")
    despliegue = despliegue_alcanzable(request.user, pk)
    posicion = despliegue.posiciones.order_by("-fecha_recepcion", "-pk").first()
    if posicion is None:
        return JsonResponse({"disponible": False, "mensaje": "Todavía no existen posiciones."})
    return JsonResponse({
        "disponible": True,
        "latitud": posicion.ubicacion.y, "longitud": posicion.ubicacion.x,
        "precision": str(posicion.precision) if posicion.precision is not None else None,
        "velocidad": str(posicion.velocidad) if posicion.velocidad is not None else None,
        "rumbo": str(posicion.rumbo) if posicion.rumbo is not None else None,
        "fecha_dispositivo": posicion.fecha_dispositivo.isoformat() if posicion.fecha_dispositivo else None,
        "fecha_recepcion": posicion.fecha_recepcion.isoformat(),
        "estado_despliegue": despliegue.estado,
    })


# ==========================================
# MÓDULO: PANTALLA DEL CHOFER
# ==========================================

@login_required
def mi_unidad(request):
    """Única pantalla del chofer: la unidad que conduce y su emergencia.

    Se resuelve por los despliegues que tiene asignados y no por su estación,
    de modo que solo alcanza lo suyo aunque comparta institución con el resto.
    """
    if not es_chofer(request.user):
        raise PermissionDenied

    despliegues = list(despliegues_asignados(request.user))
    contexto = {
        "despliegues": despliegues,
        "sin_asignacion": not despliegues,
    }

    return render(request, "emergencias/mi_unidad.html", contexto)

@login_required
def mi_historial(request):
    """Recorridos que el chofer ya cerró, para consultarlos después."""
    if not es_chofer(request.user):
        raise PermissionDenied

    despliegues = list(
        despliegues_conducidos(request.user)
        .exclude(estado__in=DespliegueUnidad.ESTADOS_ACTIVOS)
        .annotate(puntos=Count("posiciones"))
        .order_by("-fecha_asignacion", "-pk")[:50]
    )
    contexto = {"despliegues": despliegues, "sin_historial": not despliegues}

    return render(request, "emergencias/mi_historial.html", contexto)

@login_required
def mi_recorrido(request, pk):
    """Dibuja sobre el mapa el recorrido que esta unidad registró."""
    if not es_chofer(request.user):
        raise PermissionDenied
    despliegue = get_object_or_404(despliegues_conducidos(request.user), pk=pk)
    contexto = {
        "despliegue": despliegue,
        "puntos": despliegue.posiciones.count(),
    }

    return render(request, "emergencias/mi_recorrido.html", contexto)
