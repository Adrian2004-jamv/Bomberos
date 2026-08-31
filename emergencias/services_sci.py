from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .esquemas_sci import TABLA
from .models import FormularioSCI, FormularioSCI211, RegistroRecursoSCI211

def nombre_usuario(usuario):
    return usuario.get_full_name() or usuario.username

@transaction.atomic
def crear_sci211_desde_emergencia(emergencia, usuario):
    formulario = FormularioSCI211.objects.create(
        emergencia=emergencia,
        codigo=f"SCI-211-{emergencia.codigo}",
        punto_registro="Puesto de Comando",
        registrador_1=nombre_usuario(usuario),
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
            solicitado_por=nombre_usuario(despliegue.despachado_por),
            fecha_hora_solicitud=despliegue.fecha_asignacion,
            clase_recurso=unidad.tipo.categoria.nombre,
            tipo_recurso=unidad.tipo.nombre,
            fecha_hora_arribo=despliegue.fecha_llegada,
            institucion_procedencia=despliegue.estacion_procedencia.cuerpo_bomberos.nombre,
            matricula_identificacion=unidad.codigo_interno,
            numero_personas=1,
            estado_recurso=estado,
            asignado_a=emergencia.direccion if estado == "disponible" else "",
            desmovilizado_por=nombre_usuario(despliegue.despachado_por) if despliegue.fecha_retorno else "",
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

@transaction.atomic
def finalizar_sci(formulario, usuario):
    """Bloquea un formulario SCI genérico tras verificar que tenga contenido."""
    actual = FormularioSCI.objects.select_for_update().get(pk=formulario.pk)
    if not actual.es_editable:
        raise ValidationError(f"El formulario SCI-{actual.codigo_sci} ya está finalizado.")
    if not tiene_contenido(actual.datos):
        raise ValidationError("Complete al menos un campo antes de finalizar el formulario.")
    actual.estado = FormularioSCI.Estado.FINALIZADO
    actual.finalizado_por = usuario
    actual.modificado_por = usuario
    actual.fecha_finalizacion = timezone.now()
    actual.save()
    return actual

def tiene_contenido(datos):
    for valor in (datos or {}).values():
        if isinstance(valor, list):
            if any(any(celda for celda in fila.values()) for fila in valor if isinstance(fila, dict)):
                return True
        elif str(valor or "").strip():
            return True
    return False

@transaction.atomic
def desplegar_recursos_del_sci211(formulario, usuario):
    """Despacha las unidades que el SCI-211 registra y aún no están desplegadas.

    El SCI-211 es la fuente maestra de recursos del incidente, de modo que
    anotar una unidad allí es la decisión de enviarla: obligar además a
    despacharla por otra pantalla duplicaba el trabajo y dejaba las dos vistas
    contradiciéndose.

    Solo se despachan las unidades desplegables. El formulario también registra
    equipos —un ERA, por ejemplo—, que no salen como unidad y no generan
    despliegue.

    Devuelve ``(despachadas, avisos)``. Un recurso que no se pueda despachar no
    detiene al resto ni impide guardar el formulario: se informa y el usuario
    decide.
    """
    from .models import DespliegueUnidad
    from .services import desplegar_unidad

    despachadas = 0
    avisos = []
    registros = formulario.registros.select_related(
        "recurso_inventario__tipo", "despliegue"
    ).filter(recurso_inventario__isnull=False, despliegue__isnull=True)

    for registro in registros:
        recurso = registro.recurso_inventario
        if not recurso.tipo.es_unidad_desplegable:
            continue
        # Si la unidad ya está atendiendo esta misma emergencia, se enlaza en
        # lugar de intentar un despacho que la restricción rechazaría.
        existente = DespliegueUnidad.objects.filter(
            emergencia=formulario.emergencia, unidad=recurso,
            estado__in=DespliegueUnidad.ESTADOS_ACTIVOS,
        ).first()
        if existente is not None:
            registro.despliegue = existente
            registro.save(update_fields=["despliegue"])
            sincronizar_responsable(registro, existente)
            continue
        try:
            despliegue = desplegar_unidad(
                formulario.emergencia, recurso, usuario,
                observaciones=f"Despacho registrado en el {formulario.codigo}.",
            )
        except ValidationError as error:
            avisos.append(
                f"No se pudo despachar {recurso.codigo_interno}: "
                f"{' '.join(error.messages)}"
            )
            continue
        registro.despliegue = despliegue
        registro.save(update_fields=["despliegue"])
        sincronizar_responsable(registro, despliegue)
        despachadas += 1

    # Un recurso escrito a mano queda en el papel y no sale nunca. Antes eso
    # ocurría en silencio y la emergencia aparecía sin unidades sin explicar
    # por qué; conviene decirlo en el momento de guardar.
    a_mano = formulario.registros.filter(
        recurso_inventario__isnull=True, despliegue__isnull=True
    ).count()
    if a_mano:
        avisos.append(
            f"{a_mano} recurso(s) se anotaron a mano y no generan despliegue. "
            "Elíjalos de la lista del inventario para que la unidad salga."
        )

    return despachadas, avisos


def sincronizar_responsable(registro, despliegue):
    """Lleva al despliegue el chofer que el SCI-211 asignó a la unidad.

    El formulario es donde se decide quién va en la unidad; el despliegue
    necesita saberlo porque de ahí cuelga el permiso para transmitir la
    ubicación. Se copia en cada guardado para que un cambio de conductor a
    mitad de la operación llegue también al despliegue.
    """
    if registro.responsable_unidad_id == despliegue.responsable_unidad_id:
        return
    despliegue.responsable_unidad_id = registro.responsable_unidad_id
    despliegue.save(update_fields=["responsable_unidad"])
