from django import forms
from django.core.exceptions import ValidationError

from .models import Recurso, TipoRecurso
from .permissions import estaciones_permitidas


class RecursoForm(forms.ModelForm):
    class Meta:
        model = Recurso
        fields = (
            "estacion",
            "tipo",
            "codigo_interno",
            "nombre",
            "descripcion",
            "marca",
            "modelo",
            "numero_serie",
            "anio_fabricacion",
            "observaciones",
            "activo",
        )
        labels = {
            "estacion": "Estación",
            "tipo": "Tipo de recurso",
            "codigo_interno": "Código interno",
            "descripcion": "Descripción",
            "numero_serie": "Número de serie",
            "anio_fabricacion": "Año de fabricación",
        }
        help_texts = {
            "codigo_interno": "Debe ser único dentro de la estación.",
            "anio_fabricacion": "Ingrese el año con cuatro dígitos.",
        }
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
            "anio_fabricacion": forms.NumberInput(attrs={"min": "0", "inputmode": "numeric"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        permitidas = estaciones_permitidas(usuario)
        if self.instance and self.instance.pk:
            permitidas = permitidas.filter(pk=self.instance.estacion_id)
            self.fields["estacion"].disabled = True
            self.fields["estacion"].help_text = (
                "Los movimientos entre estaciones se gestionarán en un módulo posterior."
            )
        self.fields["estacion"].queryset = permitidas.order_by(
            "cuerpo_bomberos__nombre", "nombre"
        )
        self.fields["tipo"].queryset = TipoRecurso.objects.filter(activo=True).select_related(
            "categoria"
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_estacion(self):
        estacion = self.cleaned_data["estacion"]
        if self.instance and self.instance.pk and estacion.pk != self.instance.estacion_id:
            raise ValidationError("No puede trasladar el recurso desde este formulario.")
        return estacion


class CambioEstadoRecursoForm(forms.Form):
    nuevo_estado_operativo = forms.ChoiceField(
        label="Nuevo estado operativo", choices=Recurso.EstadoOperativo.choices
    )
    nueva_disponibilidad = forms.ChoiceField(
        label="Nueva disponibilidad", choices=Recurso.Disponibilidad.choices
    )
    motivo = forms.CharField(
        label="Motivo",
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Explique la razón del cambio"}),
    )
    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, recurso=None, **kwargs):
        super().__init__(*args, **kwargs)
        if recurso and not self.is_bound:
            self.initial.update(
                {
                    "nuevo_estado_operativo": recurso.estado_operativo,
                    "nueva_disponibilidad": recurso.disponibilidad,
                }
            )
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
