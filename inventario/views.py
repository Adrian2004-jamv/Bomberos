from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from instituciones.models import CuerpoBomberos

from .forms import CambioEstadoRecursoForm, RecursoForm
from .models import CategoriaRecurso, Recurso, TipoRecurso
from .permissions import (
    estaciones_permitidas,
    puede_consultar_inventario,
    puede_gestionar_inventario,
    puede_gestionar_recurso,
    recursos_permitidos,
)
from .services import actualizar_estado_recurso


def _recursos_base(usuario):
    return recursos_permitidos(usuario).select_related(
        "estacion",
        "estacion__cuerpo_bomberos",
        "estacion__cuerpo_bomberos__canton",
        "tipo",
        "tipo__categoria",
    )


def _exigir_consulta(usuario):
    if not puede_consultar_inventario(usuario):
        raise PermissionDenied


def _exigir_gestion(usuario):
    if not puede_gestionar_inventario(usuario):
        raise PermissionDenied


@login_required
def lista(request):
    _exigir_consulta(request.user)
    recursos = _recursos_base(request.user)
    busqueda = request.GET.get("q", "").strip()
    if busqueda:
        recursos = recursos.filter(
            Q(codigo_interno__icontains=busqueda)
            | Q(nombre__icontains=busqueda)
            | Q(marca__icontains=busqueda)
            | Q(modelo__icontains=busqueda)
            | Q(numero_serie__icontains=busqueda)
        )

    filtros = {
        "estacion_id": "estacion_id",
        "cuerpo_id": "estacion__cuerpo_bomberos_id",
        "categoria_id": "tipo__categoria_id",
        "tipo_id": "tipo_id",
        "estado": "estado_operativo",
        "disponibilidad": "disponibilidad",
    }
    for parametro, campo in filtros.items():
        valor = request.GET.get(parametro, "").strip()
        if valor:
            recursos = recursos.filter(**{campo: valor})

    activo = request.GET.get("activo", "").strip()
    if activo in {"true", "false"}:
        recursos = recursos.filter(activo=activo == "true")

    recursos = recursos.order_by(
        "estacion__cuerpo_bomberos__nombre",
        "tipo__categoria__nombre",
        "tipo__nombre",
        "codigo_interno",
        "pk",
    ).distinct()
    estaciones = estaciones_permitidas(request.user).order_by(
        "cuerpo_bomberos__nombre", "nombre"
    )
    cuerpos = CuerpoBomberos.objects.filter(estaciones__in=estaciones).distinct().order_by(
        "nombre"
    )
    contexto = {
            "recursos": recursos,
            "estaciones": estaciones,
            "cuerpos": cuerpos,
            "categorias": CategoriaRecurso.objects.filter(activo=True),
            "tipos": TipoRecurso.objects.filter(activo=True).select_related("categoria"),
            "estados": Recurso.EstadoOperativo.choices,
            "disponibilidades": Recurso.Disponibilidad.choices,
            "puede_gestionar": puede_gestionar_inventario(request.user),
            "filtros_activos": bool(request.GET),
    }
    plantilla = (
        "inventario/_resultados.html"
        if request.headers.get("HX-Request") == "true"
        else "inventario/lista.html"
    )
    return render(request, plantilla, contexto)


@login_required
def detalle(request, pk):
    _exigir_consulta(request.user)
    recurso = get_object_or_404(_recursos_base(request.user), pk=pk)
    return render(
        request,
        "inventario/detalle.html",
        {
            "recurso": recurso,
            "historial_reciente": recurso.historial_estados.select_related(
                "registrado_por"
            )[:5],
            "puede_gestionar": puede_gestionar_recurso(request.user, recurso),
        },
    )


@login_required
def crear(request):
    _exigir_gestion(request.user)
    form = RecursoForm(request.POST or None, usuario=request.user)
    catalogos_disponibles = form.fields["tipo"].queryset.exists()
    if request.method == "POST" and form.is_valid():
        recurso = form.save()
        messages.success(request, "El recurso fue registrado correctamente.")
        return redirect("inventario:detalle", pk=recurso.pk)
    return render(
        request,
        "inventario/formulario_recurso.html",
        {
            "form": form,
            "titulo": "Registrar recurso",
            "catalogos_disponibles": catalogos_disponibles,
        },
    )


@login_required
def editar(request, pk):
    _exigir_gestion(request.user)
    recurso = get_object_or_404(_recursos_base(request.user), pk=pk)
    if not puede_gestionar_recurso(request.user, recurso):
        raise PermissionDenied
    form = RecursoForm(request.POST or None, instance=recurso, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "La información descriptiva del recurso fue actualizada.")
        return redirect("inventario:detalle", pk=recurso.pk)
    return render(
        request,
        "inventario/formulario_recurso.html",
        {"form": form, "recurso": recurso, "titulo": "Editar recurso", "catalogos_disponibles": True},
    )


@login_required
def cambiar_estado(request, pk):
    _exigir_gestion(request.user)
    recurso = get_object_or_404(_recursos_base(request.user), pk=pk)
    if not puede_gestionar_recurso(request.user, recurso):
        raise PermissionDenied
    form = CambioEstadoRecursoForm(request.POST or None, recurso=recurso)
    if request.method == "POST" and form.is_valid():
        try:
            recurso, registro = actualizar_estado_recurso(
                recurso=recurso,
                nuevo_estado_operativo=form.cleaned_data["nuevo_estado_operativo"],
                nueva_disponibilidad=form.cleaned_data["nueva_disponibilidad"],
                usuario_responsable=request.user,
                motivo=form.cleaned_data["motivo"],
                observaciones=form.cleaned_data["observaciones"],
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            if registro is None:
                messages.info(request, "No se registró historial porque no existieron cambios.")
            else:
                messages.success(request, "El estado del recurso fue actualizado y registrado.")
            return redirect("inventario:detalle", pk=recurso.pk)
    return render(
        request,
        "inventario/cambio_estado.html",
        {"form": form, "recurso": recurso},
    )


@login_required
@require_GET
def historial(request, pk):
    _exigir_consulta(request.user)
    recurso = get_object_or_404(_recursos_base(request.user), pk=pk)
    registros = recurso.historial_estados.select_related("registrado_por")
    pagina = Paginator(registros, 20).get_page(request.GET.get("pagina"))
    return render(
        request,
        "inventario/historial.html",
        {"recurso": recurso, "registros": pagina, "pagina": pagina},
    )
