import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

def publicar_posicion_gps(posicion):
    """Publica datos mínimos después de confirmar la transacción HTTP."""
    from mapas.consumers import grupo_estacion

    capa = get_channel_layer()
    if capa is None:
        return
    payload = {
        "despliegue_id": posicion.despliegue_id,
        "unidad": posicion.despliegue.unidad.codigo_interno,
        "emergencia_id": posicion.despliegue.emergencia_id,
        "emergencia": posicion.despliegue.emergencia.codigo,
        "longitud": posicion.ubicacion.x,
        "latitud": posicion.ubicacion.y,
        "precision": float(posicion.precision) if posicion.precision is not None else None,
        "velocidad": float(posicion.velocidad) if posicion.velocidad is not None else None,
        "rumbo": float(posicion.rumbo) if posicion.rumbo is not None else None,
        "estado": posicion.despliegue.estado,
        "fecha_recepcion": posicion.fecha_recepcion.isoformat(),
    }
    try:
        async_to_sync(capa.group_send)(
            grupo_estacion(posicion.despliegue.estacion_procedencia_id),
            {"type": "gps.posicion", "posicion": payload},
        )
    except Exception:
        logger.warning("No fue posible publicar una posición GPS en la capa de canales.")
