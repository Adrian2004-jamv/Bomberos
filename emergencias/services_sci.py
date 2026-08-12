from io import BytesIO

from django.core.exceptions import ValidationError
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import FormularioSCI211, RegistroRecursoSCI211


def _nombre_usuario(usuario):
    return usuario.get_full_name() or usuario.username


@transaction.atomic
def crear_sci211_desde_emergencia(emergencia, usuario):
    formulario = FormularioSCI211.objects.create(
        emergencia=emergencia,
        codigo=f"SCI-211-{emergencia.codigo}",
        punto_registro="Puesto de Comando",
        preparado_por_nombre=_nombre_usuario(usuario),
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
            ubicacion_recurso=emergencia.direccion if estado == "disponible" else "",
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
        from weasyprint import CSS, HTML
    except (ImportError, OSError) as error:
        raise RuntimeError("WeasyPrint no está disponible en este entorno.") from error
    html = render_to_string("emergencias/sci211/pdf.html", {"formulario": formulario})
    salida = BytesIO()
    # No se define base_url: se bloquean accesos a archivos y URLs externas.
    HTML(string=html).write_pdf(salida, stylesheets=[CSS(string="@page { size: A4 landscape; margin: 10mm; }")])
    return salida.getvalue()
