from django import forms
from django.forms import inlineformset_factory

from .models import FormularioSCI211, RegistroRecursoSCI211


class FormularioSCI211Form(forms.ModelForm):
    class Meta:
        model = FormularioSCI211
        fields = ("punto_registro", "preparado_por_nombre")
        widgets = {"punto_registro": forms.TextInput(attrs={"autocomplete": "organization"})}


class RegistroRecursoSCI211Form(forms.ModelForm):
    class Meta:
        model = RegistroRecursoSCI211
        exclude = ("formulario", "despliegue", "orden")
        widgets = {
            "fecha_hora_solicitud": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "fecha_hora_arribo": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "fecha_hora_desmovilizacion": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }


RegistroRecursoSCI211FormSet = inlineformset_factory(
    FormularioSCI211, RegistroRecursoSCI211, form=RegistroRecursoSCI211Form,
    extra=1, can_delete=True, min_num=1, validate_min=True,
)
