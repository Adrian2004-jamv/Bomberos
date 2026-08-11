from django import forms

from .models import CuerpoBomberos, Estacion


class FormularioInstitucionalMixin:
    """Aplica atributos visuales comunes sin alterar los campos del modelo."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class CuerpoBomberosForm(FormularioInstitucionalMixin, forms.ModelForm):
    class Meta:
        model = CuerpoBomberos
        fields = (
            "canton",
            "nombre",
            "sigla",
            "ruc",
            "direccion",
            "telefono",
            "correo",
            "sitio_web",
            "activo",
        )
        labels = {
            "canton": "Cantón",
            "ruc": "RUC",
            "correo": "Correo electrónico",
            "sitio_web": "Sitio web",
        }
        help_texts = {
            "sigla": "Identificador institucional único, por ejemplo CBL.",
            "ruc": "Ingrese los 13 dígitos del RUC institucional.",
            "sitio_web": "Incluya https:// si registra una dirección web.",
        }
        widgets = {
            "nombre": forms.TextInput(attrs={"autocomplete": "organization"}),
            "sigla": forms.TextInput(attrs={"autocomplete": "off"}),
            "ruc": forms.TextInput(
                attrs={"inputmode": "numeric", "maxlength": "13", "autocomplete": "off"}
            ),
            "direccion": forms.TextInput(attrs={"autocomplete": "street-address"}),
            "telefono": forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel"}),
            "correo": forms.EmailInput(attrs={"autocomplete": "email"}),
            "sitio_web": forms.URLInput(attrs={"placeholder": "https://"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }


class EstacionForm(FormularioInstitucionalMixin, forms.ModelForm):
    class Meta:
        model = Estacion
        fields = (
            "nombre",
            "codigo",
            "direccion",
            "telefono",
            "latitud",
            "longitud",
            "activo",
        )
        labels = {
            "codigo": "Código",
            "direccion": "Dirección",
            "telefono": "Teléfono",
        }
        help_texts = {
            "codigo": "Debe ser único dentro del Cuerpo de Bomberos.",
            "latitud": "Valor decimal entre -90 y 90.",
            "longitud": "Valor decimal entre -180 y 180.",
        }
        widgets = {
            "nombre": forms.TextInput(attrs={"autocomplete": "organization"}),
            "codigo": forms.TextInput(attrs={"autocomplete": "off"}),
            "direccion": forms.TextInput(attrs={"autocomplete": "street-address"}),
            "telefono": forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel"}),
            "latitud": forms.NumberInput(attrs={"step": "0.000001", "inputmode": "decimal"}),
            "longitud": forms.NumberInput(attrs={"step": "0.000001", "inputmode": "decimal"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }
