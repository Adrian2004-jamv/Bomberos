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

# Catálogo de tipos de emergencia. Es la única lista: la usan el formulario de
# registro, el filtro del listado y la simbología del mapa, que asigna un icono
# y un color a cada uno. Agregar un tipo aquí exige darle su icono en
# static/emergencias/js/mapa_incidentes.js y su color en la hoja del mapa.
TIPOS_EMERGENCIA = (
    "Incendio forestal",
    "Incendio estructural",
    "Rescate",
    "Accidente vehicular",
    "Inundación",
    "Materiales peligrosos",
    "Emergencia médica",
)
OPCIONES_TIPO_EMERGENCIA = tuple((tipo, tipo) for tipo in TIPOS_EMERGENCIA)

WIDGETS_EMERGENCIA = {
    "descripcion": forms.Textarea(attrs={"rows": 4}),
    "fecha_reporte": forms.DateTimeInput(
        attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
    ),
    "latitud": forms.NumberInput(attrs={"step": "0.000001", "data-ubicacion-latitud": ""}),
    "longitud": forms.NumberInput(attrs={"step": "0.000001", "data-ubicacion-longitud": ""}),
}


def _preparar_tipo_emergencia(formulario):
    """Convierte el tipo en una lista cerrada sin descartar lo ya registrado.

    El catálogo se fijó después de que el sistema estuviera en uso, y hay
    emergencias con descripciones más específicas («Rescate en altura»). Si el
    valor guardado no está en la lista se agrega solo para ese formulario: de lo
    contrario, editar una emergencia antigua obligaría a reclasificarla.
    """
    anterior = formulario.fields["tipo_emergencia"]
    opciones = list(OPCIONES_TIPO_EMERGENCIA)
    actual = getattr(formulario.instance, "tipo_emergencia", "") or ""
    if actual and actual not in TIPOS_EMERGENCIA:
        opciones.append((actual, f"{actual} (registro anterior)"))
    # Se reemplaza el campo entero y no solo el widget: un CharField con la
    # lista puesta en el widget dibuja el desplegable pero acepta cualquier
    # valor enviado, de modo que no habria validacion real.
    formulario.fields["tipo_emergencia"] = forms.ChoiceField(
        label=anterior.label,
        required=anterior.required,
        choices=[("", "Seleccione el tipo")] + opciones,
    )


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
        _preparar_tipo_emergencia(self)
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
        _preparar_tipo_emergencia(self)
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
    OPCIONES_FILTRO_TIPO = (("", "Todos"),) + OPCIONES_TIPO_EMERGENCIA

    q = forms.CharField(
        label="Buscar emergencias",
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
        choices=OPCIONES_FILTRO_TIPO,
        widget=forms.Select(attrs={"data-incident-emergency-type": ""}),
    )
    desde = forms.DateField(
        label="Desde",
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "data-incident-date": ""}),
        error_messages={"invalid": "Indique la fecha inicial con el formato AAAA-MM-DD."},
    )
    hasta = forms.DateField(
        label="Hasta",
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "data-incident-date": ""}),
        error_messages={"invalid": "Indique la fecha final con el formato AAAA-MM-DD."},
    )
    fase = forms.ChoiceField(required=False, choices=FASES, widget=forms.HiddenInput)

    def clean_q(self):
        return self.cleaned_data["q"].strip()

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get("desde"), datos.get("hasta")
        if desde and hasta and desde > hasta:
            # Se señala el campo final porque es el que el usuario acaba de
            # elegir en el flujo habitual.
            self.add_error("hasta", "La fecha final no puede ser anterior a la inicial.")
        return datos


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
