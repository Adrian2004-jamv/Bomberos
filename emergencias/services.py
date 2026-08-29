"""Operaciones transaccionales para despliegues y posiciones de unidades.

``select_for_update`` bloquea la fila mientras dura la operación. Sobre
PostgreSQL exige una transacción abierta: toda función que lo use debe llevar
``@transaction.atomic``, o fallará con ``TransactionManagementError`` en cuanto
se ejecute fuera de las pruebas. ``TestCase`` envuelve cada prueba en una
transacción y oculta esa omisión, de modo que las comprobaciones que la vigilan
usan ``TransactionTestCase``.

Se conservan además las validaciones de servicio y una restricción única
parcial en la base de datos.
"""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from inventario.models import Recurso
from inventario.permissions import estaciones_permitidas
from inventario.services import actualizar_estado_recurso

from .models import DespliegueUnidad, Emergencia, PosicionUnidad
from .permissions import estacion_autorizada, puede_gestionar_emergencias


TRANSICIONES_VALIDAS = {
    DespliegueUnidad.Estado.ASIGNADA: {
        DespliegueUnidad.Estado.EN_RUTA,
        DespliegueUnidad.Estado.CANCELADA,
    },
    DespliegueUnidad.Estado.EN_RUTA: {
        DespliegueUnidad.Estado.EN_SITIO,
        DespliegueUnidad.Estado.RETORNANDO,
        DespliegueUnidad.Estado.CANCELADA,
    },
    DespliegueUnidad.Estado.EN_SITIO: {
        DespliegueUnidad.Estado.RETORNANDO,
        DespliegueUnidad.Estado.FINALIZADA,
        DespliegueUnidad.Estado.CANCELADA,
    },
    DespliegueUnidad.Estado.RETORNANDO: {DespliegueUnidad.Estado.FINALIZADA},
}

ESTADOS_TERMINALES_EMERGENCIA = {Emergencia.Estado.CERRADA, Emergencia.Estado.CANCELADA}

TRANSICIONES_EMERGENCIA = {
    Emergencia.Estado.REPORTADA: {
        Emergencia.Estado.EN_ATENCION,
        Emergencia.Estado.CANCELADA,
    },
    Emergencia.Estado.EN_ATENCION: {
        Emergencia.Estado.CONTROLADA,
        Emergencia.Estado.CERRADA,
        Emergencia.Estado.CANCELADA,
    },
    Emergencia.Estado.CONTROLADA: {
        Emergencia.Estado.EN_ATENCION,
        Emergencia.Estado.CERRADA,
    },
    Emergencia.Estado.CERRADA: set(),
    Emergencia.Estado.CANCELADA: set(),
}


def _validar_usuario(usuario):
    Usuario = get_user_model()
    if (
        not isinstance(usuario, Usuario)
        or not usuario.pk
        or not Usuario.objects.filter(pk=usuario.pk, is_active=True).exists()
        or not puede_gestionar_emergencias(usuario)
    ):
        raise ValidationError("El usuario no está autorizado para gestionar despliegues.")


def unidades_desplegables(emergencia, usuario_responsable):
    """Unidades que ``desplegar_unidad`` aceptaría para esta emergencia.

    Reproduce en una consulta las condiciones que el servicio comprueba fila a
    fila, de modo que el formulario ofrezca solo lo que se puede despachar. La
    validación real sigue estando en ``desplegar_unidad``: entre que se dibuja
    la lista y se envía el formulario, otra estación puede tomar la unidad.
    """
    return (
        Recurso.objects.filter(
            estacion__in=estaciones_permitidas(usuario_responsable),
            tipo__es_unidad_desplegable=True,
            activo=True,
            estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
            disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
        )
        .exclude(despliegues_emergencias__estado__in=DespliegueUnidad.ESTADOS_ACTIVOS)
        .select_related("tipo", "estacion")
        .order_by("estacion__nombre", "codigo_interno")
    )


