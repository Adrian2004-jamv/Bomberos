"""Devuelve a borrador los SCI-211 cerrados antes de tiempo.

El SCI-211 pasó a ser la bitácora de control de recursos del incidente y no
se cierra hasta que la emergencia termina. Los que se finalizaron bajo la
regla anterior, en emergencias que siguen abiertas, quedaron congelados: no
admiten las unidades que lleguen después y no hay forma de reabrirlos desde la
interfaz, porque un formulario finalizado no vuelve a borrador.

Solo se tocan los de emergencias en curso. Un SCI-211 de una emergencia ya
cerrada está finalizado como debe y se deja intacto.
"""

from django.db import migrations

ESTADOS_TERMINADOS = ("cerrada", "cancelada")


def reabrir(apps, schema_editor):
    FormularioSCI211 = apps.get_model("emergencias", "FormularioSCI211")
    FormularioSCI211.objects.filter(estado="finalizado").exclude(
        emergencia__estado__in=ESTADOS_TERMINADOS
    ).update(estado="borrador", finalizado_por=None, fecha_finalizacion=None)


def sin_vuelta_atras(apps, schema_editor):
    """No se recierran: no se sabe cuáles estaban cerrados antes."""


class Migration(migrations.Migration):

    dependencies = [
        ("emergencias", "0012_alter_registrorecursosci211_estado_recurso"),
    ]

    operations = [
        migrations.RunPython(reabrir, sin_vuelta_atras),
    ]
