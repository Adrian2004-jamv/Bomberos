import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from inventario.permissions import estaciones_permitidas

from .models import DespliegueUnidad, Emergencia
from .permissions import puede_consultar_emergencias, puede_gestionar_emergencias
from .services import registrar_posicion_unidad


def _emergencias_permitidas(usuario):
    return Emergencia.objects.filter(
        estacion_responsable__in=estaciones_permitidas(usuario)
    ).select_related(
        "estacion_responsable",
        "estacion_responsable__cuerpo_bomberos",
        "registrado_por",
    )


@login_required
def lista(request):
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied
    return render(request, "emergencias/lista.html", {
        "emergencias": _emergencias_permitidas(request.user),
        "puede_gestionar_en_admin": request.user.is_staff,
    })


@login_required
def detalle(request, pk):
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied
    emergencia = get_object_or_404(_emergencias_permitidas(request.user), pk=pk)
    despliegues = emergencia.despliegues.select_related(
        "unidad", "estacion_procedencia", "despachado_por"
    )
    return render(request, "emergencias/detalle.html", {
        "emergencia": emergencia,
        "despliegues": despliegues,
        "puede_gestionar_en_admin": request.user.is_staff,
        "puede_transmitir_gps": puede_gestionar_emergencias(request.user),
    })


def _despliegues_permitidos(usuario):
    return DespliegueUnidad.objects.filter(
        estacion_procedencia__in=estaciones_permitidas(usuario)
    ).select_related("emergencia", "unidad", "estacion_procedencia")


@login_required
@ensure_csrf_cookie
def transmitir_gps(request, pk):
    if not puede_gestionar_emergencias(request.user):
        raise PermissionDenied
    despliegue = get_object_or_404(_despliegues_permitidos(request.user), pk=pk)
    if not despliegue.activo or not despliegue.emergencia.admite_despliegues:
        raise PermissionDenied("El despliegue no admite transmisión GPS.")
    return render(request, "emergencias/transmitir_gps.html", {"despliegue": despliegue})


def _error_json(mensaje, estado, codigo):
    return JsonResponse({"error": mensaje, "codigo": codigo}, status=estado)


@require_POST
def registrar_posicion(request, pk):
    if not request.user.is_authenticated:
        return _error_json("Autenticación requerida.", 401, "no_autenticado")
    if request.content_type != "application/json":
        return _error_json("El contenido debe ser JSON.", 415, "contenido_no_valido")
    if not puede_gestionar_emergencias(request.user):
        return _error_json("No tiene autorización para reportar posiciones.", 403, "sin_autorizacion")
    try:
        datos = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _error_json("El cuerpo JSON no es válido.", 400, "json_no_valido")
    if not isinstance(datos, dict):
        return _error_json("El cuerpo JSON debe ser un objeto.", 400, "datos_no_validos")
    despliegue = get_object_or_404(_despliegues_permitidos(request.user), pk=pk)
    fecha_dispositivo = datos.get("fecha_dispositivo")
    if fecha_dispositivo:
        fecha_dispositivo = parse_datetime(str(fecha_dispositivo))
        if fecha_dispositivo is None:
            return _error_json("La fecha del dispositivo no es válida.", 400, "datos_no_validos")
        if timezone.is_naive(fecha_dispositivo):
            fecha_dispositivo = timezone.make_aware(fecha_dispositivo)
    try:
        posicion = registrar_posicion_unidad(
            despliegue, request.user,
            latitud=datos.get("latitud"), longitud=datos.get("longitud"),
            precision=datos.get("precision"), velocidad=datos.get("velocidad"),
            rumbo=datos.get("rumbo"), altitud=datos.get("altitud"),
            fecha_dispositivo=fecha_dispositivo,
        )
    except ValidationError as error:
        mensaje = next(iter(error.messages), "Los datos enviados no son válidos.")
        codigo = "despliegue_inactivo" if "activo" in mensaje or "seguimiento" in mensaje else "datos_no_validos"
        return _error_json(mensaje, 409 if codigo == "despliegue_inactivo" else 400, codigo)
    return JsonResponse({
        "id": posicion.pk,
        "fecha_recepcion": posicion.fecha_recepcion.isoformat(),
        "mensaje": "Posición recibida.",
    }, status=201)


@require_GET
def ultima_posicion(request, pk):
    if not request.user.is_authenticated:
        return _error_json("Autenticación requerida.", 401, "no_autenticado")
    if not puede_consultar_emergencias(request.user):
        return _error_json("No tiene autorización para consultar el despliegue.", 403, "sin_autorizacion")
    despliegue = get_object_or_404(_despliegues_permitidos(request.user), pk=pk)
    posicion = despliegue.posiciones.order_by("-fecha_recepcion", "-pk").first()
    if posicion is None:
        return JsonResponse({"disponible": False, "mensaje": "Todavía no existen posiciones."})
    return JsonResponse({
        "disponible": True,
        "latitud": posicion.ubicacion.y, "longitud": posicion.ubicacion.x,
        "precision": str(posicion.precision) if posicion.precision is not None else None,
        "velocidad": str(posicion.velocidad) if posicion.velocidad is not None else None,
        "rumbo": str(posicion.rumbo) if posicion.rumbo is not None else None,
        "fecha_dispositivo": posicion.fecha_dispositivo.isoformat() if posicion.fecha_dispositivo else None,
        "fecha_recepcion": posicion.fecha_recepcion.isoformat(),
        "estado_despliegue": despliegue.estado,
    })
