"""Esquemas declarativos de los formularios SCI distintos del SCI-211.

Cada esquema reproduce la numeración y la estructura del formulario oficial
(Rev. 06-2015, SCI-222 versión 2018). El SCI-211 no aparece aquí porque tiene
modelo propio en ``models.FormularioSCI211``.

Los datos capturados se guardan en ``FormularioSCI.datos`` con esta forma:

* campos simples      -> ``{"nombre_campo": "valor"}``
* tablas repetibles   -> ``{"nombre_tabla": [{"columna": "valor"}, ...]}``
* listas de chequeo   -> ``{"nombre_lista": {"filas": [...], "firma": "..."}}``
"""

TEXTO = "texto"
TEXTAREA = "textarea"
FECHA_HORA = "fecha_hora"
TABLA = "tabla"


def _columna(nombre, etiqueta, ancho=""):
    return {"nombre": nombre, "etiqueta": etiqueta, "ancho": ancho}


ESQUEMAS_SCI = {
    "201": {
        "nombre": "Resumen del Incidente",
        "proposito": (
            "Registrar la información inicial del incidente y respaldar la transferencia "
            "de mando. Es la fuente del nombre del incidente para todos los demás formularios."
        ),
        "orientacion": "vertical",
        "paginas": 4,
        "periodo_operacional": False,
        "preparado_por": "Comandante del Incidente",
        "secciones": [
            {"numero": 4, "nombre": "evaluacion_inicial", "etiqueta": "Evaluación inicial", "tipo": TEXTAREA,
             "ayuda": "Naturaleza del incidente, amenazas, áreas afectadas y aislamiento.", "filas": 5},
            {"numero": 5, "nombre": "objetivos_iniciales", "etiqueta": "Objetivo(s) inicial(es)", "tipo": TEXTAREA, "filas": 4},
            {"numero": 6, "nombre": "estrategias", "etiqueta": "Estrategias", "tipo": TEXTAREA, "filas": 4},
            {"numero": 7, "nombre": "tacticas", "etiqueta": "Tácticas", "tipo": TEXTAREA, "filas": 4},
            {"numero": 8, "nombre": "ubicacion_pc", "etiqueta": "Ubicación del Puesto de Comando (PC)", "tipo": TEXTO},
            {"numero": 9, "nombre": "ubicacion_e", "etiqueta": "Ubicación del Área de Espera (E)", "tipo": TEXTO},
            {"numero": 10, "nombre": "ruta_ingreso", "etiqueta": "Ruta de ingreso", "tipo": TEXTO},
            {"numero": 11, "nombre": "ruta_egreso", "etiqueta": "Ruta de egreso", "tipo": TEXTO},
            {"numero": 12, "nombre": "mensaje_seguridad", "etiqueta": "Mensaje general de seguridad", "tipo": TEXTAREA, "filas": 4},
            {"numero": 14, "nombre": "croquis", "etiqueta": "Mapa situacional o croquis", "tipo": TEXTAREA,
             "ayuda": "Describa el croquis. Las coordenadas de la emergencia se imprimen automáticamente.", "filas": 6},
            {"numero": 16, "nombre": "acciones", "etiqueta": "Resumen de las acciones", "tipo": TABLA,
             "columnas": [_columna("fecha_hora", "15. Fecha y hora", "18%"),
                          _columna("accion", "Resumen de la acción")],
             "filas_minimas": 6},
            {"numero": 17, "nombre": "organigrama", "etiqueta": "Organigrama actual", "tipo": TEXTAREA,
             "ayuda": "Posiciones activadas y responsable de cada una.", "filas": 6},
        ],
    },
    "202": {
        "nombre": "Plan de Acción del Incidente",
        "proposito": (
            "Consignar los objetivos, estrategias, tácticas y recursos del periodo "
            "operacional. Lo prepara el Jefe de la Sección de Planificación y lo aprueba el CI."
        ),
        "orientacion": "horizontal",
        "paginas": 3,
        "periodo_operacional": True,
        "preparado_por": "Jefe de la Sección de Planificación (JSP)",
        "aprobado_por": "Comandante del Incidente (CI)",
        "secciones": [
            {"numero": 6, "nombre": "objetivos", "etiqueta": "Objetivo(s)", "tipo": TEXTAREA, "filas": 4},
            {"numero": 7, "nombre": "plan", "etiqueta": "Estrategias, tácticas y asignación de recursos", "tipo": TABLA,
             "columnas": [_columna("estrategia", "7. Estrategia(s)"),
                          _columna("tactica", "8. Táctica(s)"),
                          _columna("recursos_lugar", "9. Recursos en el lugar", "12%"),
                          _columna("recursos_solicitar", "9. Recursos por solicitar", "12%"),
                          _columna("asignacion", "10. Asignación / Ubicación")],
             "filas_minimas": 6},
            {"numero": 13, "nombre": "mensaje_seguridad", "etiqueta": "Mensaje general de seguridad según las amenazas identificadas", "tipo": TEXTAREA, "filas": 4},
            {"numero": 14, "nombre": "pronostico_tiempo", "etiqueta": "Pronóstico del tiempo", "tipo": TEXTAREA, "filas": 3},
            {"numero": 15, "nombre": "organigrama", "etiqueta": "Organigrama para el periodo operacional", "tipo": TEXTAREA, "filas": 6},
        ],
    },
    "203": {
        "nombre": "Listado de Asignación en la Organización",
        "proposito": (
            "Registrar quién ocupa cada posición de la estructura del SCI durante el "
            "periodo operacional. Lo prepara la Unidad de Recursos."
        ),
        "orientacion": "vertical",
        "paginas": 2,
        "periodo_operacional": True,
        "preparado_por": "Unidad de Recursos",
        "secciones": [
            {"numero": 5, "nombre": "comando", "etiqueta": "Comandante de Incidente y Staff", "tipo": TABLA,
             "columnas": [_columna("posicion", "Posición", "40%"), _columna("nombre", "Nombres y apellidos")],
             "filas_fijas": ["Comandante de Incidente (Principal)", "Comandante de Incidente (Adjunto)",
                             "Oficial de Seguridad", "Oficial de Información Pública", "Oficial de Enlace"]},
            {"numero": 6, "nombre": "representantes", "etiqueta": "Representantes institucionales", "tipo": TABLA,
             "columnas": [_columna("institucion", "Institución", "40%"), _columna("nombre", "Nombres y apellidos")],
             "filas_minimas": 4},
            {"numero": 7, "nombre": "planificacion", "etiqueta": "Sección de Planificación", "tipo": TABLA,
             "columnas": [_columna("posicion", "Posición", "40%"), _columna("nombre", "Nombres y apellidos")],
             "filas_fijas": ["Jefe de Sección", "Unidad de Recursos", "Unidad de Situación",
                             "Unidad de Documentación", "Unidad de Desmovilización", "Técnicos especialistas"]},
            {"numero": 8, "nombre": "logistica", "etiqueta": "Sección de Logística", "tipo": TABLA,
             "columnas": [_columna("posicion", "Posición", "40%"), _columna("nombre", "Nombres y apellidos")],
             "filas_fijas": ["Jefe de Sección", "A. Rama de Soporte — Coordinador",
                             "A. Rama de Soporte — Unidad de Suministros",
                             "A. Rama de Soporte — Unidad de Instalaciones",
                             "A. Rama de Soporte — Unidad de Transporte",
                             "B. Rama de Servicios — Unidad de Comunicaciones",
                             "B. Rama de Servicios — Unidad Médica",
                             "B. Rama de Servicios — Unidad de Alimentación"]},
            {"numero": 9, "nombre": "operaciones", "etiqueta": "Sección de Operaciones", "tipo": TABLA,
             "columnas": [_columna("posicion", "Posición / Rama", "30%"),
                          _columna("division", "División o grupo", "25%"),
                          _columna("nombre", "Nombres y apellidos")],
             "filas_fijas": ["Jefe de Sección", "A. Rama I", "B. Rama II", "C. Rama III",
                             "D. Rama Operaciones Aéreas — Supervisor táctico",
                             "D. Rama Operaciones Aéreas — Supervisor de soporte",
                             "D. Rama Operaciones Aéreas — Supervisor de helicópteros",
                             "D. Rama Operaciones Aéreas — Supervisor de ala fija"]},
            {"numero": 10, "nombre": "finanzas", "etiqueta": "Sección de Administración y Finanzas", "tipo": TABLA,
             "columnas": [_columna("posicion", "Posición", "40%"), _columna("nombre", "Nombres y apellidos")],
             "filas_fijas": ["Jefe de Sección", "Unidad de Tiempos", "Unidad de Proveeduría",
                             "Unidad de Costos", "Unidad de Pagos"]},
        ],
    },
    "204": {
        "nombre": "Asignaciones Tácticas",
        "proposito": (
            "Detallar la asignación táctica de una rama, división o grupo. Se llena una "
            "copia por cada posición de la Sección de Operaciones."
        ),
        "orientacion": "horizontal",
        "paginas": 1,
        "periodo_operacional": True,
        "preparado_por": "Jefe de la Sección de Planificación (JSP)",
        "secciones": [
            {"numero": 6, "nombre": "posicion_operaciones", "etiqueta": "Posición en la Sección de Operaciones", "tipo": TEXTO,
             "ayuda": "Coordinador de Rama, Supervisor de División, Supervisor de Grupo, Líder de Fuerza de Tarea, "
                      "Líder de Equipo de Intervención, Líder de Recurso Simple o Encargado."},
            {"numero": 6, "nombre": "nombre_especifico", "etiqueta": "Nombre específico de la posición", "tipo": TEXTO},
            {"numero": 7, "nombre": "recursos", "etiqueta": "Recursos asignados", "tipo": TABLA,
             "columnas": [_columna("responsable", "Nombre del responsable bajo su cargo", "35%"),
                          _columna("funcion", "Función a desempeñar"),
                          _columna("observaciones", "Observaciones", "25%")],
             "filas_minimas": 8},
            {"numero": 8, "nombre": "instrucciones", "etiqueta": "Instrucciones tácticas", "tipo": TEXTAREA, "filas": 5},
            {"numero": 9, "nombre": "comunicaciones", "etiqueta": "Comunicaciones", "tipo": TEXTAREA,
             "ayuda": "Canal y forma de contacto con el PC y con las demás posiciones.", "filas": 4},
        ],
    },
    "205": {
        "nombre": "Plan de Comunicaciones",
        "proposito": (
            "Asignar los canales y equipos de comunicación del periodo operacional. "
            "Lo prepara el Líder de la Unidad de Comunicaciones."
        ),
        "orientacion": "vertical",
        "paginas": 1,
        "periodo_operacional": True,
        "preparado_por": "Líder de la Unidad de Comunicaciones (LUCO)",
        "secciones": [
            {"numero": 6, "nombre": "canales", "etiqueta": "Distribución de canales de comunicación", "tipo": TABLA,
             "columnas": [_columna("sistema", "6. Sistema / Equipo", "20%"),
                          _columna("canal", "7. Canal", "12%"),
                          _columna("asignado", "8. Asignado a", "23%"),
                          _columna("ubicacion", "9. Ubicación", "20%"),
                          _columna("observaciones", "10. Observaciones")],
             "filas_minimas": 10},
        ],
    },
    "206": {
        "nombre": "Plan Médico",
        "proposito": (
            "Definir la asistencia médica disponible para el personal del incidente y la "
            "derivación de pacientes. Lo prepara el Líder de la Unidad Médica."
        ),
        "orientacion": "vertical",
        "paginas": 1,
        "periodo_operacional": True,
        "preparado_por": "Líder de la Unidad Médica",
        "secciones": [
            {"numero": 6, "nombre": "asistencia", "etiqueta": "A. Asistencia médica", "tipo": TABLA,
             "columnas": [_columna("instalacion", "6. Nombre de la instalación de asistencia médica", "30%"),
                          _columna("institucion", "7. Nombre de la institución", "25%"),
                          _columna("ubicacion", "9. Ubicación", "25%"),
                          _columna("contacto", "10. Forma de contacto")],
             "filas_minimas": 4},
            {"numero": 11, "nombre": "ambulancias", "etiqueta": "B. Servicios de ambulancia requeridos", "tipo": TABLA,
             "columnas": [_columna("clase_tipo", "11. Clase y tipo", "25%"),
                          _columna("institucion", "12. Institución", "30%"),
                          _columna("observaciones", "13. Observaciones")],
             "filas_minimas": 4},
            {"numero": 14, "nombre": "derivacion", "etiqueta": "C. Derivación de pacientes", "tipo": TABLA,
             "columnas": [_columna("clasificacion", "14. Clasificación (rojo / amarillo / verde)", "22%"),
                          _columna("instalacion", "15. Institución de asistencia médica", "33%"),
                          _columna("transporte", "16. Medio de transporte (ambulancia / aéreo / otro)", "25%"),
                          _columna("observaciones", "Observaciones")],
             "filas_minimas": 4},
        ],
    },
    "207": {
        "nombre": "Registro de Pacientes / Víctimas",
        "proposito": (
            "Llevar el registro y control de los pacientes atendidos en el ACV o en la "
            "Unidad Médica y trasladados a una institución de asistencia médica. "
            "Este formulario no acompaña al PAI."
        ),
        "orientacion": "horizontal",
        "paginas": 1,
        "periodo_operacional": False,
        "preparado_por": "Líder de la Unidad Médica o Encargado del Área de Clasificación del ACV",
        "aviso": "Contiene datos personales sensibles. Entregue el original a la Unidad de Documentación.",
        "secciones": [
            {"numero": 2, "nombre": "lugar_registro", "etiqueta": "Lugar de registro", "tipo": TEXTO,
             "ayuda": "Área de Concentración de Víctimas (ACV) o Unidad Médica (UM)."},
            {"numero": 3, "nombre": "responsable_posicion", "etiqueta": "Nombre del responsable de la posición", "tipo": TEXTO},
            {"numero": 4, "nombre": "pacientes", "etiqueta": "Registro de pacientes", "tipo": TABLA,
             "columnas": [_columna("nombre", "4. Nombres y apellidos", "22%"),
                          _columna("sexo", "5. Sexo", "8%"),
                          _columna("edad", "6. Edad", "7%"),
                          _columna("clasificacion", "7. Clasificación", "13%"),
                          _columna("lugar_traslado", "8. Lugar de traslado", "18%"),
                          _columna("trasladado_por", "9. Trasladado por", "17%"),
                          _columna("fecha_hora", "10. Fecha y hora", "15%")],
             "filas_minimas": 12},
        ],
    },
    "214": {
        "nombre": "Registro de Actividades",
        "proposito": (
            "Llevar la bitácora cronológica de los eventos principales de una posición "
            "durante el periodo operacional."
        ),
        "orientacion": "vertical",
        "paginas": 1,
        "periodo_operacional": True,
        "preparado_por": "Responsable de la posición (nombres, apellidos, firma y posición)",
        "secciones": [
            {"numero": 6, "nombre": "personal", "etiqueta": "Lista de personal asignado", "tipo": TABLA,
             "columnas": [_columna("nombre", "Nombres y apellidos", "35%"),
                          _columna("posicion", "Posición en el SCI", "30%"),
                          _columna("institucion", "Institución a la que pertenece")],
             "filas_minimas": 6},
            {"numero": 7, "nombre": "actividades", "etiqueta": "Registro de actividades", "tipo": TABLA,
             "columnas": [_columna("hora", "Hora", "12%"), _columna("evento", "Eventos principales")],
             "filas_minimas": 14},
        ],
    },
    "215": {
        "nombre": "Análisis de Seguridad del Plan de Acción del Incidente",
        "proposito": (
            "Identificar los riesgos de cada área de trabajo del PAI y las acciones "
            "mitigantes correspondientes. Corresponde al formulario SCI-215 A."
        ),
        "orientacion": "horizontal",
        "paginas": 1,
        "periodo_operacional": True,
        "preparado_por": "Oficial de Seguridad",
        "secciones": [
            {"numero": 1, "nombre": "analisis", "etiqueta": "Análisis de seguridad por área", "tipo": TABLA,
             "columnas": [_columna("area", "Área", "25%"),
                          _columna("riesgo", "Riesgo", "35%"),
                          _columna("accion", "Acción mitigante")],
             "filas_minimas": 10},
        ],
    },
    "221": {
        "nombre": "Verificación de la Desmovilización",
        "proposito": (
            "Verificar que los recursos que salen de la escena hayan completado su misión "
            "y los trámites previos a su salida. El personal y los recursos no se liberan "
            "hasta que hayan cumplido lo requerido para su sección."
        ),
        "orientacion": "vertical",
        "paginas": 2,
        "periodo_operacional": True,
        "preparado_por": "Líder de la Unidad de Desmovilización o Jefe de la Sección de Planificación",
        "secciones": [
            {"numero": 4, "nombre": "tiempo_conclusion", "etiqueta": "Tiempo estimado de conclusión", "tipo": FECHA_HORA,
             "ayuda": "Fecha y hora en la que se estima concluir la desmovilización."},
            {"numero": 5, "nombre": "verif_planificacion", "etiqueta": "Lista de verificación — Sección de Planificación (JSP)", "tipo": TABLA,
             "columnas": [_columna("accion", "Acción de verificación", "45%"),
                          _columna("cumplido", "Cumplido", "12%"),
                          _columna("observaciones", "Observaciones")],
             "filas_minimas": 5, "firma": "Firma del JSP"},
            {"numero": 6, "nombre": "verif_operaciones", "etiqueta": "Lista de verificación — Sección de Operaciones (JSO)", "tipo": TABLA,
             "columnas": [_columna("accion", "Acción de verificación", "45%"),
                          _columna("cumplido", "Cumplido", "12%"),
                          _columna("observaciones", "Observaciones")],
             "filas_minimas": 5, "firma": "Firma del JSO"},
            {"numero": 7, "nombre": "verif_logistica", "etiqueta": "Lista de verificación — Sección de Logística (JSL)", "tipo": TABLA,
             "columnas": [_columna("accion", "Acción de verificación", "45%"),
                          _columna("cumplido", "Cumplido", "12%"),
                          _columna("observaciones", "Observaciones")],
             "filas_minimas": 5, "firma": "Firma del JSL"},
            {"numero": 8, "nombre": "verif_finanzas", "etiqueta": "Lista de verificación — Sección de Administración y Finanzas (JSAF)", "tipo": TABLA,
             "columnas": [_columna("accion", "Acción de verificación", "45%"),
                          _columna("cumplido", "Cumplido", "12%"),
                          _columna("observaciones", "Observaciones")],
             "filas_minimas": 5, "firma": "Firma del JSAF"},
        ],
    },
    "222": {
        "nombre": "Prioridades y Asignación de Recursos",
        "proposito": (
            "Hoja de trabajo del Comando de Área para priorizar incidentes y distribuir "
            "los recursos críticos entre ellos (versión 2018)."
        ),
        "orientacion": "horizontal",
        "paginas": 1,
        "periodo_operacional": True,
        "preparado_por": "Comando de Área (nombre y posición)",
        "secciones": [
            {"numero": 1, "nombre": "identificacion_comando", "etiqueta": "Identificación del Comando de Área", "tipo": TEXTO},
            {"numero": 4, "nombre": "matriz", "etiqueta": "Prioridades y recursos críticos por incidente", "tipo": TABLA,
             "columnas": [_columna("prioridad", "4. Prioridad del incidente", "10%"),
                          _columna("incidente", "5. Incidente", "22%"),
                          _columna("recurso", "6. Recurso crítico", "18%"),
                          _columna("tiene", "Tiene", "8%"),
                          _columna("falta", "Falta", "8%"),
                          _columna("requiere", "Requiere", "8%"),
                          _columna("observaciones", "7. Observaciones")],
             "filas_minimas": 10},
            {"numero": 8, "nombre": "total_requeridos", "etiqueta": "Total de recursos requeridos", "tipo": TEXTO},
            {"numero": 9, "nombre": "total_existentes", "etiqueta": "Total de recursos existentes", "tipo": TEXTO},
            {"numero": 10, "nombre": "total_faltantes", "etiqueta": "Total de recursos faltantes", "tipo": TEXTO},
        ],
    },
}

