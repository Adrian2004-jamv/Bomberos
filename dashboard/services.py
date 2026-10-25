from itertools import chain

from django.utils.dateparse import parse_date

from django.db.models import Count, Exists, OuterRef, Q, Subquery

from emergencias.esquemas_sci import evaluacion_en_partes, evaluacion_heredada
from emergencias.graficos_sci import limpiar_croquis, limpiar_organigrama, organigrama_svg
from emergencias.forms import TIPOS_EMERGENCIA
from emergencias.indicadores import (anotar_indicadores, preparar_indicadores,
                                      resumen_ejecutivo)

from emergencias.models import (DespliegueUnidad, Emergencia, FormularioSCI211,
                                numero_de_periodo_vigente)
from emergencias.permissions import puede_consultar_emergencias, puede_gestionar_emergencias
from instituciones.permissions import puede_gestionar_instituciones
from inventario.models import HistorialEstadoRecurso, Recurso
from inventario.permissions import estaciones_permitidas, puede_consultar_inventario, puede_gestionar_inventario, recursos_permitidos, tiene_alcance_global
from operaciones.models import EvaluacionCapacidadEstacion
from operaciones.permissions import puede_consultar_capacidades, puede_evaluar_capacidades
ORDEN_GRUPOS = (
    "Administrador del sistema",
    "Responsable provincial",
    "Responsable institucional",
    "Operador de sistemas institucional",
    "Responsable de estación",
    "Encargado de inventario",
    "Operador de consulta",
)

def rol_principal(usuario):
    if usuario.is_superuser:
        return "Superusuario técnico"
    grupos = set(usuario.groups.values_list("name", flat=True))
    return next((nombre for nombre in ORDEN_GRUPOS if nombre in grupos), "Usuario autorizado")

def descripcion_alcance(usuario, estaciones):
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

def evaluaciones_mas_recientes(estaciones):
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

ESTADOS_TERMINADOS = (Emergencia.Estado.CERRADA, Emergencia.Estado.CANCELADA)

def emergencias_del_ambito(estaciones):
    return Emergencia.objects.filter(estacion_responsable__in=estaciones)

def despliegues_del_ambito(estaciones):
    return DespliegueUnidad.objects.filter(estacion_procedencia__in=estaciones)

def rango_de_fechas(parametros):
    """Interpreta «desde» y «hasta» del formulario, sin romperse con basura.

    Una fecha ilegible se ignora en lugar de devolver un error: el panel es
    una pantalla de consulta y quedarse en blanco por una letra de más sería
    peor que mostrar todo.
    """
    desde = parse_date(str(parametros.get("desde") or "")) if parametros else None
    hasta = parse_date(str(parametros.get("hasta") or "")) if parametros else None
    if desde and hasta and desde > hasta:
        desde, hasta = hasta, desde
    return desde, hasta

def emergencias_para_elegir(estaciones):
    """Las emergencias abiertas del ámbito, para poblar el desplegable."""
    return list(
        emergencias_del_ambito(estaciones)
        .exclude(estado__in=ESTADOS_TERMINADOS)
        .order_by("-fecha_reporte", "-pk")
        .values("pk", "codigo", "tipo_emergencia")
    )

def tipos_para_elegir(estaciones):
    """Los tipos del catálogo, más los que existan fuera de él.

    Antes se armaba con los valores guardados sin más, de modo que dos
    variantes de la misma cadena —una con un espacio sobrante, por ejemplo—
    aparecían como dos opciones idénticas. El catálogo manda el orden y los
    nombres; solo se añade lo que alguien registró antes de que el tipo fuera
    un desplegable, para que esas emergencias sigan siendo filtrables.
    """
    guardados = (
        emergencias_del_ambito(estaciones)
        .exclude(estado__in=ESTADOS_TERMINADOS)
        .values_list("tipo_emergencia", flat=True)
        .distinct()
    )
    conocidos = {tipo.strip().casefold() for tipo in TIPOS_EMERGENCIA}
    ajenos = sorted({
        tipo.strip() for tipo in guardados
        if tipo and tipo.strip().casefold() not in conocidos
    })
    return list(TIPOS_EMERGENCIA) + ajenos

def emergencia_pedida(parametros):
    """Devuelve el identificador de la emergencia elegida, o None.

    Un identificador que no sea un número se descarta en silencio, igual que
    una fecha ilegible: el panel es de consulta y no debe quedarse en blanco
    porque alguien manipulara la dirección.
    """
    if not parametros:
        return None
    valor = str(parametros.get("emergencia") or "").strip()
    return int(valor) if valor.isdigit() else None

