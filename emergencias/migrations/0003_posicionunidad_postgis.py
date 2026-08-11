from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point
from django.db import migrations


def convertir_coordenadas_a_puntos(apps, schema_editor):
    PosicionUnidad = apps.get_model("emergencias", "PosicionUnidad")
    for posicion in PosicionUnidad.objects.only("pk", "latitud", "longitud").iterator():
        posicion.ubicacion = Point(
            float(posicion.longitud),
            float(posicion.latitud),
            srid=4326,
        )
        posicion.save(update_fields=("ubicacion",))


class Migration(migrations.Migration):
    dependencies = [("emergencias", "0002_posicionunidad")]

    operations = [
        migrations.AddField(
            model_name="posicionunidad",
            name="ubicacion",
            field=gis_models.PointField(null=True, srid=4326, spatial_index=True, verbose_name="ubicación"),
        ),
        migrations.RunPython(convertir_coordenadas_a_puntos, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="posicionunidad",
            name="ubicacion",
            field=gis_models.PointField(srid=4326, spatial_index=True, verbose_name="ubicación"),
        ),
        migrations.RemoveConstraint(model_name="posicionunidad", name="pos_latitud_valida"),
        migrations.RemoveConstraint(model_name="posicionunidad", name="pos_longitud_valida"),
        migrations.RemoveField(model_name="posicionunidad", name="latitud"),
        migrations.RemoveField(model_name="posicionunidad", name="longitud"),
    ]
