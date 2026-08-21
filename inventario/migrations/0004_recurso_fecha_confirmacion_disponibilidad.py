from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventario", "0003_tiporecurso_es_unidad_desplegable")]

    operations = [
        migrations.AddField(
            model_name="recurso",
            name="fecha_confirmacion_disponibilidad",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="fecha de confirmación de disponibilidad",
            ),
        ),
    ]
