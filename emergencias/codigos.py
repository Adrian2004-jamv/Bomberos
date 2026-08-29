"""Codificación oficial de los incidentes.

Un incidente se identifica con ``II-DDMMAAAA-NNN``:

* ``II``       dos letras derivadas del tipo de emergencia (Incendio estructural -> IE)
* ``DDMMAAAA`` fecha del reporte en hora local
* ``NNN``      consecutivo dentro de ese tipo y esa fecha, empezando en 001

Este módulo es la única fuente de la regla: lo usan el registro de incidentes,
los comandos que cargan datos de demostración y las pruebas. La migración
``0008_actualizar_codigos_incidentes`` lleva su propia copia porque una
migración no debe depender de código de aplicación que puede cambiar después.
"""

import re
import unicodedata

from django.db import connection
from django.utils import timezone

PATRON_CODIGO = re.compile(r"^[A-Z0-9]{2}-\d{8}-\d{3,}$")


def iniciales_tipo_emergencia(tipo):
    """Forma dos letras estables: «Incendio forestal» -> IF, «Rescate» -> RE."""
    limpio = unicodedata.normalize("NFKD", tipo or "")
    palabras = re.findall(r"[A-Za-z0-9]+", limpio.encode("ascii", "ignore").decode())
    if not palabras:
        return "EM"
    if len(palabras) == 1:
        return palabras[0][:2].upper().ljust(2, "X")
    return (palabras[0][0] + palabras[1][0]).upper()


def prefijo_codigo(tipo, fecha_reporte):
    """Devuelve ``II-DDMMAAAA-``, la parte del código sin el consecutivo."""
    fecha_local = timezone.localtime(fecha_reporte)
    return f"{iniciales_tipo_emergencia(tipo)}-{fecha_local:%d%m%Y}-"


def generar_codigo_emergencia(tipo, fecha_reporte):
    """Genera el siguiente código libre y serializa el consecutivo en PostgreSQL."""
    from .models import Emergencia

    prefijo = prefijo_codigo(tipo, fecha_reporte)
    # Dos registros simultaneos del mismo tipo y fecha no deben recibir el
    # mismo consecutivo. El bloqueo dura hasta finalizar transaction.atomic.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [prefijo])
    return f"{prefijo}{_siguiente_consecutivo(Emergencia, prefijo):03d}"


def _siguiente_consecutivo(Emergencia, prefijo):
    codigos = Emergencia.objects.filter(codigo__startswith=prefijo).values_list(
        "codigo", flat=True
    )
    consecutivos = [
        int(codigo.removeprefix(prefijo))
        for codigo in codigos
        if codigo.removeprefix(prefijo).isdigit()
    ]
    return max(consecutivos, default=0) + 1


def codigo_fijo(tipo, fecha_reporte, consecutivo=1):
    """Código reproducible para datos de demostración y escenarios de prueba.

    No consulta la base: dos ejecuciones con los mismos argumentos devuelven
    siempre el mismo valor, de modo que los comandos de carga siguen siendo
    idempotentes al usarlo como clave de búsqueda.
    """
    return f"{prefijo_codigo(tipo, fecha_reporte)}{consecutivo:03d}"
