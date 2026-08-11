from django.core.exceptions import ValidationError
from django.db.models import Count, OuterRef, Q, Subquery
from django.urls import reverse
from django.utils import timezone

from emergencias.models import DespliegueUnidad, Emergencia, PosicionUnidad
from inventario.permissions import estaciones_permitidas


SEGUNDOS_RECIENTE = 60
SEGUNDOS_RETRASO = 300
MAX_PUNTOS_RECORRIDO = 200
ESTADOS_EMERGENCIA_ACTIVA = (
    Emergencia.Estado.REPORTADA,
    Emergencia.Estado.EN_ATENCION,
    Emergencia.Estado.CONTROLADA,
)
ESTADOS_GPS = {"reciente", "retraso", "desactualizada", "sin_posicion"}


def clasificar_antiguedad(fecha_recepcion, ahora=None):
    if fecha_recepcion is None:
        return {"codigo": "sin_posicion", "etiqueta": "Esperando primera posición GPS", "segundos": None}
    segundos = max(0, int(((ahora or timezone.now()) - fecha_recepcion).total_seconds()))
    if segundos <= SEGUNDOS_RECIENTE:
        return {"codigo": "reciente", "etiqueta": "Posición reciente", "segundos": segundos}
    if segundos <= SEGUNDOS_RETRASO:
        return {"codigo": "retraso", "etiqueta": "Posición con retraso", "segundos": segundos}
    return {"codigo": "desactualizada", "etiqueta": "Sin actualización prolongada", "segundos": segundos}


def validar_filtros(parametros):
    filtros = {}
    for nombre in ("emergencia", "cuerpo", "estacion"):
        valor = parametros.get(nombre)
        if valor:
            try:
                valor = int(valor)
            except (TypeError, ValueError) as error:
                raise ValidationError(f"El filtro {nombre} no es válido.") from error
            if valor <= 0:
                raise ValidationError(f"El filtro {nombre} no es válido.")
            filtros[nombre] = valor
    estado = parametros.get("estado")
    if estado:
        if estado not in DespliegueUnidad.Estado.values:
            raise ValidationError("El estado de despliegue no es válido.")
        filtros["estado"] = estado
    gps = parametros.get("gps")
    if gps:
        if gps not in ESTADOS_GPS:
            raise ValidationError("El estado GPS no es válido.")
        filtros["gps"] = gps
    return filtros


def _bases_autorizadas(usuario, filtros):
    estaciones = estaciones_permitidas(usuario)
    emergencias = Emergencia.objects.filter(
        estacion_responsable__in=estaciones,
        estado__in=ESTADOS_EMERGENCIA_ACTIVA,
    ).select_related("estacion_responsable", "estacion_responsable__cuerpo_bomberos")
    despliegues = DespliegueUnidad.objects.filter(
        estacion_procedencia__in=estaciones,
        emergencia__estado__in=ESTADOS_EMERGENCIA_ACTIVA,
        estado__in=DespliegueUnidad.ESTADOS_ACTIVOS,
    ).select_related(
        "emergencia", "unidad", "unidad__tipo", "estacion_procedencia",
        "estacion_procedencia__cuerpo_bomberos",
    )
    if "emergencia" in filtros:
        emergencias = emergencias.filter(pk=filtros["emergencia"])
        despliegues = despliegues.filter(emergencia_id=filtros["emergencia"])
    if "cuerpo" in filtros:
        emergencias = emergencias.filter(estacion_responsable__cuerpo_bomberos_id=filtros["cuerpo"])
        despliegues = despliegues.filter(estacion_procedencia__cuerpo_bomberos_id=filtros["cuerpo"])
    if "estacion" in filtros:
        emergencias = emergencias.filter(estacion_responsable_id=filtros["estacion"])
        despliegues = despliegues.filter(estacion_procedencia_id=filtros["estacion"])
    if "estado" in filtros:
        despliegues = despliegues.filter(estado=filtros["estado"])
    return emergencias, despliegues


