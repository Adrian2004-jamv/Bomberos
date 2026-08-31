"""Preparación común de los campos de formulario.

Reúne dos ajustes que todos los formularios del sistema necesitan: la clase de
estilo y la etiqueta de la opción vacía de cada selector.
"""

from django import forms
from django.db.models.fields import BLANK_CHOICE_LABEL

ETIQUETA_OPCION_VACIA = "Seleccione una opción"

def preparar_campos(campos, clase="form-control"):
    """Aplica la clase de estilo y traduce la opción vacía de los selectores.

    Django 6.1 rotula esa opción con un texto propio en lugar de la línea de
    guiones anterior, y la traducción al español todavía no lo cubre, de modo
    que aparecía en inglés dentro de una interfaz en español. Solo se sustituye
    cuando el formulario no eligió una etiqueta propia; ``USE_BLANK_CHOICE_DASH``
    resolvería lo mismo, pero está marcada para desaparecer en Django 7.
    """
    for field in campos.values():
        if not isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs.setdefault("class", clase)
        if isinstance(field, forms.ModelChoiceField) and str(
            field.empty_label or ""
        ) in (str(BLANK_CHOICE_LABEL), "---------"):
            field.empty_label = ETIQUETA_OPCION_VACIA
