from django.db import migrations, models


def retirar_posiciones_repetidas(apps, schema_editor):
    """Deja una sola posición por despliegue y hora del aparato.

    La restricción que sigue no se puede crear si la base ya trae repetidas, y
    puede traerlas: hasta ahora nada impedía que el navegador reenviara la
    misma lectura. Se conserva la primera recibida —la que ya entró en el
    cálculo de los tiempos de respuesta— y se retiran las demás.
    """
    PosicionUnidad = apps.get_model("emergencias", "PosicionUnidad")
    vistas = set()
    sobrantes = []
    for identificador, despliegue_id, fecha in PosicionUnidad.objects.filter(
        fecha_dispositivo__isnull=False
    ).order_by("pk").values_list("pk", "despliegue_id", "fecha_dispositivo"):
        clave = (despliegue_id, fecha)
        if clave in vistas:
            sobrantes.append(identificador)
        else:
            vistas.add(clave)
    if sobrantes:
        PosicionUnidad.objects.filter(pk__in=sobrantes).delete()


def sin_vuelta_atras(apps, schema_editor):
    """Quitar la restricción no obliga a resucitar lo que era una copia."""


class Migration(migrations.Migration):

    dependencies = [
        ("emergencias", "0014_normalizar_tipo_de_emergencia"),
    ]

    operations = [
        migrations.RunPython(retirar_posiciones_repetidas, sin_vuelta_atras),
        migrations.AddConstraint(
            model_name="posicionunidad",
            constraint=models.UniqueConstraint(
                condition=models.Q(("fecha_dispositivo__isnull", False)),
                fields=("despliegue", "fecha_dispositivo"),
                name="pos_unica_por_hora_del_aparato",
            ),
        ),
    ]