def construir_geojson(usuario, parametros):
    filtros = validar_filtros(parametros)
    emergencias, despliegues = _bases_autorizadas(usuario, filtros)
    emergencias = emergencias.annotate(
        unidades_activas=Count(
            "despliegues",
            filter=Q(
                despliegues__estado__in=DespliegueUnidad.ESTADOS_ACTIVOS,
                despliegues__estacion_procedencia__in=estaciones_permitidas(usuario),
            ),
        )
    )
    ultima_id = PosicionUnidad.objects.filter(despliegue_id=OuterRef("pk")).order_by(
        "-fecha_recepcion", "-pk"
    ).values("pk")[:1]
    despliegues = list(despliegues.annotate(ultima_posicion_id=Subquery(ultima_id)))
    posiciones = {
        posicion.pk: posicion
        for posicion in PosicionUnidad.objects.filter(
            pk__in=[item.ultima_posicion_id for item in despliegues if item.ultima_posicion_id]
        )
    }
    ahora = timezone.now()
    features = []
    for emergencia in emergencias:
        geometria = None
        if emergencia.latitud is not None and emergencia.longitud is not None:
            geometria = {"type": "Point", "coordinates": [float(emergencia.longitud), float(emergencia.latitud)]}
        features.append({
            "type": "Feature", "id": f"emergencia-{emergencia.pk}", "geometry": geometria,
            "properties": {
                "clase": "emergencia", "id": emergencia.pk, "codigo": emergencia.codigo,
                "tipo": emergencia.tipo_emergencia, "prioridad": emergencia.prioridad,
                "prioridad_etiqueta": emergencia.get_prioridad_display(), "estado": emergencia.estado,
                "estado_etiqueta": emergencia.get_estado_display(), "direccion": emergencia.direccion,
                "fecha_reporte": emergencia.fecha_reporte.isoformat(),
                "estacion": emergencia.estacion_responsable.nombre,
                "institucion": emergencia.estacion_responsable.cuerpo_bomberos.nombre,
                "unidades": emergencia.unidades_activas,
                "detalle_url": reverse("emergencias:detalle", args=[emergencia.pk]),
            },
        })
    for despliegue in despliegues:
        posicion = posiciones.get(despliegue.ultima_posicion_id)
        antiguedad = clasificar_antiguedad(posicion.fecha_recepcion if posicion else None, ahora)
        if filtros.get("gps") and antiguedad["codigo"] != filtros["gps"]:
            continue
        geometria = None if posicion is None else {
            "type": "Point", "coordinates": [posicion.ubicacion.x, posicion.ubicacion.y]
        }
        features.append({
            "type": "Feature", "id": f"unidad-{despliegue.pk}", "geometry": geometria,
            "properties": {
                "clase": "unidad", "id": despliegue.pk,
                "unidad": despliegue.unidad.codigo_interno,
                "nombre_unidad": despliegue.unidad.nombre,
                "tipo_recurso": despliegue.unidad.tipo.nombre,
                "emergencia": despliegue.emergencia.codigo,
                "estado": despliegue.estado, "estado_etiqueta": despliegue.get_estado_display(),
                "estacion": despliegue.estacion_procedencia.nombre,
                "institucion": despliegue.estacion_procedencia.cuerpo_bomberos.nombre,
                "fecha_posicion": posicion.fecha_recepcion.isoformat() if posicion else None,
                "precision": float(posicion.precision) if posicion and posicion.precision is not None else None,
                "velocidad": float(posicion.velocidad) if posicion and posicion.velocidad is not None else None,
                "antiguedad": antiguedad,
                "detalle_url": reverse("emergencias:detalle", args=[despliegue.emergencia_id]),
                "recorrido_url": reverse("mapas:recorrido", args=[despliegue.pk]),
            },
        })
    return {"type": "FeatureCollection", "features": features, "generado_en": ahora.isoformat()}


def construir_recorrido(usuario, despliegue_id):
    _, despliegues = _bases_autorizadas(usuario, {})
    despliegue = despliegues.filter(pk=despliegue_id).first()
    if despliegue is None:
        return None
    posiciones = list(
        PosicionUnidad.objects.filter(despliegue=despliegue)
        .order_by("-fecha_recepcion", "-pk")[:MAX_PUNTOS_RECORRIDO]
    )
    posiciones.reverse()
    coordenadas = [[posicion.ubicacion.x, posicion.ubicacion.y] for posicion in posiciones]
    if len(coordenadas) == 0:
        geometria = None
    elif len(coordenadas) == 1:
        geometria = {"type": "Point", "coordinates": coordenadas[0]}
    else:
        geometria = {"type": "LineString", "coordinates": coordenadas}
    return {
        "type": "Feature", "geometry": geometria,
        "properties": {
            "despliegue": despliegue.pk, "unidad": despliegue.unidad.codigo_interno,
            "emergencia": despliegue.emergencia.codigo, "cantidad_puntos": len(coordenadas),
        },
    }
