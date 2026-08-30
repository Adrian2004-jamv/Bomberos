"""Indicadores de una emergencia concreta.

El panel de control resume toda la provincia; esto responde lo mismo pero
acotado a un solo registro: cuánto lleva abierta, cuánta gente y cuántas
unidades tiene comprometidas, qué tan rápido llegó la primera y cuánto de su
documentación SCI está lista.

Todas las cifras salen de lo ya registrado —despliegues y formularios— de modo
que no hay un dato que alguien deba mantener aparte.
"""

from django.db.models import Min, Sum
from django.utils import timezone

from .models import DespliegueUnidad

TOTAL_FORMULARIOS_SCI = 12


def _formato_duracion(diferencia):
    """Convierte una duración en algo legible: «2 h 35 min»."""
    if diferencia is None:
        return None
    minutos_totales = int(diferencia.total_seconds() // 60)
    if minutos_totales < 0:
        return None
    dias, resto = divmod(minutos_totales, 60 * 24)
    horas, minutos = divmod(resto, 60)
    if dias:
        return f"{dias} d {horas} h"
    if horas:
        return f"{horas} h {minutos} min"
    return f"{minutos} min"


def _avance_documental(emergencia):
    genericos = emergencia.formularios_sci.count()
    tiene_211 = hasattr(emergencia, "formulario_sci_211")
    completados = genericos + int(tiene_211)
    return {
        "completados": completados,
        "total": TOTAL_FORMULARIOS_SCI,
        "porcentaje": round(completados / TOTAL_FORMULARIOS_SCI * 100),
    }


def resumen_de_emergencia(emergencia):
    """Devuelve los indicadores propios de una emergencia."""
    despliegues = emergencia.despliegues.all()
    activos = [d for d in despliegues if d.estado in DespliegueUnidad.ESTADOS_ACTIVOS]

    sci211 = getattr(emergencia, "formulario_sci_211", None)
    personal = None
    recursos_registrados = 0
    if sci211 is not None:
        agregado = sci211.registros.aggregate(
            personas=Sum("numero_personas"), total=Min("orden")
        )
        personal = agregado["personas"]
        recursos_registrados = sci211.registros.count()

    # La primera llegada mide cuánto tardó la respuesta en tocar el sitio.
    primera_llegada = despliegues.aggregate(momento=Min("fecha_llegada"))["momento"]
    tiempo_respuesta = None
    if primera_llegada and emergencia.fecha_reporte:
        tiempo_respuesta = _formato_duracion(primera_llegada - emergencia.fecha_reporte)

    fin = emergencia.fecha_cierre or timezone.now()
    duracion = _formato_duracion(fin - emergencia.fecha_reporte)

    return {
        "duracion": duracion,
        "sigue_abierta": emergencia.fecha_cierre is None,
        "unidades_activas": len(activos),
        "unidades_totales": len(despliegues),
        "personal_comprometido": personal,
        "recursos_registrados": recursos_registrados,
        "tiempo_respuesta": tiempo_respuesta,
        "primera_llegada": primera_llegada,
        "avance_documental": _avance_documental(emergencia),
    }
