from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from emergencias.models import DespliegueUnidad, Emergencia
from emergencias.permissions import puede_consultar_emergencias
from instituciones.models import CuerpoBomberos
from inventario.permissions import estaciones_permitidas

from .services import construir_geojson, construir_recorrido


@login_required
def mapa_operativo(request):
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied
    estaciones = estaciones_permitidas(request.user).filter(activo=True)
    cuerpos = CuerpoBomberos.objects.filter(estaciones__in=estaciones, activo=True).distinct()
    emergencias = Emergencia.objects.filter(
        estacion_responsable__in=estaciones,
        estado__in=(Emergencia.Estado.REPORTADA, Emergencia.Estado.EN_ATENCION, Emergencia.Estado.CONTROLADA),
    )
    return render(request, "mapas/operativo.html", {
        "estaciones_filtro": estaciones,
        "cuerpos_filtro": cuerpos,
        "emergencias_filtro": emergencias,
        "estados_despliegue": DespliegueUnidad.Estado.choices,
        "estados_gps": (
            ("reciente", "Posición reciente"), ("retraso", "Posición con retraso"),
            ("desactualizada", "Sin actualización prolongada"),
            ("sin_posicion", "Esperando primera posición"),
        ),
    })


def _error(mensaje, estado):
    return JsonResponse({"error": mensaje}, status=estado)


@require_GET
def datos_operativos(request):
    if not request.user.is_authenticated:
        return _error("Autenticación requerida.", 401)
    if not puede_consultar_emergencias(request.user):
        return _error("No tiene autorización para consultar el mapa.", 403)
    try:
        datos = construir_geojson(request.user, request.GET)
    except ValidationError as error:
        return _error(next(iter(error.messages), "Los filtros no son válidos."), 400)
    return JsonResponse(datos)


@require_GET
def recorrido_despliegue(request, pk):
    if not request.user.is_authenticated:
        return _error("Autenticación requerida.", 401)
    if not puede_consultar_emergencias(request.user):
        return _error("No tiene autorización para consultar el recorrido.", 403)
    recorrido = construir_recorrido(request.user, pk)
    if recorrido is None:
        return _error("El despliegue no existe o no está autorizado.", 404)
    return JsonResponse(recorrido)

# Create your views here.
