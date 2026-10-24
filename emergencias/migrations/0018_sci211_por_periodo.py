"""El SCI-211 pasa de uno por emergencia a uno por periodo operacional.

Al reactivar un incidente el SCI-211 del periodo 1 seguía finalizado y bloqueado, y
no había forma de crear otro: en el periodo 2 no se podían registrar recursos.

Los 211 que ya existen se asignan al periodo en que se crearon: el que contiene su
fecha de creación, o el primero si ninguno la contiene (los periodos de las
emergencias que no se reactivaron son uno solo, de modo que ahí no hay duda).
"""

import django.db.models.deletion
from django.db import migrations, models


def asignar_periodo(apps, schema_editor):
    FormularioSCI211 = apps.get_model("emergencias", "FormularioSCI211")
    PeriodoOperacional = apps.get_model("emergencias", "PeriodoOperacional")

    for formulario in FormularioSCI211.objects.select_related("emergencia").all():
        periodos = list(
            PeriodoOperacional.objects.filter(emergencia=formulario.emergencia).order_by("numero")
        )
        if not periodos:
            # Una emergencia que nunca abrió un formulario genérico puede no tener
            # periodo todavía; es el mismo que se crearía bajo demanda.
            periodos = [PeriodoOperacional.objects.create(
                emergencia=formulario.emergencia, numero=1,
                inicio=formulario.emergencia.fecha_reporte,
            )]
        elegido = periodos[0]
        for periodo in periodos:
            empieza = periodo.inicio <= formulario.fecha_creacion
            termina = periodo.fin is None or formulario.fecha_creacion < periodo.fin
            if empieza and termina:
                elegido = periodo
                break
        formulario.periodo = elegido
        formulario.save(update_fields=["periodo"])


def deshacer(apps, schema_editor):
    """No hay nada que deshacer: al revertir se descarta la columna."""


class Migration(migrations.Migration):

    dependencies = [
        ("emergencias", "0017_periodo_operacional"),
    ]

    operations = [
        migrations.AddField(
            model_name="formulariosci211",
            name="periodo",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="formularios_sci_211",
                to="emergencias.periodooperacional",
                verbose_name="periodo operacional",
            ),
        ),
        migrations.RunPython(asignar_periodo, deshacer),
        migrations.AlterField(
            model_name="formulariosci211",
            name="periodo",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="formularios_sci_211",
                to="emergencias.periodooperacional",
                verbose_name="periodo operacional",
            ),
        ),
        migrations.AlterField(
            model_name="formulariosci211",
            name="emergencia",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="formularios_sci_211",
                to="emergencias.emergencia",
                verbose_name="emergencia",
            ),
        ),
        migrations.AddConstraint(
            model_name="formulariosci211",
            constraint=models.UniqueConstraint(
                fields=("emergencia", "periodo"), name="sci211_unico_por_periodo"
            ),
        ),
    ]
