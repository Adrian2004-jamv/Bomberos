from django import forms
from django.core.exceptions import ValidationError
from django.db import models

from core.forms import preparar_campos

from .models import CategoriaRecurso, Recurso, TipoRecurso
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
        preparar_campos(self.fields)

    def clean_estacion(self):
        estacion = self.cleaned_data["estacion"]
        if self.instance and self.instance.pk and estacion.pk != self.instance.estacion_id:
            raise ValidationError("No puede trasladar el recurso desde este formulario.")
        return estacion

# El modelo guarda dos columnas —estado operativo y disponibilidad— y la
# distincion es correcta: un camion puede estar operativo y aun asi no
# disponible porque esta asignado a otra emergencia. Pero pedirle a un bombero
# que elija las dos por separado le exige entender esa diferencia justo cuando
# tiene prisa, y de ahi salen combinaciones sin sentido: «fuera de servicio» y
# «disponible» a la vez.
#
# El formulario ofrece una sola lista en lenguaje de cuartel y aqui se traduce
# a las dos columnas. La combinacion imposible deja de poder elegirse.
SITUACIONES_DEL_RECURSO = (
    ("lista", "Operativa y lista para salir"),
    ("mantenimiento", "En mantenimiento"),
    ("averiada", "Averiada, no puede salir"),
    ("asignada", "Asignada a una emergencia"),
)

EQUIVALENCIA_DE_SITUACION = {
    "lista": (Recurso.EstadoOperativo.OPERATIVO, Recurso.Disponibilidad.DISPONIBLE),
    "mantenimiento": (Recurso.EstadoOperativo.MANTENIMIENTO, Recurso.Disponibilidad.NO_DISPONIBLE),
    "averiada": (Recurso.EstadoOperativo.FUERA_SERVICIO, Recurso.Disponibilidad.NO_DISPONIBLE),
    "asignada": (Recurso.EstadoOperativo.OPERATIVO, Recurso.Disponibilidad.ASIGNADO),
}


def situacion_de(recurso):
    """La opcion de la lista que corresponde al estado guardado del recurso.

    Las dos columnas admiten combinaciones que la lista no nombra —un recurso
    dado de baja, o reservado—. En ese caso no se preselecciona nada: es
    preferible que el usuario elija a que el formulario le cambie el estado sin
    que se de cuenta.
    """
    actual = (recurso.estado_operativo, recurso.disponibilidad)
    for clave, equivalencia in EQUIVALENCIA_DE_SITUACION.items():
        if equivalencia == actual:
            return clave
    return None


class CambioEstadoRecursoForm(forms.Form):
    situacion = forms.ChoiceField(
        label="¿Cómo está la unidad?",
        choices=SITUACIONES_DEL_RECURSO,
        help_text="El sistema traduce esta respuesta al estado y la disponibilidad del recurso.",
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
            situacion = situacion_de(recurso)
            if situacion:
                self.initial["situacion"] = situacion
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def estado_y_disponibilidad(self):
        """Traduce la respuesta a las dos columnas que guarda el modelo."""
        return EQUIVALENCIA_DE_SITUACION[self.cleaned_data["situacion"]]

class CategoriaRecursoForm(forms.ModelForm):
    class Meta:
        model = CategoriaRecurso
        fields = ("nombre", "codigo", "descripcion", "activo")
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3})}
        help_texts = {
            "activo": "Una categoría inactiva deja de ofrecerse al registrar tipos nuevos.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        preparar_campos(self.fields)

    def clean_codigo(self):
        return self.cleaned_data["codigo"].strip().upper()

class TipoRecursoForm(forms.ModelForm):
    class Meta:
        model = TipoRecurso
        fields = ("categoria", "nombre", "codigo", "descripcion",
                  "es_unidad_desplegable", "activo")
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3})}
        help_texts = {
            "activo": "Un tipo inactivo se conserva en los recursos ya registrados.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Una categoría desactivada no debe recibir tipos nuevos, pero sí seguir
        # apareciendo si es la del tipo que se está editando.
        categorias = CategoriaRecurso.objects.filter(activo=True)
        if self.instance.pk and self.instance.categoria_id:
            categorias = CategoriaRecurso.objects.filter(
                models.Q(activo=True) | models.Q(pk=self.instance.categoria_id)
            )
        self.fields["categoria"].queryset = categorias.order_by("nombre")
        preparar_campos(self.fields)

    def clean_codigo(self):
        return self.cleaned_data["codigo"].strip().upper()
