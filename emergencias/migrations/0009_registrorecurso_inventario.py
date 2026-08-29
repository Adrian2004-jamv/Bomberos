from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("emergencias", "0008_actualizar_codigos_incidentes"),
        ("inventario", "0004_recurso_fecha_confirmacion_disponibilidad"),
    ]

    operations = [
        migrations.AddField(
            model_name="registrorecursosci211",
            name="recurso_inventario",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="registros_sci211",
                to="inventario.recurso",
                verbose_name="recurso verificado del inventario",
            ),
        ),
    ]
