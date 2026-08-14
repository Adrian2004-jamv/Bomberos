import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from inventario.permissions import estaciones_permitidas

from .forms import EmergenciaForm
from .models import DespliegueUnidad, Emergencia
from .models import FormularioSCI211
from .forms_sci import FormularioSCI211Form, RegistroRecursoSCI211FormSet
from .permissions import (puede_consultar_emergencias, puede_consultar_sci,
                          puede_editar_sci, puede_gestionar_emergencias)
from .services import registrar_posicion_unidad
from .services_sci import crear_sci211_desde_emergencia, finalizar_sci211, generar_pdf_sci211


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
        "puede_crear": puede_gestionar_emergencias(request.user),
    })


@login_required
def crear(request):
    if not puede_gestionar_emergencias(request.user):
        raise PermissionDenied
    formulario = EmergenciaForm(request.POST or None, usuario=request.user)
    if request.method == "POST" and formulario.is_valid():
        emergencia = formulario.save(commit=False)
        emergencia.registrado_por = request.user
        emergencia.estado = Emergencia.Estado.REPORTADA
        emergencia.save()
        messages.success(request, "Emergencia registrada correctamente.")
        return redirect("emergencias:detalle", pk=emergencia.pk)
    return render(request, "emergencias/formulario.html", {"form": formulario})


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
        "sci211": getattr(emergencia, "formulario_sci_211", None),
        "puede_editar_sci": puede_editar_sci(request.user, emergencia),
    })


def _formularios_sci_permitidos(usuario):
    return FormularioSCI211.objects.filter(
        emergencia__estacion_responsable__in=estaciones_permitidas(usuario)
    ).select_related("emergencia", "creado_por", "modificado_por", "finalizado_por")


@login_required
def sci211_lista(request):
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied
    return render(request, "emergencias/sci211/lista.html", {
        "formularios": _formularios_sci_permitidos(request.user)
    })


@login_required
@require_POST
def sci211_crear(request, emergencia_pk):
    emergencia = get_object_or_404(_emergencias_permitidas(request.user), pk=emergencia_pk)
    if not puede_editar_sci(request.user, emergencia):
        raise PermissionDenied
    formulario = FormularioSCI211.objects.filter(emergencia=emergencia).first()
    if formulario is None:
        formulario = crear_sci211_desde_emergencia(emergencia, request.user)
        messages.success(request, "Formulario SCI-211 creado como borrador.")
    return redirect("emergencias:sci211_editar" if formulario.es_editable else "emergencias:sci211_detalle", pk=formulario.pk)


@login_required
def sci211_editar(request, pk):
    formulario = get_object_or_404(_formularios_sci_permitidos(request.user), pk=pk)
    if not puede_editar_sci(request.user, formulario.emergencia):
        raise PermissionDenied
    if not formulario.es_editable:
        messages.info(request, "El formulario finalizado es de solo lectura.")
        return redirect("emergencias:sci211_detalle", pk=pk)
    cabecera = FormularioSCI211Form(request.POST or None, instance=formulario)
    registros = RegistroRecursoSCI211FormSet(request.POST or None, instance=formulario)
    if request.method == "POST" and cabecera.is_valid() and registros.is_valid():
        cabecera.save(commit=False)
        formulario.modificado_por = request.user
        formulario.save()
        instancias = registros.save(commit=False)
        for borrado in registros.deleted_objects:
            borrado.delete()
        for orden, instancia in enumerate(instancias, start=1):
            instancia.orden = orden
            instancia.save()
        messages.success(request, "Borrador SCI-211 guardado.")
        return redirect("emergencias:sci211_editar", pk=pk)
    return render(request, "emergencias/sci211/formulario.html", {
        "formulario_sci": formulario, "cabecera": cabecera, "registros": registros,
    })


@login_required
def sci211_detalle(request, pk):
    formulario = get_object_or_404(_formularios_sci_permitidos(request.user), pk=pk)
    return render(request, "emergencias/sci211/detalle.html", {
        "formulario_sci": formulario,
        "puede_editar": formulario.es_editable and puede_editar_sci(request.user, formulario.emergencia),
    })


@login_required
def sci211_finalizar(request, pk):
    formulario = get_object_or_404(_formularios_sci_permitidos(request.user), pk=pk)
    if not puede_editar_sci(request.user, formulario.emergencia) or not formulario.es_editable:
        raise PermissionDenied
    if request.method == "POST":
        try:
            finalizar_sci211(formulario, request.user)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
            return redirect("emergencias:sci211_editar", pk=pk)
        messages.success(request, "Formulario SCI-211 finalizado. Ahora es de solo lectura.")
        return redirect("emergencias:sci211_detalle", pk=pk)
    return render(request, "emergencias/sci211/finalizar.html", {"formulario_sci": formulario})


@login_required
def sci211_pdf(request, pk):
    formulario = get_object_or_404(_formularios_sci_permitidos(request.user), pk=pk)
    contenido = generar_pdf_sci211(formulario)
    respuesta = HttpResponse(contenido, content_type="application/pdf")
    respuesta["Content-Disposition"] = f'attachment; filename="SCI_211_{formulario.emergencia.codigo}.pdf"'
    return respuesta


@login_required
def sci211_imprimir(request, pk):
    formulario = get_object_or_404(_formularios_sci_permitidos(request.user), pk=pk)
    return render(request, "emergencias/sci211/pdf.html", {"formulario": formulario, "vista_web": True})


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