@transaction.atomic
def desplegar_unidad(emergencia, unidad, usuario_responsable, observaciones=""):
    _validar_usuario(usuario_responsable)
    if not isinstance(emergencia, Emergencia) or not emergencia.pk:
        raise ValidationError("La emergencia no existe.")
    if not isinstance(unidad, Recurso) or not unidad.pk:
        raise ValidationError("La unidad no existe.")

    try:
        emergencia_actual = Emergencia.objects.select_for_update().get(pk=emergencia.pk)
        unidad_actual = Recurso.objects.select_for_update().select_related(
            "tipo", "estacion"
        ).get(pk=unidad.pk)
    except (Emergencia.DoesNotExist, Recurso.DoesNotExist) as error:
        raise ValidationError("La emergencia o la unidad no existe.") from error

    if not estacion_autorizada(usuario_responsable, emergencia_actual.estacion_responsable_id):
        raise ValidationError("La emergencia está fuera del ámbito autorizado.")
    if not estacion_autorizada(usuario_responsable, unidad_actual.estacion_id):
        raise ValidationError("La unidad pertenece a una estación no autorizada.")
    if not emergencia_actual.admite_despliegues:
        raise ValidationError("Una emergencia cerrada o cancelada no admite despliegues.")
    if not unidad_actual.tipo.es_unidad_desplegable:
        raise ValidationError("El recurso no está identificado como unidad desplegable.")
    if not unidad_actual.activo:
        raise ValidationError("La unidad está inactiva.")
    if unidad_actual.estado_operativo != Recurso.EstadoOperativo.OPERATIVO:
        raise ValidationError("La unidad no se encuentra operativa.")
    if unidad_actual.disponibilidad != Recurso.Disponibilidad.DISPONIBLE:
        raise ValidationError("La unidad no se encuentra disponible.")
    if DespliegueUnidad.objects.filter(
        unidad=unidad_actual, estado__in=DespliegueUnidad.ESTADOS_ACTIVOS
    ).exists():
        raise ValidationError("La unidad ya tiene un despliegue activo.")

    actualizar_estado_recurso(
        recurso=unidad_actual,
        nuevo_estado_operativo=unidad_actual.estado_operativo,
        nueva_disponibilidad=Recurso.Disponibilidad.ASIGNADO,
        usuario_responsable=usuario_responsable,
        motivo=f"Despacho a emergencia {emergencia_actual.codigo}",
        observaciones=observaciones,
    )
    try:
        despliegue = DespliegueUnidad.objects.create(
            emergencia=emergencia_actual,
            unidad=unidad_actual,
            estacion_procedencia=unidad_actual.estacion,
            despachado_por=usuario_responsable,
            observaciones=observaciones,
        )
    except IntegrityError as error:
        raise ValidationError("La unidad ya fue asignada a otro despliegue activo.") from error
    return despliegue


@transaction.atomic
def cambiar_estado_despliegue(despliegue, nuevo_estado, usuario_responsable, observaciones=""):
    _validar_usuario(usuario_responsable)
    if nuevo_estado not in DespliegueUnidad.Estado.values:
        raise ValidationError("El estado de despliegue no es válido.")
    if not isinstance(despliegue, DespliegueUnidad) or not despliegue.pk:
        raise ValidationError("El despliegue no existe.")
    try:
        actual = DespliegueUnidad.objects.select_for_update().select_related(
            "unidad", "emergencia"
        ).get(pk=despliegue.pk)
    except DespliegueUnidad.DoesNotExist as error:
        raise ValidationError("El despliegue no existe.") from error
    if not estacion_autorizada(usuario_responsable, actual.estacion_procedencia_id):
        raise ValidationError("El despliegue está fuera del ámbito autorizado.")
    if nuevo_estado not in TRANSICIONES_VALIDAS.get(actual.estado, set()):
        raise ValidationError(
            f"No se puede cambiar de {actual.get_estado_display()} al estado solicitado."
        )

    momento = timezone.now()
    actual.estado = nuevo_estado
    campos = ["estado"]
    if nuevo_estado == DespliegueUnidad.Estado.EN_RUTA and not actual.fecha_salida:
        actual.fecha_salida = momento
        campos.append("fecha_salida")
    if nuevo_estado == DespliegueUnidad.Estado.EN_SITIO and not actual.fecha_llegada:
        actual.fecha_llegada = momento
        campos.append("fecha_llegada")
    if nuevo_estado in DespliegueUnidad.ESTADOS_FINALES:
        actual.fecha_retorno = momento
        campos.append("fecha_retorno")
    if observaciones:
        actual.observaciones = "\n".join(
            parte for parte in (actual.observaciones, observaciones.strip()) if parte
        )
        campos.append("observaciones")
    actual.save(update_fields=campos)

    if nuevo_estado in DespliegueUnidad.ESTADOS_FINALES:
        unidad = Recurso.objects.select_for_update().get(pk=actual.unidad_id)
        disponibilidad = (
            Recurso.Disponibilidad.DISPONIBLE
            if unidad.activo and unidad.estado_operativo == Recurso.EstadoOperativo.OPERATIVO
            else Recurso.Disponibilidad.NO_DISPONIBLE
        )
        actualizar_estado_recurso(
            recurso=unidad,
            nuevo_estado_operativo=unidad.estado_operativo,
            nueva_disponibilidad=disponibilidad,
            usuario_responsable=usuario_responsable,
            motivo=f"Cierre de despliegue en emergencia {actual.emergencia.codigo}",
            observaciones=observaciones,
        )
    return actual


