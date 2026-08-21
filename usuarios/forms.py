from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group

from .models import Usuario
from .permissions import (
    GRUPO_SISTEMAS_INSTITUCIONAL,
    GRUPOS_CREABLES_INSTITUCION,
    estaciones_asignables,
)


class UsuarioInstitucionalForm(UserCreationForm):
    grupo = forms.ModelChoiceField(label="Rol operativo", queryset=Group.objects.none())

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = (
            "username", "first_name", "last_name", "cedula", "email", "telefono",
            "cargo_institucional", "estacion", "grupo", "password1", "password2",
        )

    def __init__(self, *args, usuario_gestor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estacion"].queryset = estaciones_asignables(usuario_gestor)
        grupos_disponibles = list(GRUPOS_CREABLES_INSTITUCION)
        if usuario_gestor.is_superuser:
            grupos_disponibles.extend((GRUPO_SISTEMAS_INSTITUCIONAL, "Responsable provincial"))
        self.fields["grupo"].queryset = Group.objects.filter(
            name__in=grupos_disponibles
        ).order_by("name")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "user-form-control")

    def save(self, commit=True):
        usuario = super().save(commit=commit)
        if commit:
            usuario.groups.set([self.cleaned_data["grupo"]])
        return usuario
