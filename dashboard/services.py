from itertools import chain

from django.db.models import Count, OuterRef, Q, Subquery

from instituciones.permissions import puede_gestionar_instituciones
from inventario.models import HistorialEstadoRecurso, Recurso
from inventario.permissions import (
    estaciones_permitidas,
    puede_consultar_inventario,
    puede_gestionar_inventario,
    recursos_permitidos,
    tiene_alcance_global,
)
from operaciones.models import EvaluacionCapacidadEstacion
from operaciones.permissions import (
    puede_consultar_capacidades,
    puede_evaluar_capacidades,
)


ORDEN_GRUPOS = (
    "Administrador del sistema",
    "Responsable provincial",
    "Responsable institucional",
    "Operador de sistemas institucional",
    "Responsable de estación",
    "Encargado de inventario",
    "Operador de consulta",
)


def _rol_principal(usuario):
    if usuario.is_superuser:
        return "Superusuario técnico"
    grupos = set(usuario.groups.values_list("name", flat=True))
    return next((nombre for nombre in ORDEN_GRUPOS if nombre in grupos), "Usuario autorizado")


def _descripcion_alcance(usuario, estaciones):
    if tiene_alcance_global(usuario):
        return "Información consolidada de todos los Cuerpos de Bomberos de Cotopaxi."
    if usuario.estacion_id and usuario.groups.filter(
        name__in=("Responsable institucional", "Operador de sistemas institucional")
    ).exists():
        return f"Información de {usuario.estacion.cuerpo_bomberos.nombre} y sus estaciones."
    if usuario.estacion_id:
        return f"Información correspondiente a la estación {usuario.estacion.nombre}."
    if not estaciones.exists():
        return "No existe un ámbito institucional asignado a esta cuenta."
    return "Información correspondiente a su ámbito autorizado."


def _evaluaciones_mas_recientes(estaciones):
    base = EvaluacionCapacidadEstacion.objects.filter(estacion__in=estaciones)
    ultimo_id = base.filter(
        estacion_id=OuterRef("estacion_id"),
        capacidad_id=OuterRef("capacidad_id"),
    ).order_by("-fecha_evaluacion", "-pk").values("pk")[:1]
    return base.filter(pk=Subquery(ultimo_id)).select_related(
        "estacion",
        "estacion__cuerpo_bomberos",
        "capacidad",
        "evaluado_por",
    ).order_by("-fecha_evaluacion", "-pk")


def construir_dashboard(usuario, limite_actividad=8):
    estaciones = estaciones_permitidas(usuario)
    recursos = recursos_permitidos(usuario)
    evaluaciones_recientes = _evaluaciones_mas_recientes(estaciones)

    resumen_recursos = recursos.aggregate(
        total=Count("pk"),
        operativos=Count("pk", filter=Q(estado_operativo=Recurso.EstadoOperativo.OPERATIVO)),
        fuera_servicio=Count("pk", filter=Q(estado_operativo=Recurso.EstadoOperativo.FUERA_SERVICIO)),
        disponibles=Count("pk", filter=Q(disponibilidad=Recurso.Disponibilidad.DISPONIBLE)),
        no_disponibles=Count("pk", filter=Q(disponibilidad=Recurso.Disponibilidad.NO_DISPONIBLE)),
    )
    resumen_recursos["estaciones"] = estaciones.count()
    resumen_recursos["capacidades_cumplidas"] = evaluaciones_recientes.filter(
        estado=EvaluacionCapacidadEstacion.Estado.CUMPLE
    ).count()
    resumen_recursos["capacidades_no_cumplidas"] = evaluaciones_recientes.exclude(
        estado=EvaluacionCapacidadEstacion.Estado.CUMPLE
    ).count()

    categorias = list(
        recursos.values("tipo__categoria__nombre")
        .annotate(total=Count("pk"))
        .order_by("-total", "tipo__categoria__nombre")
    )
    maximo_categoria = max((item["total"] for item in categorias), default=0)
    for categoria in categorias:
        categoria["porcentaje"] = round(
            categoria["total"] * 100 / maximo_categoria
        ) if maximo_categoria else 0

    conteos_estado = {
        item["estado_operativo"]: item["total"]
        for item in recursos.values("estado_operativo").annotate(total=Count("pk"))
    }
    estados_operativos = [
        {
            "codigo": codigo,
            "nombre": etiqueta,
            "total": conteos_estado.get(codigo, 0),
            "porcentaje": round(
                conteos_estado.get(codigo, 0) * 100 / resumen_recursos["total"]
            ) if resumen_recursos["total"] else 0,
        }
        for codigo, etiqueta in Recurso.EstadoOperativo.choices
    ]

    cambios = HistorialEstadoRecurso.objects.filter(
        recurso__in=recursos
    ).select_related("recurso", "recurso__estacion", "registrado_por").order_by(
        "-fecha_registro", "-pk"
    )[:limite_actividad]
    evaluaciones_actividad = EvaluacionCapacidadEstacion.objects.filter(
        estacion__in=estaciones
    ).select_related("estacion", "capacidad", "evaluado_por").order_by(
        "-fecha_evaluacion", "-pk"
    )[:limite_actividad]
    actividad = sorted(
        chain(
            (
                {
                    "fecha": cambio.fecha_registro,
                    "tipo": "Cambio de recurso",
                    "titulo": cambio.recurso.nombre,
                    "detalle": f"{cambio.get_estado_anterior_display()} → {cambio.get_estado_nuevo_display()}",
                }
                for cambio in cambios
            ),
            (
                {
                    "fecha": evaluacion.fecha_evaluacion,
                    "tipo": "Evaluación de capacidad",
                    "titulo": evaluacion.capacidad.nombre,
                    "detalle": f"{evaluacion.estacion.nombre}: {evaluacion.get_estado_display()}",
                }
                for evaluacion in evaluaciones_actividad
            ),
        ),
        key=lambda item: item["fecha"],
        reverse=True,
    )[:limite_actividad]

    return {
        "rol_principal": _rol_principal(usuario),
        "alcance_descripcion": _descripcion_alcance(usuario, estaciones),
        "resumen": resumen_recursos,
        "categorias": categorias,
        "estados_operativos": estados_operativos,
        "evaluaciones_recientes": evaluaciones_recientes[:6],
        "actividad_reciente": actividad,
        "puede_consultar_inventario": puede_consultar_inventario(usuario),
        "puede_gestionar_inventario": puede_gestionar_inventario(usuario),
        "puede_consultar_capacidades": puede_consultar_capacidades(usuario),
        "puede_evaluar_capacidades": puede_evaluar_capacidades(usuario),
        "puede_consultar_instituciones": bool(
            tiene_alcance_global(usuario) or usuario.estacion_id
        ),
        "puede_gestionar_instituciones": puede_gestionar_instituciones(usuario),
    }