# Campos 3, 4 y 5 comunes a los formularios que trabajan por periodo operacional.
CAMPOS_PERIODO_OPERACIONAL = (
    {"numero": 3, "nombre": "periodo_numero", "etiqueta": "Periodo operacional N.º", "tipo": TEXTO},
    {"numero": 4, "nombre": "periodo_inicio", "etiqueta": "Fecha y hora de inicio del periodo operacional", "tipo": FECHA_HORA},
    {"numero": 5, "nombre": "periodo_fin", "etiqueta": "Fecha y hora de finalización del periodo operacional", "tipo": FECHA_HORA},
)

LIMITE_TEXTO = 5000
LIMITE_FILAS = 60


def obtener_esquema(codigo):
    """Devuelve el esquema del formulario o ``None`` si el código no existe."""
    return ESQUEMAS_SCI.get(codigo)


def campos_periodo(esquema):
    return CAMPOS_PERIODO_OPERACIONAL if esquema.get("periodo_operacional") else ()


def _limpiar(valor):
    return str(valor or "").strip()[:LIMITE_TEXTO]


def secciones_con_valores(esquema, datos):
    """Combina el esquema con los datos guardados para renderizar el formulario."""
    resultado = []
    for seccion in esquema["secciones"]:
        item = dict(seccion)
        if seccion["tipo"] == TABLA:
            item["filas"] = _filas_para_render(seccion, datos.get(seccion["nombre"]))
            item["firma_valor"] = datos.get(f"{seccion['nombre']}__firma", "")
        else:
            item["valor"] = datos.get(seccion["nombre"], "")
        resultado.append(item)
    return resultado


