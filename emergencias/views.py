import json
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Exists, OuterRef
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from inventario.permissions import estaciones_permitidas

from .forms import EmergenciaForm
from .models import DespliegueUnidad, Emergencia
from .models import FormularioSCI, FormularioSCI211
from .forms_sci import FormularioSCI211Form, RegistroRecursoSCI211FormSet
from .permissions import (puede_consultar_emergencias, puede_consultar_sci,
                          puede_editar_sci, puede_gestionar_emergencias)
from .esquemas_sci import (ESQUEMAS_SCI, campos_periodo, extraer_datos,
                          obtener_esquema, obtener_esquema_catalogo,
                          secciones_completadas,
                          secciones_con_valores)
from .services import registrar_posicion_unidad
from .services_sci import (crear_sci211_desde_emergencia, finalizar_sci,
                          finalizar_sci211, generar_pdf_sci, generar_pdf_sci211)


_ORIENTACION = {"vertical": "Vertical", "horizontal": "Horizontal"}


def _entrada_catalogo(codigo, esquema):
    paginas = esquema["paginas"]
    return {
        "codigo": codigo,
        "nombre": esquema["nombre"],
        "formato": f"{_ORIENTACION[esquema['orientacion']]} · {paginas} página{'s' if paginas > 1 else ''}",
        "estructura": esquema["proposito"],
        "implementado": True,
    }


CATALOGO_FORMULARIOS_SCI = tuple(sorted(
    [_entrada_catalogo(codigo, esquema) for codigo, esquema in ESQUEMAS_SCI.items()] + [{
        "codigo": "211",
        "nombre": "Registro y Control de Recursos",
        "formato": "Horizontal · 2 páginas",
        "estructura": "Fuente maestra de recursos: solicitud, arribo, institución, estado, "
                      "asignación y desmovilización de cada recurso del incidente.",
        "implementado": True,
    }],
    key=lambda entrada: entrada["codigo"],
))


def _emergencias_permitidas(usuario):
    return Emergencia.objects.filter(
        estacion_responsable__in=estaciones_permitidas(usuario)
    ).select_related(
        "estacion_responsable",
        "estacion_responsable__cuerpo_bomberos",
        "registrado_por",
    ).annotate(
        cantidad_formularios_genericos=Count("formularios_sci", distinct=True),
        tiene_sci211=Exists(
            FormularioSCI211.objects.filter(emergencia_id=OuterRef("pk"))
        ),
        sci211_finalizado=Exists(
            FormularioSCI211.objects.filter(
                emergencia_id=OuterRef("pk"),
                estado=FormularioSCI211.Estado.FINALIZADO,
            )
        ),
    )


def _preparar_avance_documental(emergencias):
    for emergencia in emergencias:
        emergencia.formularios_completados = (
            emergencia.cantidad_formularios_genericos + int(emergencia.tiene_sci211)
        )
        emergencia.porcentaje_formularios = round(
            emergencia.formularios_completados / len(CATALOGO_FORMULARIOS_SCI) * 100
        )
        if emergencia.formularios_completados == 0:
            emergencia.etapa_formularios = "Sin iniciar"
            emergencia.clave_etapa_formularios = "sin_iniciar"
        elif emergencia.formularios_completados == len(CATALOGO_FORMULARIOS_SCI):
            emergencia.etapa_formularios = "Completa"
            emergencia.clave_etapa_formularios = "completa"
        elif emergencia.sci211_finalizado:
            emergencia.etapa_formularios = "SCI-211 finalizado"
            emergencia.clave_etapa_formularios = "en_elaboracion"
        else:
            emergencia.etapa_formularios = "En elaboración"
            emergencia.clave_etapa_formularios = "en_elaboracion"
    return emergencias


@login_required
def lista(request):
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied
    emergencias = list(_emergencias_permitidas(request.user))
    return render(request, "emergencias/lista.html", {
        "emergencias": _preparar_avance_documental(emergencias),
        "total_en_curso": sum(not emergencia.esta_terminada for emergencia in emergencias),
        "total_terminadas": sum(emergencia.esta_terminada for emergencia in emergencias),
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
        "catalogo_sci": CATALOGO_FORMULARIOS_SCI,
    })


def _formularios_sci_permitidos(usuario):
    return FormularioSCI211.objects.filter(
        emergencia__estacion_responsable__in=estaciones_permitidas(usuario)
    ).select_related("emergencia", "creado_por", "modificado_por", "finalizado_por")


