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

from django.db.models import (Count, IntegerField, Min, OuterRef, Q, Subquery,
                              Sum)
from django.utils import timezone

from .models import DespliegueUnidad, RegistroRecursoSCI211

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
    """Agrega a la consulta lo que necesita el resumen de cada emergencia.

    El personal va en una subconsulta y no en un ``Sum`` sobre la unión. La
    consulta enlaza a la vez los despliegues, los registros del SCI-211 y los
    formularios genéricos, de modo que cada fila del resultado se repite tantas
    veces como combinaciones haya. Un ``Count`` se defiende con ``distinct``,
    pero un ``Sum`` no admite esa opción: sumaba el mismo registro una vez por
    combinación y el panel llegó a anunciar cincuenta personas donde había
    cinco.
    """
    personal = RegistroRecursoSCI211.objects.filter(
        formulario__emergencia_id=OuterRef("pk")
    ).values("formulario__emergencia_id").annotate(
        total=Sum("numero_personas")
    ).values("total")[:1]

    return emergencias.annotate(
        unidades_totales=Count("despliegues", distinct=True),
        unidades_en_sitio=Count(
            "despliegues",
            filter=Q(despliegues__fecha_llegada__isnull=False),
            distinct=True,
        ),
        primera_llegada=Min("despliegues__fecha_llegada"),
        personal_comprometido=Subquery(personal, output_field=IntegerField()),
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
        # «Activa» incluye asignada y en ruta: decir «en el lugar» anunciaba en
        # la escena unidades que aún no habían salido de la estación.
        frase = (
            f"{emergencia.unidades_activas} unidad"
            f"{'es' if emergencia.unidades_activas != 1 else ''} movilizada"
            f"{'s' if emergencia.unidades_activas != 1 else ''}"
        )
        if emergencia.unidades_en_sitio:
            frase += f", {emergencia.unidades_en_sitio} en el lugar"
        else:
            frase += ", ninguna ha llegado todavía"
        if emergencia.unidades_totales > emergencia.unidades_activas:
            frase += f" (de {emergencia.unidades_totales} despachadas en total)"
        puntos.append(frase + ".")
    elif emergencia.unidades_totales:
        puntos.append(f"{emergencia.unidades_totales} unidad(es) movilizadas, ninguna activa.")
    else:
        puntos.append("Todavía sin unidades despachadas.")

    if emergencia.personal_comprometido:
        puntos.append(f"{emergencia.personal_comprometido} personas comprometidas.")

    # El tiempo de respuesta se sigue calculando y guardando; se retiró de este
    # resumen a petición del usuario, no porque dejara de medirse.

    puntos.append(
        f"Documentación SCI: {emergencia.formularios_completados} de "
        f"{emergencia.formularios_total} formularios."
    )
    return puntos