def _filas_para_render(seccion, guardadas):
    columnas = seccion["columnas"]
    guardadas = guardadas if isinstance(guardadas, list) else []
    fijas = seccion.get("filas_fijas")
    if fijas:
        filas = []
        for indice, etiqueta in enumerate(fijas):
            origen = guardadas[indice] if indice < len(guardadas) and isinstance(guardadas[indice], dict) else {}
            celdas = [{"columna": columna, "valor": origen.get(columna["nombre"], "")} for columna in columnas]
            celdas[0]["fija"] = etiqueta
            celdas[0]["valor"] = etiqueta
            filas.append({"celdas": celdas})
        return filas
    minimas = seccion.get("filas_minimas", 5)
    total = max(minimas, len(guardadas))
    filas = []
    for indice in range(total):
        origen = guardadas[indice] if indice < len(guardadas) and isinstance(guardadas[indice], dict) else {}
        filas.append({"celdas": [{"columna": columna, "valor": origen.get(columna["nombre"], "")}
                                 for columna in columnas]})
    return filas


def extraer_datos(esquema, post):
    """Traduce un POST del editor a la estructura que se guarda en ``datos``."""
    datos = {}
    for campo in campos_periodo(esquema):
        datos[campo["nombre"]] = _limpiar(post.get(campo["nombre"]))
    for seccion in esquema["secciones"]:
        nombre = seccion["nombre"]
        if seccion["tipo"] != TABLA:
            datos[nombre] = _limpiar(post.get(nombre))
            continue
        filas = []
        indices = _indices_enviados(post, nombre, seccion)
        for indice in indices:
            fila = {columna["nombre"]: _limpiar(post.get(f"{nombre}-{indice}-{columna['nombre']}"))
                    for columna in seccion["columnas"]}
            if any(fila.values()):
                filas.append(fila)
        datos[nombre] = filas
        if seccion.get("firma"):
            datos[f"{nombre}__firma"] = _limpiar(post.get(f"{nombre}__firma"))
    return datos


