from django import forms

from instituciones.models import CuerpoBomberos, Estacion

from .models import EvaluacionCapacidadEstacion, TipoCapacidadOperativa
from .permissions import estaciones_capacidades_permitidas, tiene_alcance_global


class EvaluacionCapacidadForm(forms.Form):
    estacion = forms.ModelChoiceField(label="Estación", queryset=Estacion.objects.none())
    tipo_capacidad = forms.ModelChoiceField(
        label="Capacidad operativa",
        queryset=TipoCapacidadOperativa.objects.none(),
    )
    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def __init__(self, *args, usuario, capacidad_inicial=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estacion"].queryset = estaciones_capacidades_permitidas(
            usuario
        ).order_by("cuerpo_bomberos__nombre", "nombre")
        self.fields["tipo_capacidad"].queryset = TipoCapacidadOperativa.objects.filter(
            activo=True
        ).order_by("nombre")
        if capacidad_inicial and not self.is_bound:
            self.initial["tipo_capacidad"] = capacidad_inicial
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class FiltroHistorialCapacidadForm(forms.Form):
    institucion = forms.ModelChoiceField(
        label="Institución",
        queryset=CuerpoBomberos.objects.none(),
        required=False,
        empty_label="Todas las instituciones",
    )
    estacion = forms.ModelChoiceField(
        label="Estación",
        queryset=Estacion.objects.none(),
        required=False,
        empty_label="Todas las estaciones",
    )
    capacidad = forms.ModelChoiceField(
        label="Capacidad",
        queryset=TipoCapacidadOperativa.objects.none(),
        required=False,
        empty_label="Todas las capacidades",
    )
    estado = forms.ChoiceField(
        label="Resultado",
        required=False,
        choices=(("", "Todos los resultados"), *EvaluacionCapacidadEstacion.Estado.choices),
    )
    fecha_desde = forms.DateField(
        label="Desde",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    fecha_hasta = forms.DateField(
        label="Hasta",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        estaciones = estaciones_capacidades_permitidas(usuario).order_by(
            "cuerpo_bomberos__nombre", "nombre"
        )
        self.fields["estacion"].queryset = estaciones
        self.fields["capacidad"].queryset = TipoCapacidadOperativa.objects.order_by("nombre")
        if tiene_alcance_global(usuario):
            self.fields["institucion"].queryset = CuerpoBomberos.objects.filter(
                estaciones__in=estaciones
            ).distinct().order_by("nombre")
        else:
            del self.fields["institucion"]
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean(self):
        datos = super().clean()
        desde = datos.get("fecha_desde")
        hasta = datos.get("fecha_hasta")
        if desde and hasta and hasta < desde:
            self.add_error("fecha_hasta", "La fecha final no puede ser anterior a la inicial.")
        return datos
