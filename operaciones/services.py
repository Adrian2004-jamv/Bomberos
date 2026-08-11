from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from instituciones.models import Estacion
from inventario.models import Recurso

from .models import EvaluacionCapacidadEstacion, TipoCapacidadOperativa


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
    """Evalúa una capacidad usando exclusivamente recursos materiales.

    Cada requisito aporta una cobertura entre 0 y 1, calculada como
    ``min(recursos_encontrados / cantidad_requerida, 1)``. La evaluación se
    persiste como una fotografía histórica y no modifica el inventario.
    """
    _validar_objetos(estacion, tipo_capacidad, usuario_evaluador)

    requisitos = list(
        tipo_capacidad.requisitos_recursos.select_related("tipo_recurso").all()
    )
    if not requisitos:
        raise ValidationError("La capacidad no tiene requisitos de recursos configurados.")

    detalle_recursos = []
    coberturas = []
    coberturas_obligatorias = []

    for requisito in requisitos:
        cantidad_encontrada = Recurso.objects.filter(
            estacion=estacion,
            tipo=requisito.tipo_recurso,
            activo=True,
            estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
            disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
        ).count()
        cobertura = min(
            Decimal(cantidad_encontrada) / Decimal(requisito.cantidad_minima),
            Decimal("1"),
        )
        detalle_recursos.append(
            {
                "requisito_id": requisito.pk,
                "tipo_recurso_id": requisito.tipo_recurso_id,
                "nombre": requisito.tipo_recurso.nombre,
                "cantidad_requerida": requisito.cantidad_minima,
                "cantidad_encontrada": cantidad_encontrada,
                "cantidad_disponible": cantidad_encontrada,
                "obligatorio": requisito.obligatorio,
                "cumplimiento": cantidad_encontrada >= requisito.cantidad_minima,
                "faltante": max(requisito.cantidad_minima - cantidad_encontrada, 0),
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
        observaciones=observaciones,
        evaluado_por=usuario_evaluador,
    )
