from django.db import migrations


NOMBRE_GRUPO = "Operador de sistemas institucional"


def crear_grupo(apps, schema_editor):
    apps.get_model("auth", "Group").objects.get_or_create(name=NOMBRE_GRUPO)


def eliminar_grupo(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name=NOMBRE_GRUPO).delete()


class Migration(migrations.Migration):
    dependencies = [("usuarios", "0003_crear_grupos_iniciales")]
    operations = [migrations.RunPython(crear_grupo, eliminar_grupo)]
