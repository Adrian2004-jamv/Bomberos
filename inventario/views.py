from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .forms import (CambioEstadoRecursoForm, CategoriaRecursoForm, RecursoForm,
                    TipoRecursoForm)
from .models import CategoriaRecurso, Recurso, TipoRecurso
from .permissions import puede_consultar_inventario, puede_gestionar_catalogos, puede_gestionar_inventario, puede_gestionar_recurso, recursos_permitidos
from .services import actualizar_estado_recurso

def recursos_base(usuario):
    return recursos_permitidos(usuario).select_related(
        "estacion",
        "estacion__cuerpo_bomberos",
        "estacion__cuerpo_bomberos__canton",
        "tipo",
        "tipo__categoria",
    )

def exigir_consulta(usuario):
    if not puede_consultar_inventario(usuario):
        raise PermissionDenied

def exigir_gestion(usuario):
    if not puede_gestionar_inventario(usuario):
        raise PermissionDenied

@login_required
def lista(request):
    exigir_consulta(request.user)
    recursos = recursos_base(request.user)
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
    contexto = {
            "recursos": recursos,
            "puede_gestionar": puede_gestionar_inventario(request.user),
    }
    plantilla = (
        "inventario/_resultados.html"
        if request.headers.get("HX-Request") == "true"
        else "inventario/lista.html"
    )
    return render(request, plantilla, contexto)

@login_required
def detalle(request, pk):
    exigir_consulta(request.user)
    recurso = get_object_or_404(recursos_base(request.user), pk=pk)
    contexto = {
            "recurso": recurso,
            "historial_reciente": recurso.historial_estados.select_related(
                "registrado_por"
            )[:5],
            "puede_gestionar": puede_gestionar_recurso(request.user, recurso),
        }

    return render(request, "inventario/detalle.html", contexto)

@login_required
def crear(request):
    exigir_gestion(request.user)
    form = RecursoForm(request.POST or None, usuario=request.user)
    catalogos_disponibles = form.fields["tipo"].queryset.exists()
    if request.method == "POST" and form.is_valid():
        recurso = form.save()
        messages.success(request, "El recurso fue registrado correctamente.")
        return redirect("inventario:detalle", pk=recurso.pk)
    contexto = {
            "form": form,
            "titulo": "Registrar recurso",
            "catalogos_disponibles": catalogos_disponibles,
        }

    return render(request, "inventario/formulario_recurso.html", contexto)

@login_required
def editar(request, pk):
    exigir_gestion(request.user)
    recurso = get_object_or_404(recursos_base(request.user), pk=pk)
    if not puede_gestionar_recurso(request.user, recurso):
        raise PermissionDenied
    form = RecursoForm(request.POST or None, instance=recurso, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "La información descriptiva del recurso fue actualizada.")
        return redirect("inventario:detalle", pk=recurso.pk)
    contexto = {"form": form, "recurso": recurso, "titulo": "Editar recurso", "catalogos_disponibles": True}

    return render(request, "inventario/formulario_recurso.html", contexto)

@login_required
def cambiar_estado(request, pk):
    exigir_gestion(request.user)
    recurso = get_object_or_404(recursos_base(request.user), pk=pk)
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
    contexto = {"form": form, "recurso": recurso}

    return render(request, "inventario/cambio_estado.html", contexto)

@login_required
@require_POST
def confirmar_disponibilidad(request, pk):
    """Confirma en un paso que el recurso está operativo y disponible."""
    exigir_gestion(request.user)
    recurso = get_object_or_404(recursos_base(request.user), pk=pk)
    if not puede_gestionar_recurso(request.user, recurso):
        raise PermissionDenied
    actualizar_estado_recurso(
        recurso=recurso,
        nuevo_estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
        nueva_disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
        usuario_responsable=request.user,
        motivo="Confirmación rápida de disponibilidad",
        confirmar_disponibilidad=True,
    )
    messages.success(request, f"{recurso.codigo_interno} quedó confirmado como operativo y disponible.")
    return redirect("inventario:lista")