def tipo_pedido(parametros):
    """Devuelve el tipo de emergencia elegido, o cadena vacía si son todos."""
    if not parametros:
        return ""
    return str(parametros.get("tipo") or "").strip()

def incidentes_en_curso(estaciones, limite=6, desde=None, hasta=None,
                        emergencia=None, tipo=""):
    """Incidentes abiertos, con las unidades que tienen encima y su documentación.

    Las unidades y la existencia del SCI-211 se anotan en la misma consulta;
    resolverlas por fila obligaría a una consulta por incidente al pintar la
    tabla.
    """
    consulta = (
        emergencias_del_ambito(estaciones)
        .exclude(estado__in=ESTADOS_TERMINADOS)
        .select_related("estacion_responsable", "estacion_responsable__cuerpo_bomberos")
        .annotate(
            unidades_activas=Count(
                "despliegues",
                filter=Q(despliegues__estado__in=DespliegueUnidad.ESTADOS_ACTIVOS),
                distinct=True,
            ),
            periodo_vigente_numero=numero_de_periodo_vigente(),
        )
        .annotate(
            tiene_sci211=Exists(
                FormularioSCI211.objects.filter(
                    emergencia_id=OuterRef("pk"),
                    periodo__numero=OuterRef("periodo_vigente_numero"),
                )
            ),
        )
        .order_by("-fecha_reporte", "-pk")
    )
    if desde:
        consulta = consulta.filter(fecha_reporte__date__gte=desde)
    if hasta:
        consulta = consulta.filter(fecha_reporte__date__lte=hasta)
    if emergencia:
        consulta = consulta.filter(pk=emergencia)
    if tipo:
        consulta = consulta.filter(tipo_emergencia=tipo)
    # El resumen de cada emergencia se anota en la misma consulta; resolverlo
    # por fila costaría varias consultas por tarjeta.
    emergencias = preparar_indicadores(list(anotar_indicadores(consulta)[:limite]))
    return resumen_ejecutivo(adjuntar_unidades(emergencias))

def adjuntar_unidades(emergencias):
    """Cuelga de cada emergencia las unidades que tiene encima.

    El tablero decía «1 unidad» sin decir cuál. En un parte lo que se pregunta
    es qué salió, no cuántos salieron. Se resuelve en una consulta para todas
    las emergencias del tablero.
    """
    if not emergencias:
        return emergencias
    por_emergencia = {emergencia.pk: [] for emergencia in emergencias}
    despliegues = DespliegueUnidad.objects.filter(
        emergencia_id__in=por_emergencia
    ).select_related(
        "unidad", "unidad__tipo", "estacion_procedencia"
    ).order_by("fecha_asignacion", "pk")
    for despliegue in despliegues:
        por_emergencia[despliegue.emergencia_id].append(despliegue)
    for emergencia in emergencias:
        emergencia.unidades_desplegadas = por_emergencia[emergencia.pk]
    return emergencias

def resumen_operativo(estaciones):
    emergencias = emergencias_del_ambito(estaciones)
    en_curso = emergencias.exclude(estado__in=ESTADOS_TERMINADOS)
    return {
        "incidentes_en_curso": en_curso.count(),
        "incidentes_atendidos": emergencias.filter(
            estado__in=ESTADOS_TERMINADOS
        ).count(),
        "unidades_desplegadas": despliegues_del_ambito(estaciones)
        .filter(estado__in=DespliegueUnidad.ESTADOS_ACTIVOS)
        .count(),
        # Un incidente abierto sin SCI-211 es documentación pendiente: ese
        # formulario es el registro maestro de recursos del incidente.
        "sin_documentar": en_curso.annotate(
            periodo_vigente_numero=numero_de_periodo_vigente()
        ).filter(
            ~Exists(FormularioSCI211.objects.filter(
                emergencia_id=OuterRef("pk"),
                periodo__numero=OuterRef("periodo_vigente_numero"),
            ))
        ).count(),
    }

def actividad_operativa(estaciones, limite):
    emergencias = (
        emergencias_del_ambito(estaciones)
        .select_related("estacion_responsable")
        .order_by("-fecha_reporte", "-pk")[:limite]
    )
    despliegues = (
        despliegues_del_ambito(estaciones)
        .select_related("unidad", "emergencia")
        .order_by("-fecha_asignacion", "-pk")[:limite]
    )
    return chain(
        (
            {
                "fecha": emergencia.fecha_reporte,
                "tipo": "Incidente",
                "titulo": f"{emergencia.codigo} · {emergencia.tipo_emergencia}",
                "detalle": f"{emergencia.estacion_responsable.nombre}: "
                           f"{emergencia.get_estado_display()}",
            }
            for emergencia in emergencias
        ),
        (
            {
                "fecha": despliegue.fecha_asignacion,
                "tipo": "Despliegue",
                "titulo": f"{despliegue.unidad.codigo_interno} → {despliegue.emergencia.codigo}",
                "detalle": despliegue.get_estado_display(),
            }
            for despliegue in despliegues
        ),
    )