def finalizar_despliegue(despliegue, usuario_responsable, observaciones=""):
    return cambiar_estado_despliegue(
        despliegue,
        DespliegueUnidad.Estado.FINALIZADA,
        usuario_responsable,
        observaciones,
    )


def cancelar_despliegue(despliegue, usuario_responsable, observaciones=""):
    return cambiar_estado_despliegue(
        despliegue,
        DespliegueUnidad.Estado.CANCELADA,
        usuario_responsable,
        observaciones,
    )


@transaction.atomic
def cambiar_estado_emergencia(emergencia, nuevo_estado, usuario_responsable):
    """Avanza la emergencia por su ciclo operativo y sella el cierre.

    Cerrar o cancelar exige que ningún despliegue siga activo: la unidad
    quedaría marcada como asignada a un incidente terminado y el inventario
    dejaría de reflejar la realidad.
    """
    _validar_usuario(usuario_responsable)
    if nuevo_estado not in Emergencia.Estado.values:
        raise ValidationError("El estado de la emergencia no es válido.")
    if not isinstance(emergencia, Emergencia) or not emergencia.pk:
        raise ValidationError("La emergencia no existe.")
    try:
        actual = Emergencia.objects.select_for_update().get(pk=emergencia.pk)
    except Emergencia.DoesNotExist as error:
        raise ValidationError("La emergencia no existe.") from error

    if not estacion_autorizada(usuario_responsable, actual.estacion_responsable_id):
        raise ValidationError("La emergencia está fuera del ámbito autorizado.")
    if nuevo_estado not in TRANSICIONES_EMERGENCIA.get(actual.estado, set()):
        raise ValidationError(
            f"No se puede pasar de {actual.get_estado_display()} al estado solicitado."
        )

    campos = ["estado"]
    if nuevo_estado in ESTADOS_TERMINALES_EMERGENCIA:
        pendientes = list(
            DespliegueUnidad.objects.filter(
                emergencia=actual, estado__in=DespliegueUnidad.ESTADOS_ACTIVOS
            ).select_related("unidad")
        )
        if pendientes:
            unidades = ", ".join(despliegue.unidad.codigo_interno for despliegue in pendientes)
            raise ValidationError(
                f"Todavía hay unidades en la emergencia ({unidades}). "
                "Finalice o cancele cada despliegue antes de terminar la emergencia."
            )
        momento = timezone.now()
        if momento < actual.fecha_reporte:
            raise ValidationError(
                "La fecha de reporte es posterior al momento actual; "
                "corríjala antes de terminar la emergencia."
            )
        actual.fecha_cierre = momento
        campos.append("fecha_cierre")

    actual.estado = nuevo_estado
    actual.save(update_fields=campos)
    return actual