def _indices_enviados(post, nombre, seccion):
    primera = seccion["columnas"][0]["nombre"]
    prefijo = f"{nombre}-"
    sufijo = f"-{primera}"
    indices = set()
    for clave in post:
        if clave.startswith(prefijo) and clave.endswith(sufijo):
            crudo = clave[len(prefijo):-len(sufijo)]
            if crudo.isdigit():
                indices.add(int(crudo))
    return sorted(indices)[:LIMITE_FILAS]


def secciones_completadas(esquema, datos):
    """Cuenta cuántas secciones del formulario tienen datos reales.

    En las tablas con ``filas_fijas`` la primera columna viene precargada con la
    posición oficial, así que no se toma en cuenta para decidir si hay contenido.
    """
    datos = datos or {}
    llenas = 0
    for seccion in esquema["secciones"]:
        valor = datos.get(seccion["nombre"])
        if seccion["tipo"] != TABLA:
            llenas += bool(str(valor or "").strip())
            continue
        filas = valor if isinstance(valor, list) else []
        ignoradas = {seccion["columnas"][0]["nombre"]} if seccion.get("filas_fijas") else set()
        llenas += any(
            str(celda or "").strip()
            for fila in filas if isinstance(fila, dict)
            for nombre, celda in fila.items() if nombre not in ignoradas
        )
    return llenas, len(esquema["secciones"])


