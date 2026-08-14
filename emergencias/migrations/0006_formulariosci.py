import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("emergencias", "0005_remove_formulariosci211_preparado_por_nombre_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FormularioSCI",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo_sci", models.CharField(max_length=3, verbose_name="código SCI")),
                ("datos", models.JSONField(blank=True, default=dict)),
                ("fecha_creacion", models.DateTimeField(auto_now_add=True)),
                ("fecha_actualizacion", models.DateTimeField(auto_now=True)),
                ("creado_por", models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name="formularios_sci_creados", to=settings.AUTH_USER_MODEL)),
                ("emergencia", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="formularios_sci", to="emergencias.emergencia", verbose_name="emergencia")),
                ("modificado_por", models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name="formularios_sci_modificados", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "formulario SCI", "verbose_name_plural": "formularios SCI", "ordering": ("codigo_sci", "pk")},
        ),
        migrations.AddConstraint(
            model_name="formulariosci",
            constraint=models.UniqueConstraint(fields=("emergencia", "codigo_sci"), name="formulario_sci_unico_por_emergencia"),
        ),
    ]
