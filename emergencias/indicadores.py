"""Indicadores por emergencia para el panel de control.

El panel resume la provincia con cuatro cifras; esto añade, en la misma
pantalla, la lectura rápida de cada emergencia abierta: cuánto lleva, cuántas
unidades tiene en el sitio, cuánta gente hay comprometida y cuánto tardó la
primera unidad en llegar.

Todo se anota en la consulta que ya trae las emergencias, de modo que la lista
completa cuesta una consulta y no una por fila. Las cifras se derivan de lo ya
registrado —despliegues y formularios—, así que no hay ningún dato que alguien
deba mantener aparte ni que pueda contradecir a la pantalla que lo alimenta.
"""

from django.db.models import Count, Min, Q, Sum
from django.utils import timezone

from .models import DespliegueUnidad

TOTAL_FORMULARIOS_SCI = 12

def formato_duracion(diferencia):
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

def anotar_indicadores(emergencias):
    """Agrega a la consulta lo que necesita el resumen de cada emergencia."""
    return emergencias.annotate(
        unidades_totales=Count("despliegues", distinct=True),
        primera_llegada=Min("despliegues__fecha_llegada"),
        personal_comprometido=Sum("formulario_sci_211__registros__numero_personas"),
        recursos_registrados=Count(
            "formulario_sci_211__registros", distinct=True
        ),
        formularios_genericos=Count("formularios_sci", distinct=True),
    )

def preparar_indicadores(emergencias):
    """Calcula sobre cada fila lo que no conviene resolver en la base.

    Las duraciones dependen del instante actual y su formato es de
    presentación, de modo que se arman aquí y no en la consulta.
    """
    ahora = timezone.now()
    for emergencia in emergencias:
        fin = emergencia.fecha_cierre or ahora
        emergencia.duracion = formato_duracion(fin - emergencia.fecha_reporte)
        emergencia.sigue_abierta = emergencia.fecha_cierre is None
        emergencia.tiempo_respuesta = (
            formato_duracion(emergencia.primera_llegada - emergencia.fecha_reporte)
            if emergencia.primera_llegada else None
        )
        completados = emergencia.formularios_genericos + int(emergencia.tiene_sci211)
        emergencia.formularios_completados = completados
        emergencia.formularios_total = TOTAL_FORMULARIOS_SCI
        emergencia.formularios_porcentaje = round(
            completados / TOTAL_FORMULARIOS_SCI * 100
        )
        emergencia.puntos_clave = puntos_clave(emergencia)
    return emergencias

def puntos_clave(emergencia):
    """Resume una emergencia en frases sueltas, listas para leerse en voz alta.

    Nace de una necesidad concreta: quien atiende una entrevista o un parte no
    puede ponerse a interpretar una tabla de indicadores. Cada frase sale de un
    dato ya calculado; lo que no consta no se menciona, en vez de rellenarse
    con un cero que se leería como un hecho.
    """
    puntos = []
    if emergencia.sigue_abierta:
        puntos.append(f"Abierta desde hace {emergencia.duracion}.")
    else:
        puntos.append(f"Cerrada tras {emergencia.duracion} de atención.")

    if emergencia.unidades_activas:
        frase = (
            f"{emergencia.unidades_activas} unidad"
            f"{'es' if emergencia.unidades_activas != 1 else ''} en el lugar"
        )
        if emergencia.unidades_totales > emergencia.unidades_activas:
            frase += f", de {emergencia.unidades_totales} movilizadas"
        puntos.append(frase + ".")
    elif emergencia.unidades_totales:
        puntos.append(f"{emergencia.unidades_totales} unidad(es) movilizadas, ninguna activa.")
    else:
        puntos.append("Todavía sin unidades despachadas.")

    if emergencia.personal_comprometido:
        puntos.append(f"{emergencia.personal_comprometido} personas comprometidas.")

    if emergencia.tiempo_respuesta:
        puntos.append(f"Primera unidad en el lugar a los {emergencia.tiempo_respuesta}.")
    elif emergencia.unidades_totales:
        puntos.append("Ninguna unidad ha reportado todavía su llegada.")

    puntos.append(
        f"Documentación SCI: {emergencia.formularios_completados} de "
        f"{emergencia.formularios_total} formularios."
    )
    return puntos