# El SCI-211 se captura con su modelo propio, pero el catálogo debe poder mostrar
# su estructura oficial en blanco igual que la de los demás formularios.
ESQUEMA_CATALOGO_211 = {
    "nombre": "Registro y Control de Recursos",
    "proposito": (
        "Fuente maestra de recursos del incidente: solicitud, arribo, institución "
        "que lo suministra, estado, asignación y desmovilización de cada recurso."
    ),
    "orientacion": "horizontal",
    "paginas": 2,
    "periodo_operacional": False,
    "preparado_por": "Registrador del punto de registro (PC, Base, Helibase o Área de Espera)",
    "secciones": [
        {"numero": 1, "nombre": "recursos", "etiqueta": "Registro y control de recursos", "tipo": TABLA,
         "columnas": [_columna("solicitado_por", "A. Solicitud — 1. Por quién", "11%"),
                      _columna("fecha_solicitud", "2. Fecha y hora", "9%"),
                      _columna("clase", "3. Clase", "8%"),
                      _columna("tipo", "4. Tipo", "8%"),
                      _columna("fecha_arribo", "B. Arribo real — 5. Fecha y hora", "9%"),
                      _columna("institucion", "C. Suministrado por — 6. Institución", "12%"),
                      _columna("matricula", "7. Matrícula", "8%"),
                      _columna("personas", "8. N.º de personas", "6%"),
                      _columna("estado", "D. Estado del recurso", "10%"),
                      _columna("desmovilizado_por", "E. Desmovilizado — 10. Por quién", "10%"),
                      _columna("fecha_desmovilizacion", "11. Fecha y hora", "9%"),
                      _columna("observaciones", "12. Observaciones")],
         "filas_minimas": 12},
    ],
}


def obtener_esquema_catalogo(codigo):
    """Como ``obtener_esquema`` pero incluye el SCI-211 para la vista de catálogo."""
    if codigo == "211":
        return ESQUEMA_CATALOGO_211
    return ESQUEMAS_SCI.get(codigo)
