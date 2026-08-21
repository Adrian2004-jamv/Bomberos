import base64
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .esquemas_sci import TABLA
from .models import FormularioSCI, FormularioSCI211, RegistroRecursoSCI211


def _nombre_usuario(usuario):
    return usuario.get_full_name() or usuario.username


@transaction.atomic
def crear_sci211_desde_emergencia(emergencia, usuario):
    formulario = FormularioSCI211.objects.create(
        emergencia=emergencia,
        codigo=f"SCI-211-{emergencia.codigo}",
        punto_registro="Puesto de Comando",
        registrador_1=_nombre_usuario(usuario),
        creado_por=usuario,
        modificado_por=usuario,
    )
    for orden, despliegue in enumerate(emergencia.despliegues.select_related(
        "unidad__tipo__categoria", "estacion_procedencia__cuerpo_bomberos", "despachado_por"
    ), start=1):
        unidad = despliegue.unidad
        estado = RegistroRecursoSCI211.EstadoRecurso.DISPONIBLE
        if unidad.estado_operativo == "fuera_servicio":
            estado = RegistroRecursoSCI211.EstadoRecurso.FUERA_SERVICIO
        elif unidad.disponibilidad == "no_disponible":
            estado = RegistroRecursoSCI211.EstadoRecurso.NO_DISPONIBLE
        RegistroRecursoSCI211.objects.create(
            formulario=formulario, despliegue=despliegue, orden=orden,
            solicitado_por=_nombre_usuario(despliegue.despachado_por),
            fecha_hora_solicitud=despliegue.fecha_asignacion,
            clase_recurso=unidad.tipo.categoria.nombre,
            tipo_recurso=unidad.tipo.nombre,
            fecha_hora_arribo=despliegue.fecha_llegada,
            institucion_procedencia=despliegue.estacion_procedencia.cuerpo_bomberos.nombre,
            matricula_identificacion=unidad.codigo_interno,
            numero_personas=1,
            estado_recurso=estado,
            asignado_a=emergencia.direccion if estado == "disponible" else "",
            desmovilizado_por=_nombre_usuario(despliegue.despachado_por) if despliegue.fecha_retorno else "",
            fecha_hora_desmovilizacion=despliegue.fecha_retorno,
            observaciones=despliegue.observaciones,
        )
    return formulario


@transaction.atomic
def finalizar_sci211(formulario, usuario):
    actual = FormularioSCI211.objects.select_for_update().select_related(
        "emergencia__estacion_responsable__cuerpo_bomberos"
    ).get(pk=formulario.pk)
    if not actual.es_editable:
        raise ValidationError("El formulario SCI-211 ya está finalizado.")
    registros = list(actual.registros.all())
    if not registros:
        raise ValidationError("Debe registrar al menos un recurso antes de finalizar.")
    actual.full_clean()
    for registro in registros:
        registro.full_clean()
    emergencia = actual.emergencia
    estacion = emergencia.estacion_responsable
    actual.emergencia_codigo_emitido = emergencia.codigo
    actual.incidente_nombre_emitido = emergencia.tipo_emergencia
    actual.incidente_fecha_emitida = emergencia.fecha_reporte
    actual.incidente_direccion_emitida = emergencia.direccion
    actual.institucion_emitida = estacion.cuerpo_bomberos.nombre
    actual.estacion_emitida = estacion.nombre
    if emergencia.latitud is not None and emergencia.longitud is not None:
        actual.coordenadas_emitidas = f"{emergencia.latitud}, {emergencia.longitud}"
    actual.estado = FormularioSCI211.Estado.FINALIZADO
    actual.finalizado_por = usuario
    actual.modificado_por = usuario
    actual.fecha_finalizacion = timezone.now()
    actual.save()
    return actual


def generar_pdf_sci211(formulario):
    try:
        from weasyprint import HTML, default_url_fetcher
    except (ImportError, OSError) as error:
        raise RuntimeError("WeasyPrint no está disponible en este entorno.") from error
    logo = Path(settings.BASE_DIR) / "static" / "emergencias" / "img" / "sci-logo.png"
    contexto = {
        "formulario": formulario,
        "filas_vacias": range(max(0, 24 - formulario.registros.count())),
        "logo_sci_data_uri": "data:image/png;base64," + base64.b64encode(logo.read_bytes()).decode("ascii"),
    }
    html = render_to_string("emergencias/sci211/pdf.html", contexto)
    salida = BytesIO()

    def bloquear_recurso_externo(url, timeout=10, ssl_context=None):
        if url.startswith("data:image/png;base64,"):
            return default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)
        raise ValueError(f"El PDF SCI-211 no admite recursos externos: {url!r}")

    HTML(string=html, url_fetcher=bloquear_recurso_externo).write_pdf(salida)
    return salida.getvalue()


@transaction.atomic
def finalizar_sci(formulario, usuario):
    """Bloquea un formulario SCI genérico tras verificar que tenga contenido."""
    actual = FormularioSCI.objects.select_for_update().get(pk=formulario.pk)
    if not actual.es_editable:
        raise ValidationError(f"El formulario SCI-{actual.codigo_sci} ya está finalizado.")
    if not _tiene_contenido(actual.datos):
        raise ValidationError("Complete al menos un campo antes de finalizar el formulario.")
    actual.estado = FormularioSCI.Estado.FINALIZADO
    actual.finalizado_por = usuario
    actual.modificado_por = usuario
    actual.fecha_finalizacion = timezone.now()
    actual.save()
    return actual


def _tiene_contenido(datos):
    for valor in (datos or {}).values():
        if isinstance(valor, list):
            if any(any(celda for celda in fila.values()) for fila in valor if isinstance(fila, dict)):
                return True
        elif str(valor or "").strip():
            return True
    return False


def generar_pdf_sci(contexto):
    """Genera el PDF de un formulario SCI genérico a partir del contexto del documento."""
    try:
        from weasyprint import HTML, default_url_fetcher
    except (ImportError, OSError) as error:
        raise RuntimeError("WeasyPrint no está disponible en este entorno.") from error
    logo = Path(settings.BASE_DIR) / "static" / "emergencias" / "img" / "sci-logo.png"
    contexto = dict(
        contexto,
        modo_pdf=True,
        logo_sci_data_uri="data:image/png;base64," + base64.b64encode(logo.read_bytes()).decode("ascii"),
    )
    html = render_to_string("emergencias/sci_preview.html", contexto)
    salida = BytesIO()

    def bloquear_recurso_externo(url, timeout=10, ssl_context=None):
        if url.startswith("data:image/png;base64,"):
            return default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)
        raise ValueError(f"El PDF SCI no admite recursos externos: {url!r}")

    HTML(string=html, url_fetcher=bloquear_recurso_externo).write_pdf(salida)
    return salida.getvalue()