def _emergencia_para_visualizar(usuario):
    emergencias = _emergencias_permitidas(usuario)
    return emergencias.filter(codigo="EM-SCI-001").first() or emergencias.order_by("pk").first()


def _preparar_expedientes_sci(usuario):
    emergencias = list(
        _emergencias_permitidas(usuario)
        .select_related("formulario_sci_211")
        .prefetch_related("formularios_sci")
    )
    _preparar_avance_documental(emergencias)
    catalogo = {item["codigo"]: item for item in CATALOGO_FORMULARIOS_SCI}
    for emergencia in emergencias:
        genericos = {formulario.codigo_sci: formulario for formulario in emergencia.formularios_sci.all()}
        sci211 = getattr(emergencia, "formulario_sci_211", None)
        documentos = []
        for item in CATALOGO_FORMULARIOS_SCI:
            codigo = item["codigo"]
            if codigo == "211":
                if sci211 is None:
                    continue
                finalizado = sci211.estado == FormularioSCI211.Estado.FINALIZADO
                documentos.append({
                    **catalogo[codigo],
                    "estado": "Finalizado" if finalizado else "Borrador",
                    "clave_estado": "complete" if finalizado else "draft",
                    "actualizado": sci211.fecha_actualizacion,
                    "editable": puede_editar_sci(usuario, emergencia) and not finalizado,
                    "sci211": sci211,
                })
                continue
            formulario = genericos.get(codigo)
            if formulario is None:
                continue
            secciones_llenas, secciones_totales = secciones_completadas(
                obtener_esquema(codigo), formulario.datos
            )
            completo = bool(secciones_totales) and secciones_llenas == secciones_totales
            documentos.append({
                **catalogo[codigo],
                "estado": "Completo" if completo else "En elaboración",
                "clave_estado": "complete" if completo else "draft",
                "actualizado": formulario.fecha_actualizacion,
                "editable": puede_editar_sci(usuario, emergencia),
                "formulario": formulario,
            })
        emergencia.documentos_sci = documentos
        emergencia.puede_editar_documentos = puede_editar_sci(usuario, emergencia)
    return emergencias


@login_required
def sci211_lista(request):
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied
    return render(request, "emergencias/sci211/lista.html", {
        "formularios": _formularios_sci_permitidos(request.user),
        "catalogo_sci": CATALOGO_FORMULARIOS_SCI,
        "expedientes": _preparar_expedientes_sci(request.user),
    })


@login_required
def formulario_sci_catalogo_detalle(request, codigo):
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied
    formulario_catalogo = next(
        (formulario for formulario in CATALOGO_FORMULARIOS_SCI if formulario["codigo"] == codigo),
        None,
    )
    if formulario_catalogo is None:
        raise Http404
    return render(request, "emergencias/sci211/catalogo_detalle.html", {
        "formulario_catalogo": formulario_catalogo,
        "emergencia_visualizacion": _emergencia_para_visualizar(request.user),
    })


@login_required
def formulario_sci_catalogo_visualizar(request, codigo):
    """Muestra la estructura imprimible aun cuando no exista un incidente."""
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied
    esquema = obtener_esquema_catalogo(codigo)
    if esquema is None:
        raise Http404
    cuerpo = SimpleNamespace(nombre="Cuerpos de Bomberos de Cotopaxi")
    estacion = SimpleNamespace(nombre="Estación por asignar", cuerpo_bomberos=cuerpo)
    emergencia = SimpleNamespace(
        pk=None,
        codigo="VISTA-PREVIA",
        tipo_emergencia="Incidente por registrar",
        descripcion="Espacio destinado a la descripción y evaluación inicial del incidente.",
        fecha_reporte=timezone.now(),
        direccion="Ubicación por registrar",
        latitud=None,
        longitud=None,
        estacion_responsable=estacion,
        get_estado_display=lambda: "Sin asociar",
        get_prioridad_display=lambda: "Por definir",
    )
    return render(request, "emergencias/sci_preview.html", {
        "emergencia": emergencia,
        "esquema": esquema,
        "codigo": codigo,
        "formulario_catalogo": next(item for item in CATALOGO_FORMULARIOS_SCI if item["codigo"] == codigo),
        "formulario_generico": None,
        "campos_periodo": [dict(campo, valor="") for campo in campos_periodo(esquema)],
        "secciones": secciones_con_valores(esquema, {}),
        "solo_vista": True,
    })