def transiciones_disponibles(transiciones, estado_actual, opciones):
    """Traduce un mapa de transiciones a pares valor/etiqueta para la interfaz."""
    permitidos = transiciones.get(estado_actual) or set()
    return [
        {"valor": valor, "etiqueta": etiqueta}
        for valor, etiqueta in opciones.choices
        if valor in permitidos
    ]


def _ajustar_a_campo(valor, nombre_campo):
    """Ajusta un dato del sensor a los decimales que admite su campo.

    El navegador entrega precisión, velocidad, rumbo y altitud con toda la
    resolución del flotante, mientras que el modelo las guarda con dos o tres
    decimales. El ajuste se hace aquí y no en el navegador porque este extremo
    atiende peticiones de cualquier cliente, y es el servidor el que conoce el
    formato de almacenamiento. Los decimales se leen del propio campo para que
    la regla siga valiendo si el modelo cambia.
    """
    if valor is None or valor == "":
        return None
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError({nombre_campo: "Debe ser un valor numérico."}) from error
    if not numero.is_finite():
        raise ValidationError({nombre_campo: "Debe ser un valor numérico."})
    decimales = PosicionUnidad._meta.get_field(nombre_campo).decimal_places
    return numero.quantize(Decimal(1).scaleb(-decimales))


@transaction.atomic
def registrar_posicion_unidad(
    despliegue,
    usuario_responsable,
    *,
    latitud,
    longitud,
    precision=None,
    velocidad=None,
    rumbo=None,
    altitud=None,
    fecha_dispositivo=None,
    fuente=PosicionUnidad.Fuente.NAVEGADOR,
):
    """Valida y conserva una posición dentro del recorrido de un despliegue."""
    _validar_usuario(usuario_responsable)
    if not isinstance(despliegue, DespliegueUnidad) or not despliegue.pk:
        raise ValidationError("El despliegue no existe.")
    try:
        actual = DespliegueUnidad.objects.select_for_update().select_related(
            "emergencia", "unidad"
        ).get(pk=despliegue.pk)
    except DespliegueUnidad.DoesNotExist as error:
        raise ValidationError("El despliegue no existe.") from error
    if not estacion_autorizada(usuario_responsable, actual.estacion_procedencia_id):
        raise ValidationError("El despliegue está fuera del ámbito autorizado.")
    if actual.estado not in DespliegueUnidad.ESTADOS_ACTIVOS:
        raise ValidationError("El despliegue ya no está activo.")
    if not actual.emergencia.admite_despliegues:
        raise ValidationError("La emergencia ya no admite seguimiento de unidades.")
    if actual.unidad_id != despliegue.unidad_id:
        raise ValidationError("La unidad ya no corresponde al despliegue.")
    if fecha_dispositivo and timezone.is_naive(fecha_dispositivo):
        fecha_dispositivo = timezone.make_aware(fecha_dispositivo)
    if fecha_dispositivo and fecha_dispositivo > timezone.now() + timedelta(minutes=5):
        raise ValidationError({"fecha_dispositivo": "La fecha del dispositivo está adelantada."})

    try:
        latitud_num = float(latitud)
        longitud_num = float(longitud)
    except (TypeError, ValueError) as error:
        raise ValidationError("La latitud y la longitud deben ser valores numéricos.") from error
    if not -90 <= latitud_num <= 90:
        raise ValidationError({"latitud": "La latitud debe estar entre -90 y 90."})
    if not -180 <= longitud_num <= 180:
        raise ValidationError({"longitud": "La longitud debe estar entre -180 y 180."})

    posicion = PosicionUnidad(
        despliegue=actual,
        ubicacion=Point(longitud_num, latitud_num, srid=4326),
        precision=_ajustar_a_campo(precision, "precision"),
        velocidad=_ajustar_a_campo(velocidad, "velocidad"),
        rumbo=_ajustar_a_campo(rumbo, "rumbo"),
        altitud=_ajustar_a_campo(altitud, "altitud"),
        fecha_dispositivo=fecha_dispositivo,
        reportado_por=usuario_responsable,
        fuente=fuente,
    )
    posicion.full_clean()
    posicion.save()
    from .realtime import publicar_posicion_gps

    transaction.on_commit(lambda: publicar_posicion_gps(posicion), robust=True)
    return posicion
