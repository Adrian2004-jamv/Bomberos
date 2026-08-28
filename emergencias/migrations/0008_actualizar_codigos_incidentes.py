import re
import unicodedata
from collections import defaultdict

from django.db import migrations
from django.utils import timezone


PATRON_NUEVO = re.compile(r"^[A-Z0-9]{2}-\d{8}-\d{3,}$")


def iniciales(tipo):
    limpio = unicodedata.normalize("NFKD", tipo or "")
    palabras = re.findall(
        r"[A-Za-z0-9]+", limpio.encode("ascii", "ignore").decode()
    )
    if not palabras:
        return "EM"
    if len(palabras) == 1:
        return palabras[0][:2].upper().ljust(2, "X")
    return (palabras[0][0] + palabras[1][0]).upper()


def actualizar_codigos(apps, schema_editor):
    Emergencia = apps.get_model("emergencias", "Emergencia")
    existentes = set(Emergencia.objects.values_list("codigo", flat=True))
    pendientes = [
        emergencia
        for emergencia in Emergencia.objects.order_by("fecha_reporte", "pk")
        if not PATRON_NUEVO.fullmatch(emergencia.codigo)
    ]
    for emergencia in pendientes:
        existentes.discard(emergencia.codigo)

    contadores = defaultdict(int)
    cambios = []
    for emergencia in pendientes:
        fecha = timezone.localtime(emergencia.fecha_reporte)
        prefijo = f"{iniciales(emergencia.tipo_emergencia)}-{fecha:%d%m%Y}-"
        while True:
            contadores[prefijo] += 1
            nuevo = f"{prefijo}{contadores[prefijo]:03d}"
            if nuevo not in existentes:
                break
        existentes.add(nuevo)
        cambios.append((emergencia, nuevo))

    # Los nombres temporales evitan colisiones cuando un código de destino ya
    # pertenece a otra fila que también será convertida dentro de la migración.
    for emergencia, _ in cambios:
        Emergencia.objects.filter(pk=emergencia.pk).update(
            codigo=f"TMP-{emergencia.pk}"
        )
    for emergencia, nuevo in cambios:
        Emergencia.objects.filter(pk=emergencia.pk).update(codigo=nuevo)


class Migration(migrations.Migration):
    dependencies = [("emergencias", "0007_formulariosci_estado_and_more")]

    operations = [
        migrations.RunPython(actualizar_codigos, migrations.RunPython.noop),
    ]
