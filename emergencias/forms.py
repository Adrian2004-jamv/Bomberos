from django import forms

from inventario.permissions import estaciones_permitidas

from .models import Emergencia


class EmergenciaForm(forms.ModelForm):
    class Meta:
        model = Emergencia
        fields = (
            "codigo",
            "tipo_emergencia",
            "descripcion",
            "prioridad",
            "fecha_reporte",
            "direccion",
            "latitud",
            "longitud",
            "estacion_responsable",
        )
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 4}),
            "fecha_reporte": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "latitud": forms.NumberInput(attrs={"step": "0.000001"}),
            "longitud": forms.NumberInput(attrs={"step": "0.000001"}),
        }

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estacion_responsable"].queryset = estaciones_permitidas(usuario).order_by(
            "cuerpo_bomberos__nombre", "nombre"
        )
        self.fields["fecha_reporte"].input_formats = ("%Y-%m-%dT%H:%M",)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