def construir_dashboard(usuario, limite_actividad=8, parametros=None):
    filtro_desde, filtro_hasta = rango_de_fechas(parametros)
    filtro_emergencia = emergencia_pedida(parametros)
    filtro_tipo = tipo_pedido(parametros)
    estaciones = estaciones_permitidas(usuario)
    recursos = recursos_permitidos(usuario)
    evaluaciones_recientes = evaluaciones_mas_recientes(estaciones)

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
            actividad_operativa(estaciones, limite_actividad),
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
        "rol_principal": rol_principal(usuario),
        "alcance_descripcion": descripcion_alcance(usuario, estaciones),
        "resumen": resumen_recursos,
        "operativo": resumen_operativo(estaciones),
        "incidentes_en_curso": incidentes_en_curso(
            estaciones, desde=filtro_desde, hasta=filtro_hasta,
            emergencia=filtro_emergencia, tipo=filtro_tipo,
        ),
        "emergencias_del_filtro": emergencias_para_elegir(estaciones),
        "tipos_del_filtro": tipos_para_elegir(estaciones),
        "filtro_desde": filtro_desde,
        "filtro_hasta": filtro_hasta,
        "filtro_emergencia": filtro_emergencia,
        "filtro_tipo": filtro_tipo,
        "categorias": categorias,
        "estados_operativos": estados_operativos,
        "evaluaciones_recientes": evaluaciones_recientes[:6],
        "actividad_reciente": actividad,
        "puede_consultar_inventario": puede_consultar_inventario(usuario),
        "puede_gestionar_inventario": puede_gestionar_inventario(usuario),
        "puede_consultar_capacidades": puede_consultar_capacidades(usuario),
        "puede_evaluar_capacidades": puede_evaluar_capacidades(usuario),
        "puede_consultar_emergencias": puede_consultar_emergencias(usuario),
        "puede_gestionar_emergencias": puede_gestionar_emergencias(usuario),
        "puede_consultar_instituciones": bool(
            tiene_alcance_global(usuario) or usuario.estacion_id
        ),
        "puede_gestionar_instituciones": puede_gestionar_instituciones(usuario),
    }


# ==========================================
# MÓDULO: INFORME DE EMERGENCIAS FINALIZADAS
# ==========================================

def emergencias_finalizadas(estaciones, limite=20, desde=None, hasta=None):
    """Emergencias cerradas o canceladas del ámbito, con datos relacionados precargados."""
    consulta = (
        emergencias_del_ambito(estaciones)
        .filter(estado__in=ESTADOS_TERMINADOS)
        .select_related(
            "estacion_responsable",
            "estacion_responsable__cuerpo_bomberos",
            "estacion_responsable__cuerpo_bomberos__canton",
            "registrado_por",
        )
        .prefetch_related("despliegues__unidad__tipo__categoria", "despliegues__estacion_procedencia")
        .order_by("-fecha_cierre", "-fecha_reporte", "-pk")
    )
    if desde:
        consulta = consulta.filter(fecha_reporte__date__gte=desde)
    if hasta:
        consulta = consulta.filter(fecha_reporte__date__lte=hasta)
    return list(consulta[:limite])


def _sci_datos(emergencia, codigo):
    """Devuelve el JSONField datos del primer FormularioSCI encontrado, o {}."""
    from emergencias.models import FormularioSCI
    formulario = (
        FormularioSCI.objects
        .filter(emergencia=emergencia, codigo_sci=codigo)
        .order_by("periodo__numero")
        .first()
    )
    return formulario.datos if formulario else {}


def _sci_preparado_por(emergencia, codigo):
    """Devuelve el campo preparado_por del formulario, o cadena vacía."""
    from emergencias.models import FormularioSCI
    formulario = (
        FormularioSCI.objects
        .filter(emergencia=emergencia, codigo_sci=codigo)
        .order_by("periodo__numero")
        .first()
    )
    return formulario.preparado_por if formulario else ""


def _fmt_dt(dt):
    """Fecha y hora en formato legible, o 'No registrado'."""
    if dt is None:
        return "No registrado"
    from django.utils.timezone import localtime
    return localtime(dt).strftime("%d/%m/%Y %H:%M")


