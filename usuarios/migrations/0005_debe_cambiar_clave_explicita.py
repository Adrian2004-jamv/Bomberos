"""El aviso de cambio de clave pasa a activarse de forma explícita.

Hasta ahora ``debe_cambiar_clave`` nacía en verdadero y ningún código lo leía,
de modo que su valor en las cuentas existentes es un resto del valor por
omisión y no una decisión de nadie. Se normaliza a falso para que la obligación
empiece a contar desde las cuentas que se creen o cuyo acceso se restablezca a
partir de aquí, en lugar de sorprender a todo el padrón en su próximo ingreso.
"""

from django.db import migrations, models


def normalizar(apps, schema_editor):
    Usuario = apps.get_model("usuarios", "Usuario")
    Usuario.objects.filter(debe_cambiar_clave=True).update(debe_cambiar_clave=False)


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0004_grupo_operador_sistemas_institucional"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usuario",
            name="debe_cambiar_clave",
            field=models.BooleanField(default=False, verbose_name="debe cambiar la clave"),
        ),
        migrations.RunPython(normalizar, migrations.RunPython.noop),
    ]
