from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from inventario.permissions import puede_gestionar_catalogos

from .forms import (EvaluacionCapacidadForm, FiltroHistorialCapacidadForm,
                    RequisitoCapacidadFormSet, TipoCapacidadOperativaForm)
from .models import EvaluacionCapacidadEstacion, TipoCapacidadOperativa
from .permissions import estaciones_capacidades_permitidas, puede_consultar_capacidades, puede_evaluar_capacidades
from .services import evaluar_capacidad_estacion

def exigir_consulta(usuario):
    if not puede_consultar_capacidades(usuario):
        raise PermissionDenied

def exigir_evaluacion(usuario):
    if not puede_evaluar_capacidades(usuario):
        raise PermissionDenied

def evaluaciones_visibles(usuario):
    return EvaluacionCapacidadEstacion.objects.filter(
        estacion__in=estaciones_capacidades_permitidas(usuario)
    ).select_related(
        "estacion",
        "estacion__cuerpo_bomberos",
        "capacidad",
        "evaluado_por",
    )

@login_required
@require_GET
def lista_capacidades(request):
    exigir_consulta(request.user)
    capacidades = TipoCapacidadOperativa.objects.annotate(
        cantidad_requisitos=Count("requisitos_recursos")
    ).order_by("nombre")
    pagina = Paginator(capacidades, 12).get_page(request.GET.get("pagina"))
    contexto = {
            "capacidades": pagina,
            "pagina": pagina,
            "puede_evaluar": puede_evaluar_capacidades(request.user),
        }

    return render(request, "operaciones/capacidades_lista.html", contexto)

@login_required
@require_GET
def detalle_capacidad(request, pk):
    exigir_consulta(request.user)
    capacidad = get_object_or_404(
        TipoCapacidadOperativa.objects.prefetch_related(
            "requisitos_recursos__tipo_recurso__categoria"
        ),
        pk=pk,
    )
    contexto = {
            "capacidad": capacidad,
            "puede_evaluar": puede_evaluar_capacidades(request.user),
        }

    return render(request, "operaciones/capacidad_detalle.html", contexto)

@login_required
def evaluar_capacidad(request):
    exigir_evaluacion(request.user)
    capacidad_inicial = None
    capacidad_id = request.GET.get("capacidad", "").strip()
    if capacidad_id:
        capacidad_inicial = TipoCapacidadOperativa.objects.filter(
            pk=capacidad_id, activo=True
        ).first()
    form = EvaluacionCapacidadForm(
        request.POST or None,
        usuario=request.user,
        capacidad_inicial=capacidad_inicial,
    )
    if request.method == "POST" and form.is_valid():
        try:
            evaluacion = evaluar_capacidad_estacion(
                estacion=form.cleaned_data["estacion"],
                tipo_capacidad=form.cleaned_data["tipo_capacidad"],
                usuario_evaluador=request.user,
                observaciones=form.cleaned_data["observaciones"],
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "La capacidad fue evaluada correctamente.")
            return redirect("operaciones:detalle_evaluacion", pk=evaluacion.pk)
    contexto = {"form": form}

    return render(request, "operaciones/evaluacion_formulario.html", contexto)

@login_required
@require_GET
def historial_evaluaciones(request):
    exigir_consulta(request.user)
    evaluaciones = evaluaciones_visibles(request.user)
    form = FiltroHistorialCapacidadForm(request.GET or None, usuario=request.user)
    if form.is_valid():
        filtros = form.cleaned_data
        if filtros.get("institucion"):
            evaluaciones = evaluaciones.filter(
                estacion__cuerpo_bomberos=filtros["institucion"]
            )
        if filtros.get("estacion"):
            evaluaciones = evaluaciones.filter(estacion=filtros["estacion"])
        if filtros.get("capacidad"):
            evaluaciones = evaluaciones.filter(capacidad=filtros["capacidad"])
        if filtros.get("estado"):
            evaluaciones = evaluaciones.filter(estado=filtros["estado"])
        if filtros.get("fecha_desde"):
            evaluaciones = evaluaciones.filter(
                fecha_evaluacion__date__gte=filtros["fecha_desde"]
            )
        if filtros.get("fecha_hasta"):
            evaluaciones = evaluaciones.filter(
                fecha_evaluacion__date__lte=filtros["fecha_hasta"]
            )
    pagina = Paginator(evaluaciones, 15).get_page(request.GET.get("pagina"))
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    contexto = {
            "form": form,
            "evaluaciones": pagina,
            "pagina": pagina,
            "querystring": parametros.urlencode(),
            "puede_evaluar": puede_evaluar_capacidades(request.user),
        }

    return render(request, "operaciones/evaluaciones_historial.html", contexto)

@login_required
@require_GET
def detalle_evaluacion(request, pk):
    exigir_consulta(request.user)
    evaluacion = get_object_or_404(evaluaciones_visibles(request.user), pk=pk)
    detalle_recursos = []
    for requisito in evaluacion.detalle_recursos:
        detalle = requisito.copy()
        detalle["cantidad_encontrada"] = detalle.get(
            "cantidad_encontrada", detalle.get("cantidad_disponible", 0)
        )
        detalle_recursos.append(detalle)
    contexto = {"evaluacion": evaluacion, "detalle_recursos": detalle_recursos}

    return render(request, "operaciones/evaluacion_detalle.html", contexto)

def exigir_catalogos(usuario):
    if not puede_gestionar_catalogos(usuario):
        raise PermissionDenied

def _editar_capacidad(request, capacidad, contexto):
    """Guarda la capacidad y sus requisitos en una sola operación.

    Los requisitos son la definición de la capacidad, no un anexo: una
    capacidad guardada a medias mediría mal a todas las estaciones hasta que
    alguien completara la otra mitad.
    """
    formulario = TipoCapacidadOperativaForm(request.POST or None, instance=capacidad)
    requisitos = RequisitoCapacidadFormSet(request.POST or None, instance=capacidad)
    if request.method == "POST" and formulario.is_valid() and requisitos.is_valid():
        with transaction.atomic():
            guardada = formulario.save()
            requisitos.instance = guardada
            requisitos.save()
        messages.success(request, f"La capacidad {guardada.nombre} fue guardada.")
        return redirect("operaciones:detalle_capacidad", pk=guardada.pk)
    contexto = {
        **contexto,
        "formulario": formulario,
        "requisitos": requisitos,
    }

    return render(request, "operaciones/formulario_capacidad.html", contexto)

@login_required
def crear_capacidad(request):
    exigir_catalogos(request.user)
    return _editar_capacidad(request, TipoCapacidadOperativa(), {
        "titulo": "Nueva capacidad operativa",
        "descripcion": "Defina qué recursos materiales necesita una estación para "
                       "sostener esta respuesta. El motor de evaluación compara el "
                       "inventario de cada estación contra estos requisitos.",
        "accion": "Crear capacidad",
    })

@login_required
def editar_capacidad(request, pk):
    exigir_catalogos(request.user)
    capacidad = get_object_or_404(TipoCapacidadOperativa, pk=pk)
    return _editar_capacidad(request, capacidad, {
        "capacidad": capacidad,
        "titulo": f"Editar {capacidad.codigo}",
        "descripcion": "Las evaluaciones ya registradas conservan el detalle con el que "
                       "se calcularon y no se recalculan al cambiar los requisitos.",
        "accion": "Guardar cambios",
    })
