"""Fase 2 de «el periodo operacional es solo del SCI-201»: las restricciones.

La 0021 dejó los datos listos. Aquí la base empieza a exigirlo:

* Un SCI-201 por periodo; cualquier otro formulario, uno por emergencia y código.
* Solo el SCI-201 lleva periodo, y los demás no pueden llevarlo (CHECK).
* El SCI-211 vuelve a ser uno por emergencia y pierde su columna de periodo.
"""

from django.db import migrations, models


def sin_trabajo(apps, schema_editor):
    """Marcador: solo hace algo al revertir."""


def periodo_a_los_211(apps, schema_editor):
    """Al revertir: cada 211 vuelve al periodo vigente de su emergencia."""
    FormularioSCI211 = apps.get_model("emergencias", "FormularioSCI211")
    PeriodoOperacional = apps.get_model("emergencias", "PeriodoOperacional")
    for formulario in FormularioSCI211.objects.select_related("emergencia"):
        periodo = (
            PeriodoOperacional.objects.filter(emergencia=formulario.emergencia)
            .order_by("-numero").first()
        )
        if periodo is None:
            periodo = PeriodoOperacional.objects.create(
                emergencia=formulario.emergencia, numero=1,
                inicio=formulario.emergencia.fecha_reporte,
            )
        formulario.periodo = periodo
        formulario.save(update_fields=["periodo"])


class Migration(migrations.Migration):

    dependencies = [
        ("emergencias", "0021_periodo_solo_en_el_sci201"),
    ]

    operations = [
        # ── FormularioSCI ───────────────────────────────────────────────────
        migrations.RemoveConstraint(
            model_name="formulariosci",
            name="formulario_sci_unico_por_emergencia_y_periodo",
        ),
        migrations.AddConstraint(
            model_name="formulariosci",
            constraint=models.UniqueConstraint(
                condition=models.Q(("codigo_sci", "201"), _negated=True),
                fields=("emergencia", "codigo_sci"),
                name="formulario_sci_unico_por_emergencia",
            ),
        ),
        migrations.AddConstraint(
            model_name="formulariosci",
            constraint=models.UniqueConstraint(
                condition=models.Q(("codigo_sci", "201")),
                fields=("emergencia", "periodo"),
                name="formulario_sci201_unico_por_periodo",
            ),
        ),
        migrations.AddConstraint(
            model_name="formulariosci",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("codigo_sci", "201"), ("periodo__isnull", False)),
                    models.Q(models.Q(("codigo_sci", "201"), _negated=True),
                             ("periodo__isnull", True)),
                    _connector="OR",
                ),
                name="formulario_sci_periodo_solo_en_el_201",
            ),
        ),
        # ── SCI-211: uno por emergencia ─────────────────────────────────────
        migrations.AlterField(
            model_name="formulariosci211",
            name="periodo",
            field=models.ForeignKey(
                null=True, on_delete=models.deletion.PROTECT,
                related_name="formularios_sci_211",
                to="emergencias.periodooperacional",
                verbose_name="periodo operacional",
            ),
        ),
        migrations.RunPython(sin_trabajo, periodo_a_los_211),
        migrations.RemoveConstraint(
            model_name="formulariosci211",
            name="sci211_unico_por_periodo",
        ),
        migrations.RemoveField(model_name="formulariosci211", name="periodo"),
        migrations.AddConstraint(
            model_name="formulariosci211",
            constraint=models.UniqueConstraint(
                fields=("emergencia",), name="sci211_unico_por_emergencia"
            ),
        ),
        migrations.AlterField(
            model_name="periodooperacional",
            name="motivo",
            field=models.TextField(
                blank=True,
                help_text="Por qué se abrió este periodo. El primero no lo necesita.",
                verbose_name="motivo del periodo",
            ),
        ),
    ]
