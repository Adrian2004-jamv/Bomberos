from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from .forms import UsuarioInstitucionalForm
from .permissions import puede_gestionar_usuarios, usuarios_administrables


@login_required
def lista(request):
    if not puede_gestionar_usuarios(request.user):
        raise PermissionDenied
    return render(
        request,
        "usuarios/lista.html",
        {"usuarios_gestionables": usuarios_administrables(request.user)},
    )


@login_required
def crear(request):
    if not puede_gestionar_usuarios(request.user):
        raise PermissionDenied
    formulario = UsuarioInstitucionalForm(
        request.POST or None,
        usuario_gestor=request.user,
    )
    if request.method == "POST" and formulario.is_valid():
        usuario = formulario.save()
        messages.success(request, f"La cuenta {usuario.username} fue creada correctamente.")
        return redirect("usuarios:lista")
    return render(request, "usuarios/formulario.html", {"formulario": formulario})
