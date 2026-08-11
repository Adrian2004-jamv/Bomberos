from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from .forms import EvaluacionCapacidadForm, FiltroHistorialCapacidadForm
from .models import EvaluacionCapacidadEstacion, TipoCapacidadOperativa
from .permissions import (
    estaciones_capacidades_permitidas,
    puede_consultar_capacidades,
    puede_evaluar_capacidades,
)
from .services import evaluar_capacidad_estacion


def _exigir_consulta(usuario):
    if not puede_consultar_capacidades(usuario):
        raise PermissionDenied


def _exigir_evaluacion(usuario):
    if not puede_evaluar_capacidades(usuario):
        raise PermissionDenied


def _evaluaciones_visibles(usuario):
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
    _exigir_consulta(request.user)
    capacidades = TipoCapacidadOperativa.objects.annotate(
        cantidad_requisitos=Count("requisitos_recursos")
    ).order_by("nombre")
    pagina = Paginator(capacidades, 12).get_page(request.GET.get("pagina"))
    return render(
        request,
        "operaciones/capacidades_lista.html",
        {
            "capacidades": pagina,
            "pagina": pagina,
            "puede_evaluar": puede_evaluar_capacidades(request.user),
        },
    )


@login_required
@require_GET
def detalle_capacidad(request, pk):
    _exigir_consulta(request.user)
    capacidad = get_object_or_404(
        TipoCapacidadOperativa.objects.prefetch_related(
            "requisitos_recursos__tipo_recurso__categoria"
        ),
        pk=pk,
    )
    return render(
        request,
        "operaciones/capacidad_detalle.html",
        {
            "capacidad": capacidad,
            "puede_evaluar": puede_evaluar_capacidades(request.user),
        },
    )


@login_required
def evaluar_capacidad(request):
    _exigir_evaluacion(request.user)
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
    return render(
        request,
        "operaciones/evaluacion_formulario.html",
        {"form": form},
    )


@login_required
@require_GET
def historial_evaluaciones(request):
    _exigir_consulta(request.user)
    evaluaciones = _evaluaciones_visibles(request.user)
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
    return render(
        request,
        "operaciones/evaluaciones_historial.html",
        {
            "form": form,
            "evaluaciones": pagina,
            "pagina": pagina,
            "querystring": parametros.urlencode(),
            "puede_evaluar": puede_evaluar_capacidades(request.user),
        },
    )


@login_required
@require_GET
def detalle_evaluacion(request, pk):
    _exigir_consulta(request.user)
    evaluacion = get_object_or_404(_evaluaciones_visibles(request.user), pk=pk)
    detalle_recursos = []
    for requisito in evaluacion.detalle_recursos:
        detalle = requisito.copy()
        detalle["cantidad_encontrada"] = detalle.get(
            "cantidad_encontrada", detalle.get("cantidad_disponible", 0)
        )
        detalle_recursos.append(detalle)
    return render(
        request,
        "operaciones/evaluacion_detalle.html",
        {"evaluacion": evaluacion, "detalle_recursos": detalle_recursos},
    )
