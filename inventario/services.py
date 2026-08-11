from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import HistorialEstadoRecurso, Recurso


@transaction.atomic
def actualizar_estado_recurso(
    recurso,
    nuevo_estado_operativo,
    nueva_disponibilidad,
    usuario_responsable,
    motivo,
    observaciones="",
):
    """Actualiza el recurso y registra su historial en una única transacción."""
    Usuario = get_user_model()

    if (
        not isinstance(usuario_responsable, Usuario)
        or usuario_responsable.pk is None
        or not Usuario.objects.filter(pk=usuario_responsable.pk).exists()
    ):
        raise ValidationError("El usuario responsable no existe.")

    if nuevo_estado_operativo not in Recurso.EstadoOperativo.values:
        raise ValidationError({"estado_operativo": "El estado operativo no es válido."})

    if nueva_disponibilidad not in Recurso.Disponibilidad.values:
        raise ValidationError({"disponibilidad": "La disponibilidad no es válida."})

    if not motivo or not motivo.strip():
        raise ValidationError({"motivo": "Debe indicar el motivo del cambio."})

    if not isinstance(recurso, Recurso) or recurso.pk is None:
        raise ValidationError("El recurso no existe.")

    try:
        recurso_actual = Recurso.objects.select_for_update().get(pk=recurso.pk)
    except Recurso.DoesNotExist as error:
        raise ValidationError("El recurso no existe.") from error

    estado_anterior = recurso_actual.estado_operativo
    disponibilidad_anterior = recurso_actual.disponibilidad

    if (
        estado_anterior == nuevo_estado_operativo
        and disponibilidad_anterior == nueva_disponibilidad
    ):
        return recurso_actual, None

    recurso_actual.estado_operativo = nuevo_estado_operativo
    recurso_actual.disponibilidad = nueva_disponibilidad
    recurso_actual.save(
        update_fields=("estado_operativo", "disponibilidad", "fecha_actualizacion")
    )

    historial = HistorialEstadoRecurso.objects.create(
        recurso=recurso_actual,
        estado_anterior=estado_anterior,
        estado_nuevo=nuevo_estado_operativo,
        disponibilidad_anterior=disponibilidad_anterior,
        disponibilidad_nueva=nueva_disponibilidad,
        motivo=motivo.strip(),
        observaciones=observaciones,
        registrado_por=usuario_responsable,
    )

    return recurso_actual, historial