def _duracion(inicio, fin):
    """Calcula horas y minutos entre dos datetime, o None si falta alguno."""
    if not inicio or not fin:
        return None
    delta = fin - inicio
    if delta.total_seconds() < 0:
        return None
    total = int(delta.total_seconds())
    horas, resto = divmod(total, 3600)
    minutos = resto // 60
    if horas:
        return f"{horas} h {minutos:02d} min"
    return f"{minutos} min"


def datos_informe_emergencia(emergencia):
    """
    Reúne toda la información disponible de una emergencia finalizada
    para construir el resumen operativo y el PDF institucional.

    Extrae datos reales del modelo y los formularios SCI relacionados.
    No inventa valores: usa 'No registrado' cuando el dato falta.
    """
    # ── Despliegues ──────────────────────────────────────────────────
    despliegues = list(
        emergencia.despliegues
        .select_related(
            "unidad", "unidad__tipo", "unidad__tipo__categoria",
            "estacion_procedencia", "estacion_procedencia__cuerpo_bomberos",
            "despachado_por",
        )
        .order_by("fecha_asignacion", "pk")
    )
    # Primera salida y primera llegada registradas entre todos los despliegues
    salidas    = [d.fecha_salida   for d in despliegues if d.fecha_salida]
    llegadas   = [d.fecha_llegada  for d in despliegues if d.fecha_llegada]
    retornos   = [d.fecha_retorno  for d in despliegues if d.fecha_retorno]
    primera_salida  = min(salidas)   if salidas   else None
    primera_llegada = min(llegadas)  if llegadas  else None
    ultima_retorno  = max(retornos)  if retornos  else None

    # ── Formularios SCI ──────────────────────────────────────────────
    sci201 = _sci_datos(emergencia, "201")
    sci203 = _sci_datos(emergencia, "203")
    sci207 = _sci_datos(emergencia, "207")
    sci214 = _sci_datos(emergencia, "214")
    sci221 = _sci_datos(emergencia, "221")
    ci_nombre = _sci_preparado_por(emergencia, "201")  # campo «preparado_por» = CI

    # Comandante del incidente desde SCI-203 tabla «comando»
    if not ci_nombre and sci203:
        for fila in (sci203.get("comando") or []):
            if isinstance(fila, dict):
                posicion = str(fila.get("posicion", "")).strip()
                nombre   = str(fila.get("nombre", "")).strip()
                if "principal" in posicion.lower() and nombre:
                    ci_nombre = nombre
                    break

    # Representantes institucionales (SCI-203)
    representantes = [
        f"{r.get('nombre','')} — {r.get('institucion','')}"
        for r in (sci203.get("representantes") or [])
        if isinstance(r, dict) and (r.get("nombre") or r.get("institucion"))
    ]

    # Personal SCI-214
    personal_sci = [
        f"{p.get('nombre','')} ({p.get('posicion','')}) — {p.get('institucion','')}"
        for p in (sci214.get("personal") or [])
        if isinstance(p, dict) and p.get("nombre")
    ]

    # Actividades SCI-214
    actividades = [
        {"hora": a.get("hora", ""), "evento": a.get("evento", "")}
        for a in (sci214.get("actividades") or [])
        if isinstance(a, dict) and a.get("evento")
    ]

    # Acciones cronológicas SCI-201
    acciones_201 = [
        {"fecha_hora": a.get("fecha_hora", ""), "accion": a.get("accion", "")}
        for a in (sci201.get("acciones") or [])
        if isinstance(a, dict) and a.get("accion")
    ]

    # Pacientes SCI-207
    pacientes = [
        p for p in (sci207.get("pacientes") or [])
        if isinstance(p, dict) and p.get("nombre")
    ]
    total_pacientes = len(pacientes)
    fallecidos   = sum(1 for p in pacientes if "rojo" in str(p.get("clasificacion","")).lower()
                       and "fallecido" in str(p.get("lugar_traslado","")).lower())
    evacuados    = sum(1 for p in pacientes if p.get("lugar_traslado"))

    # ── Cronología ───────────────────────────────────────────────────
    hora_notificacion  = emergencia.fecha_reporte
    hora_cierre        = emergencia.fecha_cierre
    hora_desmoviliz    = None
    if sci221.get("tiempo_conclusion"):
        from django.utils.dateparse import parse_datetime
        from django.utils.timezone import make_aware, is_naive
        dt_raw = parse_datetime(sci221["tiempo_conclusion"])
        if dt_raw:
            hora_desmoviliz = make_aware(dt_raw) if is_naive(dt_raw) else dt_raw

    tiempo_respuesta      = _duracion(hora_notificacion, primera_llegada)
    duracion_operaciones  = _duracion(primera_llegada,   hora_cierre)
    duracion_total        = _duracion(hora_notificacion, hora_cierre)

    # ── Institución ──────────────────────────────────────────────────
    estacion = emergencia.estacion_responsable
    try:
        cuerpo = estacion.cuerpo_bomberos
        canton = cuerpo.canton
        institucion_nombre = cuerpo.nombre
        provincia = getattr(canton, "provincia", None) or "Cotopaxi"
        canton_nombre = canton.nombre if canton else "No registrado"
    except Exception:
        institucion_nombre = "No registrado"
        provincia = "Cotopaxi"
        canton_nombre = "No registrado"

    # ── SCI-211 ──────────────────────────────────────────────────────
    sci211 = getattr(emergencia, "formulario_sci_211", None)
    registros_211 = []
    if sci211:
        registros_211 = list(
            sci211.registros
            .select_related("recurso_inventario__tipo__categoria")
            .order_by("orden", "pk")
        )

    return {
        # Identificación
        "emergencia":          emergencia,
        "codigo":              emergencia.codigo,
        "tipo":                emergencia.tipo_emergencia,
        "prioridad":           emergencia.get_prioridad_display(),
        "estado":              emergencia.get_estado_display(),
        "descripcion":         emergencia.descripcion or "No registrado",
        "institucion":         institucion_nombre,
        "provincia":           str(provincia),
        "canton":              canton_nombre,
        "estacion":            estacion.nombre,
        # Ubicación
        "direccion":           emergencia.direccion or "No registrado",
        "latitud":             str(emergencia.latitud)  if emergencia.latitud  else None,
        "longitud":            str(emergencia.longitud) if emergencia.longitud else None,
        "coordenadas":         (f"{emergencia.latitud}, {emergencia.longitud}"
                                if emergencia.latitud and emergencia.longitud else "No registrado"),
        # Mando
        "ci_nombre":           ci_nombre or "No registrado",
        "registrado_por":      emergencia.registrado_por.get_full_name()
                               or emergencia.registrado_por.username,
        "representantes":      representantes,
        "personal_sci":        personal_sci,
        # Cronología
        "hora_notificacion":   _fmt_dt(hora_notificacion),
        "hora_primera_salida": _fmt_dt(primera_salida),
        "hora_primera_llegada":_fmt_dt(primera_llegada),
        "hora_cierre":         _fmt_dt(hora_cierre),
        "hora_desmoviliz":     _fmt_dt(hora_desmoviliz),
        "tiempo_respuesta":    tiempo_respuesta    or "No calculable",
        "duracion_operaciones":duracion_operaciones or "No calculable",
        "duracion_total":      duracion_total       or "No calculable",
        # Descripción operativa (SCI-201)
        # Cada sub-punto del punto 4 por separado; si el SCI-201 es de cuando
        # era una sola casilla, ese texto va como único elemento.
        "evaluacion_items":    (
            evaluacion_en_partes(sci201)
            or ([("Evaluación inicial", evaluacion_heredada(sci201))]
                if evaluacion_heredada(sci201) else [])
        ),
        "objetivos":           sci201.get("objetivos_iniciales") or "No registrado",
        "estrategias":         sci201.get("estrategias")         or "No registrado",
        "tacticas":            sci201.get("tacticas")            or "No registrado",
        "mensaje_seguridad":   sci201.get("mensaje_seguridad")   or "No registrado",
        "organigrama":         sci201.get("organigrama")         or "No registrado",
        # Los gráficos del SCI-201: el croquis dibujado y el organigrama armado.
        # Sin ellos el resumen y el PDF no se enteraban de que existían.
        "croquis_dibujo":      limpiar_croquis(sci201.get("croquis__dibujo")),
        "croquis_nota":        sci201.get("croquis") or "",
        "organigrama_svg":     organigrama_svg(sci201.get("organigrama__grafico")),
        "organigrama_grafico": limpiar_organigrama(sci201.get("organigrama__grafico")),
        "ubicacion_pc":        sci201.get("ubicacion_pc")        or "No registrado",
        "acciones_201":        acciones_201,
        # Recursos
        "despliegues":         despliegues,
        "total_unidades":      len(despliegues),
        "registros_211":       registros_211,
        "sci211":              sci211,
        # Afectaciones (SCI-207)
        "pacientes":           pacientes,
        "total_pacientes":     total_pacientes,
        "evacuados":           evacuados,
        "fallecidos":          fallecidos,
        # Actividades (SCI-214)
        "actividades":         actividades,
        "representantes_inst": representantes,
    }
