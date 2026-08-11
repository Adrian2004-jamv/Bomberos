from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from instituciones.models import Estacion
from inventario.models import Recurso

from .models import (
    CalificacionPersonal,
    EvaluacionCapacidadEstacion,
    PersonalOperativo,
    TipoCapacidadOperativa,
)


JERARQUIA_NIVELES = {
    CalificacionPersonal.Nivel.BASICO: 1,
    CalificacionPersonal.Nivel.INTERMEDIO: 2,
    CalificacionPersonal.Nivel.AVANZADO: 3,
    CalificacionPersonal.Nivel.INSTRUCTOR: 4,
}


def _validar_objetos(estacion, capacidad, usuario_evaluador):
    if (
        not isinstance(estacion, Estacion)
        or estacion.pk is None
        or not Estacion.objects.filter(pk=estacion.pk).exists()
    ):
        raise ValidationError("La estación no existe.")

    if (
        not isinstance(capacidad, TipoCapacidadOperativa)
        or capacidad.pk is None
        or not TipoCapacidadOperativa.objects.filter(pk=capacidad.pk).exists()
    ):
        raise ValidationError("El tipo de capacidad no existe.")

    if usuario_evaluador is not None:
        Usuario = get_user_model()
        if (
            not isinstance(usuario_evaluador, Usuario)
            or usuario_evaluador.pk is None
            or not Usuario.objects.filter(pk=usuario_evaluador.pk).exists()
        ):
            raise ValidationError("El usuario evaluador no existe.")


@transaction.atomic
def evaluar_capacidad_estacion(
    estacion,
    tipo_capacidad,
    usuario_evaluador=None,
    observaciones="",
):
    """Evalúa una capacidad sin modificar recursos, personal ni calificaciones.

    Cada requisito aporta una cobertura de 0 a 1 calculada como
    ``min(disponible / requerido, 1)``. El porcentaje es el promedio de todas
    las coberturas, incluidas las opcionales, multiplicado por 100.
    """
    _validar_objetos(estacion, tipo_capacidad, usuario_evaluador)

    requisitos_recursos = list(
        tipo_capacidad.requisitos_recursos.select_related("tipo_recurso").all()
    )
    requisitos_personal = list(
        tipo_capacidad.requisitos_personal.select_related("especialidad").all()
    )
    if not requisitos_recursos and not requisitos_personal:
        raise ValidationError("La capacidad no tiene requisitos configurados.")

    detalle_recursos = []
    detalle_personal = []
    coberturas = []
    coberturas_obligatorias = []

    for requisito in requisitos_recursos:
        cantidad_disponible = Recurso.objects.filter(
            estacion=estacion,
            tipo=requisito.tipo_recurso,
            activo=True,
            estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
            disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
        ).count()
        cobertura = min(
            Decimal(cantidad_disponible) / Decimal(requisito.cantidad_minima),
            Decimal("1"),
        )
        detalle_recursos.append(
            {
                "requisito_id": requisito.pk,
                "tipo_recurso_id": requisito.tipo_recurso_id,
                "nombre": requisito.tipo_recurso.nombre,
                "cantidad_requerida": requisito.cantidad_minima,
                "cantidad_disponible": cantidad_disponible,
                "obligatorio": requisito.obligatorio,
                "cumplimiento": cantidad_disponible >= requisito.cantidad_minima,
                "faltante": max(requisito.cantidad_minima - cantidad_disponible, 0),
            }
        )
        coberturas.append(cobertura)
        if requisito.obligatorio:
            coberturas_obligatorias.append(cobertura)

    hoy = timezone.localdate()
    for requisito in requisitos_personal:
        nivel_requerido = JERARQUIA_NIVELES[requisito.nivel_minimo]
        niveles_aceptados = [
            nivel
            for nivel, jerarquia in JERARQUIA_NIVELES.items()
            if jerarquia >= nivel_requerido
        ]
        cantidad_disponible = (
            PersonalOperativo.objects.filter(
                Q(calificaciones__fecha_vencimiento__isnull=True)
                | Q(calificaciones__fecha_vencimiento__gte=hoy),
                estacion=estacion,
                activo=True,
                disponibilidad=PersonalOperativo.Disponibilidad.DISPONIBLE,
                calificaciones__especialidad=requisito.especialidad,
                calificaciones__activo=True,
                calificaciones__nivel__in=niveles_aceptados,
            )
            .distinct()
            .count()
        )
        cobertura = min(
            Decimal(cantidad_disponible) / Decimal(requisito.cantidad_minima),
            Decimal("1"),
        )
        detalle_personal.append(
            {
                "requisito_id": requisito.pk,
                "especialidad_id": requisito.especialidad_id,
                "nombre": requisito.especialidad.nombre,
                "nivel_minimo": requisito.nivel_minimo,
                "cantidad_requerida": requisito.cantidad_minima,
                "cantidad_disponible": cantidad_disponible,
                "obligatorio": requisito.obligatorio,
                "cumplimiento": cantidad_disponible >= requisito.cantidad_minima,
                "faltante": max(requisito.cantidad_minima - cantidad_disponible, 0),
            }
        )
        coberturas.append(cobertura)
        if requisito.obligatorio:
            coberturas_obligatorias.append(cobertura)

    porcentaje = (
        (sum(coberturas, Decimal("0")) / Decimal(len(coberturas))) * Decimal("100")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    porcentaje = min(max(porcentaje, Decimal("0")), Decimal("100"))

    if all(cobertura == Decimal("1") for cobertura in coberturas_obligatorias):
        estado = EvaluacionCapacidadEstacion.Estado.CUMPLE
    elif any(cobertura > Decimal("0") for cobertura in coberturas_obligatorias):
        estado = EvaluacionCapacidadEstacion.Estado.PARCIAL
    else:
        estado = EvaluacionCapacidadEstacion.Estado.NO_CUMPLE

    return EvaluacionCapacidadEstacion.objects.create(
        estacion=estacion,
        capacidad=tipo_capacidad,
        estado=estado,
        porcentaje_cumplimiento=porcentaje,
        detalle_recursos=detalle_recursos,
        detalle_personal=detalle_personal,
        observaciones=observaciones,
        evaluado_por=usuario_evaluador,
    )
