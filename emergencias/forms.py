from datetime import timedelta

from django import forms
from django.utils import timezone

from core.forms import preparar_campos
from inventario.permissions import estaciones_permitidas

from .models import Emergencia
from .services import unidades_desplegables


# El navegador envía la fecha con precisión de minuto, así que un registro hecho
# en el minuto corriente puede llegar unos segundos "adelantado".
TOLERANCIA_FECHA_REPORTE = timedelta(minutes=1)

WIDGETS_EMERGENCIA = {
    "descripcion": forms.Textarea(attrs={"rows": 4}),
    "fecha_reporte": forms.DateTimeInput(
        attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
    ),
    "latitud": forms.NumberInput(attrs={"step": "0.000001"}),
    "longitud": forms.NumberInput(attrs={"step": "0.000001"}),
}


class EmergenciaForm(forms.ModelForm):
    class Meta:
        model = Emergencia
        fields = (
            "tipo_emergencia",
            "descripcion",
            "prioridad",
            "fecha_reporte",
            "direccion",
            "latitud",
            "longitud",
            "estacion_responsable",
        )
        widgets = WIDGETS_EMERGENCIA

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estacion_responsable"].queryset = estaciones_permitidas(usuario).order_by(
            "cuerpo_bomberos__nombre", "nombre"
        )
        self.fields["fecha_reporte"].input_formats = ("%Y-%m-%dT%H:%M",)
        preparar_campos(self.fields)

    def clean_fecha_reporte(self):
        """Una fecha futura dejaría la emergencia sin poder cerrarse.

        El cierre escribe ``fecha_cierre`` con la hora del sistema y la base
        exige que no sea anterior al reporte.
        """
        fecha = self.cleaned_data["fecha_reporte"]
        if fecha and fecha > timezone.now() + TOLERANCIA_FECHA_REPORTE:
            raise forms.ValidationError("La fecha del reporte no puede estar en el futuro.")
        return fecha


class EmergenciaEdicionForm(forms.ModelForm):
    """Corrección de la información situacional de un incidente en curso.

    Deja fuera código, estación responsable, fecha de reporte y estado: son la
    identidad y la trazabilidad del registro. El estado se mueve por
    ``cambiar_estado_emergencia``, que valida cada transición.
    """

    class Meta:
        model = Emergencia
        fields = (
            "tipo_emergencia",
            "descripcion",
            "prioridad",
            "direccion",
            "latitud",
            "longitud",
        )
        widgets = WIDGETS_EMERGENCIA

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        preparar_campos(self.fields)


class FiltroIncidentesForm(forms.Form):
    """Filtros del registro de incidentes, resueltos en el servidor.

    Antes vivían en JavaScript sobre las filas ya dibujadas, lo que obligaba a
    traer el padrón completo y era incompatible con paginar.
    """

    FASES = (
        ("", "Todas"),
        ("curso", "En curso"),
        ("terminada", "Terminadas"),
    )
    ETAPAS = (
        ("", "Todas"),
        ("sin_iniciar", "Sin iniciar"),
        ("en_elaboracion", "En elaboración"),
        ("completa", "Completa"),
    )
    TIPOS_EMERGENCIA = (
        ("", "Todos"),
        ("Incendio forestal", "Incendio forestal"),
        ("Incendio estructural", "Incendio estructural"),
        ("Rescate", "Rescate"),
        ("Accidente vehicular", "Accidente vehicular"),
        ("Inundación", "Inundación"),
        ("Materiales peligrosos", "Materiales peligrosos"),
        ("Emergencia médica", "Emergencia médica"),
    )

    q = forms.CharField(
        label="Buscar incidentes",
        required=False,
        max_length=120,
        widget=forms.TextInput(attrs={
            "placeholder": "Buscar código, tipo, estación o dirección…",
            "type": "search",
        }),
    )
    etapa = forms.ChoiceField(
        label="Etapa SCI",
        required=False,
        choices=ETAPAS,
        # El guion de la página envía el formulario al cambiar esta selección,
        # para no obligar a pulsar «Filtrar».
        widget=forms.Select(attrs={"data-incident-document-stage": ""}),
    )
    tipo = forms.ChoiceField(
        label="Tipo de emergencia",
        required=False,
        choices=TIPOS_EMERGENCIA,
        widget=forms.Select(attrs={"data-incident-emergency-type": ""}),
    )
    fase = forms.ChoiceField(required=False, choices=FASES, widget=forms.HiddenInput)

    def clean_q(self):
        return self.cleaned_data["q"].strip()


class UnidadDesplegableChoiceField(forms.ModelChoiceField):
    """Identifica cada unidad por su estación.

    El código interno solo es único dentro de una estación, de modo que un
    usuario provincial vería varias «AB-01» indistinguibles.
    """

    def label_from_instance(self, obj):
        return f"{obj.codigo_interno} - {obj.nombre} ({obj.estacion.nombre})"


class DespachoUnidadForm(forms.Form):
    """Selección de la unidad que se despacha al incidente.

    La lista solo filtra lo que el usuario puede ver; quien decide es
    ``desplegar_unidad``, que vuelve a comprobar todo con la fila bloqueada.
    """

    unidad = UnidadDesplegableChoiceField(
        label="Unidad disponible",
        queryset=None,
        empty_label="Seleccione una unidad",
        error_messages={
            "invalid_choice": "La unidad ya no está disponible para despacharse.",
        },
    )
    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Quedan registradas en el despliegue y en el historial del recurso.",
    )

    def __init__(self, *args, emergencia, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unidad"].queryset = unidades_desplegables(emergencia, usuario)
        preparar_campos(self.fields)
