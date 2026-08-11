from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.core.paginator import Paginator
from django.db.models import Count, IntegerField, Prefetch, Value
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CuerpoBomberosForm, EstacionForm
from .models import CuerpoBomberos, Estacion
from .permissions import puede_gestionar_instituciones


def _cuerpos_visibles_para(usuario):
    cuerpos = CuerpoBomberos.objects.select_related("canton")
    if puede_gestionar_instituciones(usuario):
        return cuerpos
    if usuario.estacion_id:
        return cuerpos.filter(pk=usuario.estacion.cuerpo_bomberos_id)
    return cuerpos.none()


def _exigir_gestion(usuario):
    if not puede_gestionar_instituciones(usuario):
        raise PermissionDenied


@login_required
def lista(request):
    cuerpos = _cuerpos_visibles_para(request.user)
    if puede_gestionar_instituciones(request.user):
        cuerpos = cuerpos.annotate(cantidad_estaciones=Count("estaciones"))
    else:
        cuerpos = cuerpos.annotate(
            cantidad_estaciones=Value(1, output_field=IntegerField())
        )
    cuerpos = cuerpos.order_by("nombre", "pk")
    pagina = Paginator(cuerpos, 10).get_page(request.GET.get("pagina"))
    return render(
        request,
        "instituciones/lista.html",
        {
            "cuerpos": pagina,
            "pagina": pagina,
            "puede_gestionar": puede_gestionar_instituciones(request.user),
        },
    )


@login_required
def detalle(request, pk):
    estaciones = Estacion.objects.order_by("nombre")
    if not puede_gestionar_instituciones(request.user):
        estaciones = estaciones.filter(pk=request.user.estacion_id)

    cuerpo = get_object_or_404(
        _cuerpos_visibles_para(request.user).prefetch_related(
            Prefetch("estaciones", queryset=estaciones)
        ),
        pk=pk,
    )
    return render(
        request,
        "instituciones/detalle.html",
        {
            "cuerpo": cuerpo,
            "puede_gestionar": puede_gestionar_instituciones(request.user),
        },
    )


@login_required
def crear_cuerpo(request):
    _exigir_gestion(request.user)
    form = CuerpoBomberosForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cuerpo = form.save()
        messages.success(request, "El Cuerpo de Bomberos fue creado correctamente.")
        return redirect("instituciones:detalle", pk=cuerpo.pk)
    return render(
        request,
        "instituciones/formulario_cuerpo.html",
        {"form": form, "titulo": "Crear Cuerpo de Bomberos"},
    )


@login_required
def editar_cuerpo(request, pk):
    _exigir_gestion(request.user)
    cuerpo = get_object_or_404(CuerpoBomberos.objects.select_related("canton"), pk=pk)
    form = CuerpoBomberosForm(request.POST or None, instance=cuerpo)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "La información institucional fue actualizada.")
        return redirect("instituciones:detalle", pk=cuerpo.pk)
    return render(
        request,
        "instituciones/formulario_cuerpo.html",
        {"form": form, "cuerpo": cuerpo, "titulo": "Editar Cuerpo de Bomberos"},
    )


@login_required
def crear_estacion(request, cuerpo_pk):
    _exigir_gestion(request.user)
    cuerpo = get_object_or_404(CuerpoBomberos, pk=cuerpo_pk)
    if request.method == "POST" and "cuerpo_bomberos" in request.POST:
        raise SuspiciousOperation("La institución se determina mediante la URL.")
    form = EstacionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        estacion = form.save(commit=False)
        estacion.cuerpo_bomberos = cuerpo
        estacion.save()
        messages.success(request, "La estación fue creada correctamente.")
        return redirect("instituciones:detalle", pk=cuerpo.pk)
    return render(
        request,
        "instituciones/formulario_estacion.html",
        {"form": form, "cuerpo": cuerpo, "titulo": "Crear estación"},
    )


@login_required
def editar_estacion(request, pk):
    _exigir_gestion(request.user)
    estacion = get_object_or_404(
        Estacion.objects.select_related("cuerpo_bomberos"), pk=pk
    )
    if request.method == "POST" and "cuerpo_bomberos" in request.POST:
        raise SuspiciousOperation("La institución de la estación no es editable.")
    form = EstacionForm(request.POST or None, instance=estacion)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "La estación fue actualizada correctamente.")
        return redirect("instituciones:detalle", pk=estacion.cuerpo_bomberos_id)
    return render(
        request,
        "instituciones/formulario_estacion.html",
        {
            "form": form,
            "cuerpo": estacion.cuerpo_bomberos,
            "estacion": estacion,
            "titulo": "Editar estación",
        },
    )
