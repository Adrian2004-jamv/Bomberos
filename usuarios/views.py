from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import UsuarioEdicionForm, UsuarioInstitucionalForm
from .permissions import puede_gestionar_usuarios, usuarios_administrables


def _exigir_gestion(usuario):
    if not puede_gestionar_usuarios(usuario):
        raise PermissionDenied


def _cuenta_administrable(usuario_gestor, pk):
    """Acota la cuenta al ámbito del gestor.

    ``usuarios_administrables`` excluye a los superusuarios, de modo que esa
    cuenta no se puede editar, desactivar ni intervenir desde aquí.
    """
    return get_object_or_404(usuarios_administrables(usuario_gestor), pk=pk)


@login_required
def lista(request):
    _exigir_gestion(request.user)
    return render(
        request,
        "usuarios/lista.html",
        {"usuarios_gestionables": usuarios_administrables(request.user)},
    )


@login_required
def crear(request):
    _exigir_gestion(request.user)
    formulario = UsuarioInstitucionalForm(
        request.POST or None,
        usuario_gestor=request.user,
    )
    if request.method == "POST" and formulario.is_valid():
        usuario = formulario.save()
        messages.success(
            request,
            f"La cuenta {usuario.username} fue creada correctamente. "
            "Deberá cambiar la clave en su primer ingreso.",
        )
        return redirect("usuarios:lista")
    return render(request, "usuarios/formulario.html", {
        "formulario": formulario,
        "titulo": "Nueva cuenta",
        "encabezado": "Datos del nuevo usuario",
        "descripcion": "La estación y el rol determinan la información que podrá consultar y gestionar.",
        "accion": "Crear cuenta",
        "icono": "ti-user-check",
    })


@login_required
def editar(request, pk):
    _exigir_gestion(request.user)
    cuenta = _cuenta_administrable(request.user, pk)
    formulario = UsuarioEdicionForm(
        request.POST or None,
        instance=cuenta,
        usuario_gestor=request.user,
    )
    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, f"La cuenta {cuenta.username} fue actualizada.")
        return redirect("usuarios:lista")
    return render(request, "usuarios/formulario.html", {
        "formulario": formulario,
        "cuenta": cuenta,
        "titulo": f"Editar {cuenta.username}",
        "encabezado": f"Datos de {cuenta.get_full_name() or cuenta.username}",
        "descripcion": "El nombre de usuario no cambia porque es la identidad con la que se ingresa.",
        "accion": "Guardar cambios",
        "icono": "ti-device-floppy",
    })


@login_required
@require_POST
def cambiar_actividad(request, pk):
    """Desactiva o reactiva una cuenta.

    No se borra: ``Usuario`` está protegido desde emergencias, despliegues e
    historial de inventario, y esos registros deben conservar a su responsable.
    """
    _exigir_gestion(request.user)
    cuenta = _cuenta_administrable(request.user, pk)
    if cuenta.pk == request.user.pk:
        messages.error(request, "No puede desactivar su propia cuenta.")
        return redirect("usuarios:lista")
    cuenta.is_active = not cuenta.is_active
    cuenta.save(update_fields=["is_active"])
    estado = "reactivada" if cuenta.is_active else "desactivada"
    messages.success(request, f"La cuenta {cuenta.username} fue {estado}.")
    return redirect("usuarios:lista")


@login_required
def restablecer_clave(request, pk):
    """Devuelve el acceso a quien olvidó su clave.

    La cuenta queda obligada a reemplazarla, porque quien la escribió aquí es
    el operador y no su titular.
    """
    _exigir_gestion(request.user)
    cuenta = _cuenta_administrable(request.user, pk)
    if cuenta.pk == request.user.pk:
        messages.info(request, "Para cambiar su propia clave use «Cambiar contraseña».")
        return redirect("usuarios:cambiar_clave")
    formulario = SetPasswordForm(cuenta, request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        usuario = formulario.save()
        usuario.debe_cambiar_clave = True
        usuario.save(update_fields=["debe_cambiar_clave"])
        messages.success(
            request,
            f"La clave de {usuario.username} fue restablecida. "
            "Deberá cambiarla en su próximo ingreso.",
        )
        return redirect("usuarios:lista")
    return render(request, "usuarios/restablecer_clave.html", {
        "formulario": formulario,
        "cuenta": cuenta,
    })


@login_required
def cambiar_clave(request):
    """Cambio de clave del propio usuario.

    Es la única salida cuando ``debe_cambiar_clave`` está activo, así que la
    plantilla explica el motivo y oculta la opción de cancelar.
    """
    obligatorio = request.user.debe_cambiar_clave
    formulario = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        usuario = formulario.save()
        usuario.debe_cambiar_clave = False
        usuario.save(update_fields=["debe_cambiar_clave"])
        # Sin esto, cambiar la clave invalida la sesión en curso.
        update_session_auth_hash(request, usuario)
        messages.success(request, "Su contraseña fue actualizada.")
        return redirect("emergencias:lista")
    return render(request, "usuarios/cambiar_clave.html", {
        "formulario": formulario,
        "obligatorio": obligatorio,
    })