@login_required
def formulario_sci_visualizar(request, codigo, emergencia_pk):
    emergencia = get_object_or_404(_emergencias_permitidas(request.user), pk=emergencia_pk)
    if not puede_consultar_sci(request.user, emergencia):
        raise PermissionDenied
    if codigo == "211":
        formulario = FormularioSCI211.objects.filter(emergencia=emergencia).first()
        if formulario:
            return redirect("emergencias:sci211_imprimir", pk=formulario.pk)
    contexto = _contexto_documento_sci(request.user, emergencia, codigo)
    contexto["puede_editar"] = puede_editar_sci(request.user, emergencia)
    return render(request, "emergencias/sci_preview.html", contexto)


def _contexto_documento_sci(usuario, emergencia, codigo):
    esquema = obtener_esquema(codigo)
    if esquema is None:
        raise Http404
    formulario = FormularioSCI.objects.filter(emergencia=emergencia, codigo_sci=codigo).first()
    datos = formulario.datos if formulario else {}
    return {
        "emergencia": emergencia,
        "esquema": esquema,
        "codigo": codigo,
        "formulario_catalogo": next(item for item in CATALOGO_FORMULARIOS_SCI if item["codigo"] == codigo),
        "formulario_generico": formulario,
        "campos_periodo": [dict(campo, valor=datos.get(campo["nombre"], ""))
                           for campo in campos_periodo(esquema)],
        "secciones": secciones_con_valores(esquema, datos),
    }


@login_required
def formulario_sci_editar(request, codigo, emergencia_pk):
    emergencia = get_object_or_404(_emergencias_permitidas(request.user), pk=emergencia_pk)
    if codigo == "211":
        formulario = FormularioSCI211.objects.filter(emergencia=emergencia).first()
        if formulario is None:
            formulario = crear_sci211_desde_emergencia(emergencia, request.user)
        return redirect("emergencias:sci211_editar", pk=formulario.pk)
    esquema = obtener_esquema(codigo)
    if esquema is None:
        raise Http404
    if not puede_editar_sci(request.user, emergencia):
        raise PermissionDenied
    formulario, _ = FormularioSCI.objects.get_or_create(
        emergencia=emergencia, codigo_sci=codigo,
        defaults={"creado_por": request.user, "modificado_por": request.user},
    )
    if not formulario.es_editable:
        messages.info(request, f"El formulario SCI-{codigo} está finalizado y es de solo lectura.")
        return redirect("emergencias:sci_visualizar", codigo=codigo, emergencia_pk=emergencia.pk)
    if request.method == "POST":
        formulario.datos = extraer_datos(esquema, request.POST)
        formulario.preparado_por = request.POST.get("preparado_por", "").strip()[:150]
        formulario.modificado_por = request.user
        formulario.save()
        messages.success(request, f"Formulario SCI-{codigo} guardado correctamente.")
        return redirect("emergencias:sci_visualizar", codigo=codigo, emergencia_pk=emergencia.pk)
    contexto = _contexto_documento_sci(request.user, emergencia, codigo)
    contexto["es_horizontal"] = esquema["orientacion"] == "horizontal"
    return render(request, "emergencias/sci_editar.html", contexto)


@login_required
def formulario_sci_finalizar(request, codigo, emergencia_pk):
    emergencia = get_object_or_404(_emergencias_permitidas(request.user), pk=emergencia_pk)
    if not puede_editar_sci(request.user, emergencia) or obtener_esquema(codigo) is None:
        raise PermissionDenied
    formulario = get_object_or_404(FormularioSCI, emergencia=emergencia, codigo_sci=codigo)
    if request.method == "POST":
        try:
            finalizar_sci(formulario, request.user)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, f"Formulario SCI-{codigo} finalizado. Ahora es de solo lectura.")
    return redirect("emergencias:sci_visualizar", codigo=codigo, emergencia_pk=emergencia.pk)


@login_required
def formulario_sci_pdf(request, codigo, emergencia_pk):
    emergencia = get_object_or_404(_emergencias_permitidas(request.user), pk=emergencia_pk)
    if not puede_consultar_sci(request.user, emergencia):
        raise PermissionDenied
    contexto = _contexto_documento_sci(request.user, emergencia, codigo)
    contenido = generar_pdf_sci(contexto)
    respuesta = HttpResponse(contenido, content_type="application/pdf")
    respuesta["Content-Disposition"] = (
        f'attachment; filename="SCI_{codigo}_{emergencia.codigo}.pdf"'
    )
    return respuesta


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
    return render(request, "emergencias/sci211/pdf.html", {
        "formulario": formulario,
        "vista_web": True,
        "filas_vacias": range(max(0, 24 - formulario.registros.count())),
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
