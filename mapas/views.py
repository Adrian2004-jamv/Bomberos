from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from emergencias.models import DespliegueUnidad, Emergencia
from emergencias.permissions import es_chofer, puede_consultar_emergencias
from instituciones.models import CuerpoBomberos
from inventario.permissions import estaciones_permitidas

from .services import construir_geojson, construir_recorrido

ESTADOS_ABIERTOS = (
    Emergencia.Estado.REPORTADA,
    Emergencia.Estado.EN_ATENCION,
    Emergencia.Estado.CONTROLADA,
)

ESTADOS_GPS = (
    ("reciente", "Posición reciente"),
    ("retraso", "Posición con retraso"),
    ("desactualizada", "Sin actualización prolongada"),
    ("sin_posicion", "Esperando primera posición"),
)

# ==========================================
# MÓDULO: MAPA OPERATIVO
# ==========================================

@login_required
def mapa_operativo(request):
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied

    estaciones = estaciones_permitidas(request.user).filter(activo=True)
    cuerpos = CuerpoBomberos.objects.filter(estaciones__in=estaciones, activo=True).distinct()
    emergencias = Emergencia.objects.filter(
        estacion_responsable__in=estaciones,
        estado__in=ESTADOS_ABIERTOS,
    )

    contexto = {
        "estaciones_filtro": estaciones,
        "cuerpos_filtro": cuerpos,
        "emergencias_filtro": emergencias,
        "estados_despliegue": DespliegueUnidad.Estado.choices,
        "estados_gps": ESTADOS_GPS,
    }

    return render(request, "mapas/operativo.html", contexto)

# ==========================================
# MÓDULO: DATOS PARA EL MAPA
# ==========================================

def responder_error(mensaje, estado):
    return JsonResponse({"error": mensaje}, status=estado)

@require_GET
def datos_operativos(request):
    if not request.user.is_authenticated:
        return responder_error("Autenticación requerida.", 401)

    if not puede_consultar_emergencias(request.user):
        return responder_error("No tiene autorización para consultar el mapa.", 403)

    try:
        datos = construir_geojson(request.user, request.GET)
    except ValidationError as error:
        return responder_error(next(iter(error.messages), "Los filtros no son válidos."), 400)

    return JsonResponse(datos)

@require_GET
def recorrido_despliegue(request, pk):
    if not request.user.is_authenticated:
        return responder_error("Autenticación requerida.", 401)

    # Quien conduce la unidad puede revisar su propio recorrido aunque su perfil
    # no alcance el resto del mapa.
    if not (puede_consultar_emergencias(request.user) or es_chofer(request.user)):
        return responder_error("No tiene autorización para consultar el recorrido.", 403)

    recorrido = construir_recorrido(
        request.user, pk,
        conducidos_por=request.user if es_chofer(request.user) else None,
    )

    if recorrido is None:
        return responder_error("El despliegue no existe o no está autorizado.", 404)

    return JsonResponse(recorrido)
