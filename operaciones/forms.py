from django import forms
from django.db.models import Q

from instituciones.models import CuerpoBomberos, Estacion
from core.forms import preparar_campos
from inventario.models import TipoRecurso

from .models import (EvaluacionCapacidadEstacion, RequisitoRecursoCapacidad,
                     TipoCapacidadOperativa)
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
        preparar_campos(self.fields)


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
        preparar_campos(self.fields)

    def clean(self):
        datos = super().clean()
        desde = datos.get("fecha_desde")
        hasta = datos.get("fecha_hasta")
        if desde and hasta and hasta < desde:
            self.add_error("fecha_hasta", "La fecha final no puede ser anterior a la inicial.")
        return datos


class TipoCapacidadOperativaForm(forms.ModelForm):
    class Meta:
        model = TipoCapacidadOperativa
        fields = ("nombre", "codigo", "descripcion", "activo")
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4})}
        help_texts = {
            "activo": "Una capacidad inactiva conserva sus evaluaciones históricas.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        preparar_campos(self.fields)

    def clean_codigo(self):
        return self.cleaned_data["codigo"].strip().upper()


class RequisitoRecursoCapacidadForm(forms.ModelForm):
    class Meta:
        model = RequisitoRecursoCapacidad
        fields = ("tipo_recurso", "cantidad_minima", "obligatorio", "observaciones")
        widgets = {"observaciones": forms.TextInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Un tipo desactivado no debe sumarse a requisitos nuevos, pero el que ya
        # forma parte de la capacidad tiene que seguir siendo visible y editable.
        tipos = TipoRecurso.objects.filter(activo=True)
        if self.instance.pk and self.instance.tipo_recurso_id:
            tipos = TipoRecurso.objects.filter(
                Q(activo=True) | Q(pk=self.instance.tipo_recurso_id)
            )
        self.fields["tipo_recurso"].queryset = tipos.select_related(
            "categoria"
        ).order_by("categoria__nombre", "nombre")
        preparar_campos(self.fields)

    def has_changed(self):
        """Una fila nueva cuenta como usada solo si trae recurso o cantidad.

        ``obligatorio`` nace marcado por el valor por omisión del modelo, de
        modo que una casilla que el usuario nunca tocó se ve como un cambio y
        arrastraría la fila en blanco a la validación, exigiendo los campos que
        justamente quedaron vacíos.
        """
        if self.instance.pk:
            return super().has_changed()
        return any(
            self.data.get(self.add_prefix(campo))
            for campo in ("tipo_recurso", "cantidad_minima")
        )


RequisitoCapacidadFormSet = forms.inlineformset_factory(
    TipoCapacidadOperativa,
    RequisitoRecursoCapacidad,
    form=RequisitoRecursoCapacidadForm,
    extra=3,
    can_delete=True,
)
