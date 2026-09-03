"""Quita los espacios sobrantes del tipo de emergencia.

El tipo se capturaba como texto libre antes de convertirse en un desplegable,
y quedaron valores que solo se diferencian por un espacio al principio o al
final. En los filtros aparecían como dos opciones idénticas, y una emergencia
guardada con la variante no se encontraba al filtrar por la buena.
"""

from django.db import migrations
from django.db.models.functions import Trim


def normalizar(apps, schema_editor):
    Emergencia = apps.get_model("emergencias", "Emergencia")
    Emergencia.objects.update(tipo_emergencia=Trim("tipo_emergencia"))


def sin_vuelta_atras(apps, schema_editor):
    """No se restauran: los espacios sobrantes no eran un dato."""


class Migration(migrations.Migration):

    dependencies = [
        ("emergencias", "0013_reabrir_sci211_de_emergencias_en_curso"),
    ]

    operations = [
        migrations.RunPython(normalizar, sin_vuelta_atras),
    ]