@login_required
@require_GET
def historial(request, pk):
    exigir_consulta(request.user)
    recurso = get_object_or_404(recursos_base(request.user), pk=pk)
    registros = recurso.historial_estados.select_related("registrado_por")
    pagina = Paginator(registros, 20).get_page(request.GET.get("pagina"))
    contexto = {"recurso": recurso, "registros": pagina, "pagina": pagina}

    return render(request, "inventario/historial.html", contexto)

def exigir_catalogos(usuario):
    if not puede_gestionar_catalogos(usuario):
        raise PermissionDenied

@login_required
@require_GET
def catalogo(request):
    """Categorías y tipos de recurso, la base sobre la que se registra todo.

    Se muestran juntas porque un tipo no existe fuera de su categoría, y se
    indica cuántos recursos dependen de cada uno: es lo que explica por qué se
    desactivan en lugar de borrarse.
    """
    exigir_catalogos(request.user)
    categorias = CategoriaRecurso.objects.prefetch_related(
        Prefetch(
            "tipos_recurso",
            queryset=TipoRecurso.objects.annotate(
                cantidad_recursos=Count("recursos")
            ).order_by("nombre"),
        )
    ).annotate(cantidad_tipos=Count("tipos_recurso")).order_by("nombre")
    contexto = {"categorias": categorias}

    return render(request, "inventario/catalogo.html", contexto)

@login_required
def crear_categoria(request):
    exigir_catalogos(request.user)
    formulario = CategoriaRecursoForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        categoria = formulario.save()
        messages.success(request, f"La categoría {categoria.nombre} fue creada.")
        return redirect("inventario:catalogo")
    contexto = {
        "formulario": formulario,
        "titulo": "Nueva categoría",
        "encabezado": "Categoría de recursos",
        "descripcion": "Agrupa los tipos de recurso; por ejemplo vehículos, equipos o herramientas.",
        "accion": "Crear categoría",
    }

    return render(request, "inventario/formulario_catalogo.html", contexto)

@login_required
def editar_categoria(request, pk):
    exigir_catalogos(request.user)
    categoria = get_object_or_404(CategoriaRecurso, pk=pk)
    formulario = CategoriaRecursoForm(request.POST or None, instance=categoria)
    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, f"La categoría {categoria.nombre} fue actualizada.")
        return redirect("inventario:catalogo")
    contexto = {
        "formulario": formulario,
        "titulo": f"Editar {categoria.codigo}",
        "encabezado": categoria.nombre,
        "descripcion": "Los tipos y recursos que ya dependen de esta categoría conservan su vínculo.",
        "accion": "Guardar cambios",
    }

    return render(request, "inventario/formulario_catalogo.html", contexto)

@login_required
def crear_tipo(request):
    exigir_catalogos(request.user)
    formulario = TipoRecursoForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        tipo = formulario.save()
        messages.success(request, f"El tipo {tipo.nombre} fue creado.")
        return redirect("inventario:catalogo")
    contexto = {
        "formulario": formulario,
        "titulo": "Nuevo tipo de recurso",
        "encabezado": "Tipo de recurso",
        "descripcion": "Marque «es unidad desplegable» solo si los recursos de este tipo "
                       "pueden despacharse a una emergencia.",
        "accion": "Crear tipo",
    }

    return render(request, "inventario/formulario_catalogo.html", contexto)

@login_required
def editar_tipo(request, pk):
    exigir_catalogos(request.user)
    tipo = get_object_or_404(TipoRecurso, pk=pk)
    formulario = TipoRecursoForm(request.POST or None, instance=tipo)
    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, f"El tipo {tipo.nombre} fue actualizado.")
        return redirect("inventario:catalogo")
    contexto = {
        "formulario": formulario,
        "titulo": f"Editar {tipo.codigo}",
        "encabezado": tipo.nombre,
        "descripcion": "Retirar «es unidad desplegable» no afecta a los despliegues ya registrados.",
        "accion": "Guardar cambios",
    }

    return render(request, "inventario/formulario_catalogo.html", contexto)
