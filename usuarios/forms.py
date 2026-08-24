from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.db.models import Q

from core.forms import preparar_campos

from .models import Usuario
from .permissions import (
    GRUPO_SISTEMAS_INSTITUCIONAL,
    GRUPOS_CREABLES_INSTITUCION,
    estaciones_asignables,
)


CAMPOS_PERFIL = (
    "first_name", "last_name", "cedula", "email", "telefono",
    "cargo_institucional", "estacion",
)


def grupos_asignables(usuario_gestor):
    """Roles que este gestor puede otorgar.

    Solo el superusuario reparte los dos roles que amplían el alcance más allá
    de una institución; el operador de sistemas se limita a los operativos.
    """
    disponibles = list(GRUPOS_CREABLES_INSTITUCION)
    if usuario_gestor.is_superuser:
        disponibles.extend((GRUPO_SISTEMAS_INSTITUCIONAL, "Responsable provincial"))
    return Group.objects.filter(name__in=disponibles).order_by("name")


def _preparar_campos(formulario, usuario_gestor):
    formulario.fields["estacion"].queryset = estaciones_asignables(usuario_gestor)
    formulario.fields["grupo"].queryset = grupos_asignables(usuario_gestor)
    preparar_campos(formulario.fields, clase="user-form-control")


class UsuarioInstitucionalForm(UserCreationForm):
    grupo = forms.ModelChoiceField(label="Rol operativo", queryset=Group.objects.none())

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("username",) + CAMPOS_PERFIL + ("grupo", "password1", "password2")

    def __init__(self, *args, usuario_gestor, **kwargs):
        super().__init__(*args, **kwargs)
        _preparar_campos(self, usuario_gestor)

    def save(self, commit=True):
        usuario = super().save(commit=False)
        # La clave la eligió el gestor, así que la cuenta nace obligada a
        # reemplazarla en el primer ingreso.
        usuario.debe_cambiar_clave = True
        if commit:
            usuario.save()
            usuario.groups.set([self.cleaned_data["grupo"]])
        return usuario


class UsuarioEdicionForm(forms.ModelForm):
    """Corrige los datos de una cuenta existente.

    Deja fuera el nombre de usuario, que es la identidad con la que se ingresa,
    y la clave, que tiene su propio formulario.
    """

    grupo = forms.ModelChoiceField(label="Rol operativo", queryset=Group.objects.none())

    class Meta:
        model = Usuario
        fields = CAMPOS_PERFIL

    def __init__(self, *args, usuario_gestor, **kwargs):
        super().__init__(*args, **kwargs)
        _preparar_campos(self, usuario_gestor)
        actual = self.instance.groups.first()
        # El rol vigente siempre debe poder conservarse. Un gestor no otorga
        # «Administrador del sistema», pero corregir un teléfono de esa cuenta
        # no puede degradarla por no encontrar su rol en la lista.
        if actual is not None:
            self.fields["grupo"].queryset = Group.objects.filter(
                Q(pk__in=grupos_asignables(usuario_gestor)) | Q(pk=actual.pk)
            ).order_by("name")
        self.fields["grupo"].initial = actual

    def save(self, commit=True):
        usuario = super().save(commit=commit)
        if commit:
            usuario.groups.set([self.cleaned_data["grupo"]])
        return usuario
