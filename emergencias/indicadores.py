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

from datetime import datetime, timedelta

from django.db.models import (Count, IntegerField, Min, OuterRef, Q, Subquery,
                              Sum)
from django.utils import timezone

from .models import DespliegueUnidad, FormularioSCI, RegistroRecursoSCI211

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
            "formularios_sci_211__registros", distinct=True
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
    return emergencias

def _momento(texto):
    """Lee la fecha y hora de una celda del formulario, o ``None`` si no se entiende.

    Las celdas ``datetime-local`` guardan «2026-10-24T09:30» sin zona: es la hora
    que el bombero vio en su pantalla, o sea la local.
    """
    try:
        momento = datetime.fromisoformat(str(texto).strip())
    except ValueError:
        return None
    if timezone.is_naive(momento):
        momento = timezone.make_aware(momento)
    return momento


def _corto(texto, largo=90):
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= largo else texto[: largo - 1].rstrip() + "…"


def resumen_ejecutivo(emergencias):
    """Cuelga de cada emergencia lo que un jefe quiere saber al primer vistazo.

    Tres datos, ninguno escrito aparte: se leen de lo que el personal ya registra,
    así que no hay un campo más que mantener ni una cifra que pueda contradecir al
    formulario del que sale.

    * ``mando``: el Comandante del Incidente, del SCI-201 (quien firma como
      «preparado por») o, si ese no lo trae, de la fila «Comandante de Incidente
      (Principal)» del SCI-203.
    * ``recursos_en_escena``: las unidades activas repartidas en el lugar, en camino
      y de regreso, de los despliegues ya cargados en la emergencia.
    * ``ultima_novedad``: lo más reciente que consta entre las acciones del SCI-201,
      los hitos de cada despliegue (despachada, salió, llegó, regresó) y, si no hay
      otra cosa, el último formulario tocado.

    Lo que no consta se deja vacío para que la tarjeta lo diga («Sin designar»); no
    se rellena con un valor que se leería como un hecho. El costo son tres consultas
    para todas las tarjetas, no una por tarjeta.
    """
    if not emergencias:
        return emergencias
    ahora = timezone.now()
    ids = [emergencia.pk for emergencia in emergencias]

    mando, mando_203, novedades = {}, {}, {pk: [] for pk in ids}
    formularios = (
        FormularioSCI.objects
        .filter(emergencia_id__in=ids, codigo_sci__in=("201", "203"))
        .order_by("periodo__numero", "pk")
        .only("emergencia_id", "codigo_sci", "datos", "preparado_por",
              "posicion_preparado_por")
    )
    for formulario in formularios:
        datos = formulario.datos or {}
        if formulario.codigo_sci == "201":
            if formulario.preparado_por.strip():
                # Se ordena por periodo: el último que firmó es quien manda ahora.
                mando[formulario.emergencia_id] = (
                    formulario.preparado_por.strip(),
                    formulario.posicion_preparado_por.strip(),
                )
            for fila in datos.get("acciones") or []:
                if not isinstance(fila, dict) or not str(fila.get("accion", "")).strip():
                    continue
                cuando = _momento(fila.get("fecha_hora"))
                if cuando and cuando <= ahora:
                    novedades[formulario.emergencia_id].append(
                        (cuando, _corto(fila["accion"]))
                    )
        else:
            for fila in datos.get("comando") or []:
                if (isinstance(fila, dict)
                        and "principal" in str(fila.get("posicion", "")).lower()
                        and str(fila.get("nombre", "")).strip()):
                    mando_203[formulario.emergencia_id] = (
                        str(fila["nombre"]).strip(), "",
                    )

    ultimo_tocado = {}
    for pk, codigo, cuando in (
        FormularioSCI.objects.filter(emergencia_id__in=ids)
        .order_by("fecha_actualizacion")
        .values_list("emergencia_id", "codigo_sci", "fecha_actualizacion")
    ):
        ultimo_tocado[pk] = (cuando, f"Se actualizó el SCI-{codigo}")

    for emergencia in emergencias:
        emergencia.mando = mando.get(emergencia.pk) or mando_203.get(emergencia.pk)

        en_lugar = en_camino = regresando = 0
        for despliegue in getattr(emergencia, "unidades_desplegadas", []):
            codigo = despliegue.unidad.codigo_interno
            for cuando, frase in (
                (despliegue.fecha_asignacion, f"{codigo} despachada"),
                (despliegue.fecha_salida, f"{codigo} salió de la estación"),
                (despliegue.fecha_llegada, f"{codigo} llegó al lugar"),
                (despliegue.fecha_retorno, f"{codigo} terminó y regresó"),
            ):
                if cuando:
                    novedades[emergencia.pk].append((cuando, frase))
            if despliegue.estado == DespliegueUnidad.Estado.EN_SITIO:
                en_lugar += 1
            elif despliegue.estado == DespliegueUnidad.Estado.RETORNANDO:
                regresando += 1
            elif despliegue.estado in (DespliegueUnidad.Estado.ASIGNADA,
                                       DespliegueUnidad.Estado.EN_RUTA):
                en_camino += 1
        emergencia.recursos_en_escena = {
            "en_lugar": en_lugar, "en_camino": en_camino, "regresando": regresando,
            "activos": en_lugar + en_camino + regresando,
        }

        candidatas = novedades[emergencia.pk]
        if not candidatas and emergencia.pk in ultimo_tocado:
            candidatas = [ultimo_tocado[emergencia.pk]]
        if candidatas:
            cuando, texto = max(candidatas, key=lambda par: par[0])
            emergencia.ultima_novedad = {
                "texto": texto, "momento": cuando,
                # «Hace 0 min» se lee como un error: bajo el minuto se dice así.
                "hace": (
                    formato_duracion(ahora - cuando)
                    if ahora - cuando >= timedelta(minutes=1) else "menos de 1 min"
                ),
            }
        else:
            emergencia.ultima_novedad = None
    return emergencias
