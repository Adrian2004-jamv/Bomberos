from django.db import migrations

NOMBRE_GRUPO = "Chofer de unidad"

def crear_grupo(apps, schema_editor):
    apps.get_model("auth", "Group").objects.get_or_create(name=NOMBRE_GRUPO)

def eliminar_grupo(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name=NOMBRE_GRUPO).delete()

class Migration(migrations.Migration):
    dependencies = [("usuarios", "0005_debe_cambiar_clave_explicita")]
    operations = [migrations.RunPython(crear_grupo, eliminar_grupo)]
