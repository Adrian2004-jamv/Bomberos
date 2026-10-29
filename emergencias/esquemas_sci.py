"""Esquemas declarativos de los formularios SCI distintos del SCI-211.

Cada esquema reproduce la numeración y la estructura del formulario oficial
(Rev. 06-2015, SCI-222 versión 2018). El SCI-211 no aparece aquí porque tiene
modelo propio en ``models.FormularioSCI211``.

Los datos capturados se guardan en ``FormularioSCI.datos`` con esta forma:

* campos simples      -> ``{"nombre_campo": "valor"}``
* tablas repetibles   -> ``{"nombre_tabla": [{"columna": "valor"}, ...]}``
* listas de chequeo   -> ``{"nombre_lista": {"filas": [...], "firma": "..."}}``
"""

import re
from datetime import datetime

from .graficos_sci import (clave_dibujo, clave_grafico, limpiar_croquis,
                           limpiar_organigrama, organigrama_svg)

TEXTO = "texto"
TEXTAREA = "textarea"
FECHA_HORA = "fecha_hora"
HORA = "hora"
TABLA = "tabla"
SELECCION = "seleccion"
NUMERO = "numero"
# Campos gráficos: un dibujo a mano alzada y un organigrama de cajas. Cada uno
# guarda, además del texto que ya tenía el campo, su gráfico (ver graficos_sci).
CROQUIS = "croquis"
ORGANIGRAMA = "organigrama"
TIPOS_GRAFICOS = (CROQUIS, ORGANIGRAMA)
SUFIJOS_GRAFICOS = ("__dibujo", "__grafico")

# Formatos que produce cada control del navegador. Sirven para reconocer un
# valor guardado antes de que la columna tuviera tipo: si no encaja se muestra
# como texto, de modo que nadie pierde lo que ya habia escrito.
_PATRONES = {
    FECHA_HORA: re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$"),
    HORA: re.compile(r"^\d{2}:\d{2}(:\d{2})?$"),
}

# De qué conjunto se surte una columna de recursos. «Inventario» es todo lo que
# la institución tiene; «en el lugar» son los que el SCI-211 ya registró en esta
# emergencia, que es lo único que puede estar en la escena.
# Formularios que son bitácoras y no documentos: se escriben durante toda la
# intervención y solo se cierran cuando la emergencia termina. Vive aquí, con
# el resto de la declaración de los formularios, porque lo consultan tanto las
# vistas como los servicios y ninguno de los dos debe depender del otro.
#
#   211 · Registro y Control de Recursos: las unidades siguen llegando.
#   214 · Registro de Actividades: es la bitácora cronológica del periodo.
FORMULARIOS_SCI_CONTINUOS = frozenset({"211", "214"})

ORIGEN_INVENTARIO = "inventario"
ORIGEN_EN_EL_LUGAR = "en_el_lugar"

def _columna(nombre, etiqueta, ancho="", recurso_inventario=False, tipo=TEXTO,
             opciones=None, origen=ORIGEN_INVENTARIO):
    return {
        "nombre": nombre,
        "etiqueta": etiqueta,
        "ancho": ancho,
        "recurso_inventario": recurso_inventario,
        "tipo": tipo,
        "opciones": opciones or [],
        "origen": origen,
    }

# El punto 4 del SCI-201 enumera cuatro cosas distintas —naturaleza, amenazas,
# áreas afectadas y aislamiento— y el formulario oficial las lista como viñetas
# de un mismo renglón. Se guardaban en un solo texto, y ese texto no se puede
# consultar: no hay manera de preguntar «cuántos incidentes tuvieron áreas
# afectadas con riesgo de colapso» sobre un párrafo donde alguien mezcló las
# cuatro cosas a su manera. Cada una es ahora su propio campo, con su propia
# clave en ``datos``, de modo que los reportes y las estadísticas puedan leerla.
EVALUACION_INICIAL = (
    ("evaluacion_naturaleza", "Naturaleza del incidente"),
    ("evaluacion_amenazas", "Amenazas"),
    ("evaluacion_areas_afectadas", "Áreas afectadas"),
    ("evaluacion_aislamiento", "Aislamiento"),
)

# La clave antigua, de cuando el punto 4 era una sola casilla. No se migra a los
# cuatro campos porque no hay manera de saber dónde acaba la naturaleza y dónde
# empiezan las amenazas en un párrafo escrito a mano, y repartirlo por
# adivinación sería inventar datos en un expediente. Se conserva tal cual y se
# muestra mientras los cuatro campos nuevos sigan vacíos.
EVALUACION_INICIAL_HEREDADA = "evaluacion_inicial"

# Campos que un formulario tuvo y ya no tiene. Al guardar se vuelven a escribir
# tal como estaban: ``extraer_datos`` solo conoce el esquema vigente y sin esto
# el primer guardado borraría en silencio lo que alguien escribió con el esquema
# anterior.
CAMPOS_RETIRADOS = {"201": (EVALUACION_INICIAL_HEREDADA,)}

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
            # Campo 3 — Lugar del incidente (fila completa, auto-completado)
            {"numero": 3, "nombre": "lugar_incidente", "obligatorio": True, "etiqueta": "Lugar del incidente", "tipo": TEXTO,
             "ayuda": "Se completa automáticamente con la dirección registrada en la emergencia."},
            # Campo 4 — Evaluación inicial: un campo por cada sub-punto. Todos son
            # obligatorios para finalizar; si uno no aplica se escribe «No aplica»,
            # que también es una respuesta.
            *[
                {"numero": 4, "nombre": nombre, "grupo": "evaluacion_inicial",
                 "obligatorio": True,
                 "etiqueta": f"Evaluación inicial — {etiqueta}", "tipo": TEXTAREA,
                 "filas": 3}
                for nombre, etiqueta in EVALUACION_INICIAL
            ],
            # Campos 5, 6, 7 en una misma sección (se renderizan en 3 columnas en el preview)
            {"numero": 5, "nombre": "objetivos_iniciales", "obligatorio": True, "etiqueta": "Objetivo(s) inicial(es)", "tipo": TEXTAREA, "filas": 6},
            {"numero": 6, "nombre": "estrategias", "etiqueta": "Estrategias", "tipo": TEXTAREA, "filas": 6},
            {"numero": 7, "nombre": "tacticas", "etiqueta": "Tácticas", "tipo": TEXTAREA, "filas": 6},
            # Campos 8-9 en 2 columnas
            {"numero": 8, "nombre": "ubicacion_pc", "etiqueta": "Ubicación del Puesto de Comando (PC)", "tipo": TEXTO},
            {"numero": 9, "nombre": "ubicacion_e", "etiqueta": "Ubicación del Área de Espera (E)", "tipo": TEXTO},
            # Campos 10-11 en 2 columnas
            {"numero": 10, "nombre": "ruta_ingreso", "etiqueta": "Ruta de ingreso", "tipo": TEXTO},
            {"numero": 11, "nombre": "ruta_egreso", "etiqueta": "Ruta de egreso", "tipo": TEXTO},
            # Campo 12 — Seguridad
            {"numero": 12, "nombre": "mensaje_seguridad", "etiqueta": "Mensaje general de seguridad", "tipo": TEXTAREA, "filas": 4},
            # Campo 14 — Mapa/Croquis (página 2 completa)
            {"numero": 14, "nombre": "croquis", "etiqueta": "Mapa situacional o croquis", "tipo": CROQUIS,
             "ayuda": "Suba una foto o un plano, o capture el mapa del lugar. La nota de abajo es opcional.",
             "filas": 3},
            # Campos 15-16 — Tabla cronológica de acciones (página 3)
            {"numero": 16, "nombre": "acciones", "fila": "acción", "etiqueta": "Resumen de las acciones", "tipo": TABLA,
             "columnas": [_columna("fecha_hora", "15. Fecha y Hora", "22%", tipo=FECHA_HORA),
                          _columna("accion", "16. Resumen de la acción")],
             "filas_impresion": 24},
            # Campo 17 — Organigrama (página 4)
            {"numero": 17, "nombre": "organigrama", "etiqueta": "Organigrama actual", "tipo": ORGANIGRAMA,
             "ayuda": "Arrastre las cajas y conéctelas. La nota de abajo, con el responsable de cada posición, es opcional.",
             "filas": 3},
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
            {"numero": 6, "nombre": "objetivos", "obligatorio": True, "etiqueta": "Objetivo(s)", "tipo": TEXTAREA, "filas": 4},
            {"numero": 7, "nombre": "plan", "fila": "estrategia", "etiqueta": "Estrategias, tácticas y asignación de recursos", "tipo": TABLA,
             "columnas": [_columna("estrategia", "7. Estrategia(s)"),
                          _columna("tactica", "8. Táctica(s)"),
                          _columna("recursos_lugar", "9. Recursos en el lugar", "12%", True,
                                   origen=ORIGEN_EN_EL_LUGAR),
                          _columna("recursos_solicitar", "9. Recursos por solicitar", "12%", True),
                          _columna("asignacion", "10. Asignación / Ubicación")],
             "filas_impresion": 6},
            {"numero": 13, "nombre": "mensaje_seguridad", "etiqueta": "Mensaje general de seguridad según las amenazas identificadas", "tipo": TEXTAREA, "filas": 4},
            {"numero": 14, "nombre": "pronostico_tiempo", "etiqueta": "Pronóstico del tiempo", "tipo": TEXTAREA, "filas": 3},
            {"numero": 15, "nombre": "organigrama", "etiqueta": "Organigrama para el periodo operacional", "tipo": ORGANIGRAMA,
             "ayuda": "Arrastre las cajas y conéctelas. La nota de abajo, con el responsable de cada posición, es opcional.",
             "filas": 3},
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
            {"numero": 5, "nombre": "comando", "obligatorio": True, "etiqueta": "Comandante de Incidente y Staff", "tipo": TABLA,
             "columnas": [_columna("posicion", "Posición", "40%"), _columna("nombre", "Nombres y apellidos")],
             "filas_fijas": ["Comandante de Incidente (Principal)", "Comandante de Incidente (Adjunto)",
                             "Oficial de Seguridad", "Oficial de Información Pública", "Oficial de Enlace"]},
            {"numero": 6, "nombre": "representantes", "fila": "institución", "etiqueta": "Representantes institucionales", "tipo": TABLA,
             "columnas": [_columna("institucion", "Institución", "40%"), _columna("nombre", "Nombres y apellidos")],
             "filas_impresion": 4},
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
        "aprobado_por": "Jefe de la Sección de Operaciones",
        "secciones": [
            {"numero": 6, "nombre": "posicion_operaciones", "etiqueta": "Posición en la Sección de Operaciones", "tipo": TEXTO, "obligatorio": True,
             "ayuda": "Coordinador de Rama, Supervisor de División, Supervisor de Grupo, Líder de Fuerza de Tarea, "
                      "Líder de Equipo de Intervención, Líder de Recurso Simple o Encargado."},
            {"numero": 6, "nombre": "nombre_especifico", "etiqueta": "Nombre específico de la posición", "tipo": TEXTO},
            {"numero": 7, "nombre": "recursos", "fila": "recurso", "etiqueta": "Recursos asignados", "tipo": TABLA,
             "obligatorio": True,
             "columnas": [_columna("recurso", "Recurso verificado", "17%", True),
                          _columna("responsable", "Nombre del responsable bajo su cargo", "17%"),
                          _columna("funcion", "Función a desempeñar", "14%"),
                          # Las tres que faltaban frente al formulario oficial.
                          _columna("asignacion_tactica", "Asignación táctica", "16%"),
                          _columna("ubicacion", "Ubicación", "14%"),
                          _columna("personas_a_cargo", "N.º de personas a cargo", "8%",
                                   tipo=NUMERO),
                          _columna("observaciones", "Observaciones", "14%")],
             "filas_impresion": 8},
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
            {"numero": 6, "nombre": "canales", "fila": "canal", "obligatorio": True, "etiqueta": "Distribución de canales de comunicación", "tipo": TABLA,
             "columnas": [_columna("sistema", "6. Sistema / Equipo", "20%", True),
                          _columna("canal", "7. Canal", "12%"),
                          _columna("asignado", "8. Asignado a", "23%"),
                          _columna("ubicacion", "9. Ubicación", "20%"),
                          _columna("observaciones", "10. Observaciones")],
             "filas_impresion": 10},
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
            # Los campos 6 y 7 describen la Unidad Médica del incidente —una
            # sola— y estaban metidos como columnas de la tabla A, que enumera
            # las instalaciones de la periferia. Al mezclarlos se perdió el
            # campo 8 y la numeración de la tabla quedó corrida.
            {"numero": 6, "nombre": "instalacion_um", "tipo": TEXTO, "obligatorio": True,
             "etiqueta": "Nombre de la instalación de asistencia médica"},
            {"numero": 7, "nombre": "ubicacion_um", "tipo": TEXTO, "obligatorio": True,
             "etiqueta": "Ubicación de la Unidad Médica",
             "ayuda": "Ubicación geográfica de la Unidad Médica dentro del incidente."},
            {"numero": 8, "nombre": "asistencia", "fila": "instalación", "etiqueta": "A. Asistencia médica", "tipo": TABLA,
             "ayuda": "Instalaciones de asistencia médica en la periferia del incidente.",
             "columnas": [_columna("institucion", "8. Nombre de la institución", "32%"),
                          _columna("ubicacion", "9. Ubicación", "30%"),
                          _columna("contacto", "10. Forma de contacto")],
             "filas_impresion": 4},
            {"numero": 11, "nombre": "ambulancias", "fila": "ambulancia", "etiqueta": "B. Servicios de ambulancia requeridos", "tipo": TABLA,
             "columnas": [_columna("clase_tipo", "11. Ambulancia verificada", "25%", True),
                          _columna("institucion", "12. Institución", "30%"),
                          _columna("observaciones", "13. Observaciones")],
             "filas_impresion": 4},
            {"numero": 14, "nombre": "derivacion", "fila": "derivación", "etiqueta": "C. Derivación de pacientes", "tipo": TABLA,
             "columnas": [_columna("clasificacion", "14. Clasificación (rojo / amarillo / verde)", "22%"),
                          _columna("instalacion", "15. Institución de asistencia médica", "33%"),
                          _columna("transporte", "16. Medio de transporte verificado", "25%", True),
                          _columna("observaciones", "Observaciones")],
             "filas_impresion": 4},
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
            {"numero": 4, "nombre": "pacientes", "fila": "paciente", "obligatorio": True, "etiqueta": "Registro de pacientes", "tipo": TABLA,
             "columnas": [_columna("nombre", "4. Nombres y apellidos", "22%"),
                          _columna("sexo", "5. Sexo", "8%", tipo=SELECCION, opciones=["M", "F", "Otro"]),
                          _columna("edad", "6. Edad", "7%", tipo=NUMERO),
                          _columna("clasificacion", "7. Clasificación", "13%"),
                          _columna("lugar_traslado", "8. Lugar de traslado", "18%"),
                          _columna("trasladado_por", "9. Trasladado por", "17%"),
                          _columna("fecha_hora", "10. Fecha y hora", "15%", tipo=FECHA_HORA)],
             "filas_impresion": 12},
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
            {"numero": 6, "nombre": "personal", "fila": "persona", "etiqueta": "Lista de personal asignado", "tipo": TABLA,
             "columnas": [_columna("nombre", "Nombres y apellidos", "35%"),
                          _columna("posicion", "Posición en el SCI", "30%"),
                          _columna("institucion", "Institución a la que pertenece")],
             "filas_impresion": 6},
            {"numero": 7, "nombre": "actividades", "fila": "actividad", "obligatorio": True, "etiqueta": "Registro de actividades", "tipo": TABLA,
             "columnas": [_columna("hora", "Hora", "12%", tipo=HORA), _columna("evento", "Eventos principales")],
             "filas_impresion": 14},
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
            {"numero": 1, "nombre": "analisis", "fila": "área", "obligatorio": True, "etiqueta": "Análisis de seguridad por área", "tipo": TABLA,
             "columnas": [_columna("area", "Área", "25%"),
                          _columna("riesgo", "Riesgo", "35%"),
                          _columna("accion", "Acción mitigante")],
             "filas_impresion": 10},
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
            {"numero": 5, "nombre": "verif_planificacion", "fila": "verificación", "etiqueta": "Lista de verificación — Sección de Planificación (JSP)", "tipo": TABLA,
             "columnas": [_columna("accion", "Acción de verificación", "45%"),
                          _columna("cumplido", "Cumplido", "12%"),
                          _columna("observaciones", "Observaciones")],
             "filas_impresion": 5, "firma": "Firma del JSP"},
            {"numero": 6, "nombre": "verif_operaciones", "fila": "verificación", "etiqueta": "Lista de verificación — Sección de Operaciones (JSO)", "tipo": TABLA,
             "columnas": [_columna("accion", "Acción de verificación", "45%"),
                          _columna("cumplido", "Cumplido", "12%"),
                          _columna("observaciones", "Observaciones")],
             "filas_impresion": 5, "firma": "Firma del JSO"},
            {"numero": 7, "nombre": "verif_logistica", "fila": "verificación", "etiqueta": "Lista de verificación — Sección de Logística (JSL)", "tipo": TABLA,
             "columnas": [_columna("accion", "Acción de verificación", "45%"),
                          _columna("cumplido", "Cumplido", "12%"),
                          _columna("observaciones", "Observaciones")],
             "filas_impresion": 5, "firma": "Firma del JSL"},
            {"numero": 8, "nombre": "verif_finanzas", "fila": "verificación", "etiqueta": "Lista de verificación — Sección de Administración y Finanzas (JSAF)", "tipo": TABLA,
             "columnas": [_columna("accion", "Acción de verificación", "45%"),
                          _columna("cumplido", "Cumplido", "12%"),
                          _columna("observaciones", "Observaciones")],
             "filas_impresion": 5, "firma": "Firma del JSAF"},
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
            {"numero": 1, "nombre": "identificacion_comando", "obligatorio": True, "etiqueta": "Identificación del Comando de Área", "tipo": TEXTO},
            {"numero": 4, "nombre": "matriz", "fila": "prioridad", "etiqueta": "Prioridades y recursos críticos por incidente", "tipo": TABLA,
             "columnas": [_columna("prioridad", "4. Prioridad del incidente", "10%"),
                          _columna("incidente", "5. Incidente", "22%"),
                          _columna("recurso", "6. Recurso crítico", "18%", True),
                          _columna("tiene", "Tiene", "8%"),
                          _columna("falta", "Falta", "8%"),
                          _columna("requiere", "Requiere", "8%"),
                          _columna("observaciones", "7. Observaciones")],
             "filas_impresion": 10},
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

def limpiar(valor):
    return str(valor or "").strip()[:LIMITE_TEXTO]

# Cómo se dibuja una tabla según para qué sea la pantalla:
#
# * EDICION: una sola fila vacía para empezar y el botón de agregar las demás.
# * LECTURA: solo las filas que tienen datos, ni una más. Es la hoja impresa y
#   también todo documento de solo lectura: un expediente no lleva renglones de
#   relleno, y una estrategia registrada se imprime como una fila, no como una
#   fila entre seis vacías.
# * BLANCO: los renglones que declara ``filas_impresion``, para el formulario en
#   blanco del catálogo, que no pertenece a ningún incidente y se imprime para
#   escribirlo a mano.
MODO_EDICION = "edicion"
MODO_LECTURA = "lectura"
MODO_BLANCO = "blanco"

def secciones_con_valores(esquema, datos, modo=MODO_EDICION):
    """Combina el esquema con los datos guardados para renderizar el formulario.

    ``modo`` decide qué filas lleva cada tabla; ver ``MODO_EDICION``,
    ``MODO_LECTURA`` y ``MODO_BLANCO``.
    """
    resultado = []
    for seccion in esquema["secciones"]:
        item = dict(seccion)
        if seccion["tipo"] == TABLA:
            item["filas"] = filas_para_render(
                seccion, datos.get(seccion["nombre"]), modo
            )
            item["firma_valor"] = datos.get(f"{seccion['nombre']}__firma", "")
        else:
            item["valor"] = datos.get(seccion["nombre"], "")
            if seccion["tipo"] == CROQUIS:
                item["dibujo"] = limpiar_croquis(datos.get(clave_dibujo(seccion["nombre"])))
            elif seccion["tipo"] == ORGANIGRAMA:
                item["grafico"] = limpiar_organigrama(datos.get(clave_grafico(seccion["nombre"])))
                item["svg"] = organigrama_svg(item["grafico"])
        resultado.append(item)
    return resultado

def _celda(columna, valor):
    """Arma una celda y decide el control con que se dibuja.

    Una columna de fecha vuelve a texto cuando el valor guardado no tiene el
    formato que espera el control: es información que alguien escribió antes de
    que la columna tuviera tipo y no debe desaparecer de la pantalla.
    """
    tipo = columna.get("tipo", TEXTO)
    patron = _PATRONES.get(tipo)
    if patron and valor and not patron.match(str(valor)):
        tipo = TEXTO
    # Los tipos seleccion y numero nunca se degradan a texto
    return {"columna": columna, "valor": valor, "tipo": tipo,
            "legible": texto_legible(tipo, valor)}


def texto_legible(tipo, valor):
    """El valor como se lee en una hoja, no como lo pide el control del navegador.

    Un campo de fecha y hora se guarda en el formato que exige
    ``<input type="datetime-local">`` —2026-10-24T17:10—, y eso es lo que salía
    impreso en la hoja oficial y en los periodos cerrados. En papel la fecha se
    escribe como la escribe una persona.
    """
    if tipo == FECHA_HORA and valor:
        try:
            return datetime.fromisoformat(str(valor)).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return valor
    return valor

# Cuántas líneas lleva una tabla impresa si el esquema no lo dice.
FILAS_IMPRESION_POR_DEFECTO = 5

# Los selectores del editor nombran cada recurso y, si no está libre, añaden por qué:
# «AB-01 - Autobomba (Estación Central) · ya asignada a otra emergencia». Esa cadena
# se guarda tal cual como valor de la celda —cambiar lo guardado dejaría sin selección
# los formularios ya llenos—, de modo que el aviso del editor acaba impreso en un
# documento oficial y la celda se desborda. Solo se quita al mostrar; lo guardado no
# se toca. El aviso nunca lleva paréntesis ni otro punto medio, de modo que se corta
# justo detrás del paréntesis de la estación.
_AVISO_DE_DISPONIBILIDAD = re.compile(r"^(.*\)) · [^·()]+$")

def sin_aviso_de_disponibilidad(valor):
    return _AVISO_DE_DISPONIBILIDAD.sub(r"\1", str(valor or ""))

def limpiar_avisos(filas):
    """Quita el aviso de disponibilidad de las celdas de recursos (solo al mostrar)."""
    for fila in filas:
        for celda in fila["celdas"]:
            if celda["columna"].get("recurso_inventario"):
                celda["valor"] = sin_aviso_de_disponibilidad(celda["valor"])
                celda["legible"] = celda["valor"]
    return filas

def fila_con_datos(fila, ignorar_primera=False):
    """Si alguna celda de la fila tiene algo escrito.

    En las tablas de filas fijas la primera celda es el nombre oficial de la
    posición, que está siempre: no cuenta como dato.
    """
    celdas = fila["celdas"][1:] if ignorar_primera else fila["celdas"]
    return any(str(celda["valor"] or "").strip() for celda in celdas)

def filas_para_render(seccion, guardadas, modo=MODO_EDICION):
    columnas = seccion["columnas"]
    guardadas = guardadas if isinstance(guardadas, list) else []
    fijas = seccion.get("filas_fijas")
    if fijas:
        filas = []
        for indice, etiqueta in enumerate(fijas):
            origen = guardadas[indice] if indice < len(guardadas) and isinstance(guardadas[indice], dict) else {}
            celdas = [_celda(columna, origen.get(columna["nombre"], "")) for columna in columnas]
            celdas[0]["fija"] = etiqueta
            celdas[0]["valor"] = etiqueta
            filas.append({"celdas": celdas})
        if modo == MODO_LECTURA:
            # Una posición sin nadie asignado es un renglón vacío con nombre.
            return limpiar_avisos(
                [fila for fila in filas if fila_con_datos(fila, ignorar_primera=True)]
            )
        return filas
    # En pantalla, una sola fila vacía. Antes se precargaban 24 en el SCI-201 y
    # entre 4 y 14 en los demás: nadie las iba a llenar todas, ensuciaban la
    # hoja, obligaban a desplazarse en el teléfono y daban a entender que había
    # que completarlas. Lo que falta se agrega con el botón.
    # En lectura no hay mínimo: solo las filas que existen y tienen algo escrito.
    if modo == MODO_LECTURA:
        minimas = 0
    elif modo == MODO_BLANCO:
        minimas = seccion.get("filas_impresion", FILAS_IMPRESION_POR_DEFECTO)
    else:
        minimas = 1
    total = max(minimas, len(guardadas))
    filas = []
    for indice in range(total):
        origen = guardadas[indice] if indice < len(guardadas) and isinstance(guardadas[indice], dict) else {}
        filas.append({"celdas": [_celda(columna, origen.get(columna["nombre"], ""))
                                 for columna in columnas]})
    if modo == MODO_LECTURA:
        filas = limpiar_avisos([fila for fila in filas if fila_con_datos(fila)])
    return filas

def extraer_datos(esquema, post):
    """Traduce un POST del editor a la estructura que se guarda en ``datos``."""
    datos = {}
    for campo in campos_periodo(esquema):
        datos[campo["nombre"]] = limpiar(post.get(campo["nombre"]))
    for seccion in esquema["secciones"]:
        nombre = seccion["nombre"]
        if seccion["tipo"] != TABLA:
            datos[nombre] = limpiar(post.get(nombre))
            # Un gráfico solo se escribe si el envío lo trae. Una página que se
            # quedó abierta de antes de tener estos campos no manda la clave, y eso
            # no puede interpretarse como «borró el dibujo»; borrarlo manda la
            # clave vacía. Lo que falta se conserva en ``conservar_campos_retirados``.
            if seccion["tipo"] == CROQUIS and clave_dibujo(nombre) in post:
                datos[clave_dibujo(nombre)] = limpiar_croquis(post.get(clave_dibujo(nombre)))
            elif seccion["tipo"] == ORGANIGRAMA and clave_grafico(nombre) in post:
                datos[clave_grafico(nombre)] = limpiar_organigrama(post.get(clave_grafico(nombre)))
            continue
        filas = []
        indices = indices_enviados(post, nombre, seccion)
        for indice in indices:
            fila = {columna["nombre"]: limpiar(post.get(f"{nombre}-{indice}-{columna['nombre']}"))
                    for columna in seccion["columnas"]}
            if any(fila.values()):
                filas.append(fila)
        datos[nombre] = filas
        if seccion.get("firma"):
            datos[f"{nombre}__firma"] = limpiar(post.get(f"{nombre}__firma"))
    return datos

def indices_enviados(post, nombre, seccion):
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

def evaluacion_heredada(datos):
    """El texto del punto 4 escrito cuando era una sola casilla, si sigue vigente.

    Solo se devuelve mientras los cuatro campos nuevos estén vacíos: en cuanto
    alguien empieza a repartirlo, lo antiguo deja de mostrarse (se conserva en
    los datos, no en pantalla) para no enseñar la misma información dos veces.
    """
    datos = datos or {}
    if any(str(datos.get(nombre) or "").strip() for nombre, _ in EVALUACION_INICIAL):
        return ""
    return str(datos.get(EVALUACION_INICIAL_HEREDADA) or "").strip()

def evaluacion_en_partes(datos):
    """El punto 4 como pares (etiqueta, texto), solo con los que tienen contenido."""
    datos = datos or {}
    return [
        (etiqueta, str(datos.get(nombre)).strip())
        for nombre, etiqueta in EVALUACION_INICIAL
        if str(datos.get(nombre) or "").strip()
    ]

# Clave reservada del JSON de un formulario. La migración 0021 unificó los
# formularios que existían en varios periodos y dejó lo de los periodos anteriores
# dentro del registro vigente, bajo esta clave. Ningún campo del esquema empieza
# por guion bajo, de modo que el editor nunca la sobrescribe ni la muestra.
RESPALDO_DE_PERIODOS = "_periodos_anteriores"


def conservar_campos_retirados(codigo, anteriores, nuevos):
    """Devuelve ``nuevos`` con los campos retirados y el respaldo, tal como estaban."""
    if RESPALDO_DE_PERIODOS in (anteriores or {}) and RESPALDO_DE_PERIODOS not in nuevos:
        nuevos[RESPALDO_DE_PERIODOS] = anteriores[RESPALDO_DE_PERIODOS]
    for nombre in CAMPOS_RETIRADOS.get(codigo, ()):
        if nombre in (anteriores or {}) and nombre not in nuevos:
            nuevos[nombre] = anteriores[nombre]
    # Los gráficos que el envío no mencionó tampoco se pierden (ver extraer_datos).
    for nombre in anteriores or {}:
        if nombre.endswith(SUFIJOS_GRAFICOS) and nombre not in nuevos:
            nuevos[nombre] = anteriores[nombre]
    return nuevos

def tiene_grafico(seccion, datos):
    """Si el campo gráfico trae algo dibujado, además de su nota de texto."""
    if seccion["tipo"] == CROQUIS:
        return bool(limpiar_croquis((datos or {}).get(clave_dibujo(seccion["nombre"]))))
    if seccion["tipo"] == ORGANIGRAMA:
        return bool(limpiar_organigrama((datos or {}).get(clave_grafico(seccion["nombre"]))))
    return False

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
            # Un croquis dibujado o un organigrama armado cuentan aunque no haya nota.
            llenas += bool(str(valor or "").strip()) or tiene_grafico(seccion, datos)
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
# Los anchos de las columnas con tamaño propio suman el 86 %: el 14 % restante es de
# «Observaciones». Con la suma en el 100 % esa columna se quedaba sin sitio y la tabla,
# que es de disposición fija, se salía de la hoja por la derecha.
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
         "columnas": [_columna("solicitado_por", "A. Solicitud — 1. Por quién", "9%"),
                      _columna("fecha_solicitud", "2. Fecha y hora", "8%", tipo=FECHA_HORA),
                      _columna("clase", "3. Clase", "7%"),
                      _columna("tipo", "4. Tipo", "7%"),
                      _columna("fecha_arribo", "B. Arribo real — 5. Fecha y hora", "8%", tipo=FECHA_HORA),
                      _columna("institucion", "C. Suministrado por — 6. Institución", "10%"),
                      _columna("matricula", "7. Matrícula", "7%"),
                      _columna("personas", "8. N.º de personas", "5%"),
                      _columna("estado", "D. Estado del recurso", "8%"),
                      _columna("desmovilizado_por", "E. Desmovilizado — 10. Por quién", "9%"),
                      _columna("fecha_desmovilizacion", "11. Fecha y hora", "8%", tipo=FECHA_HORA),
                      _columna("observaciones", "12. Observaciones")],
         "filas_impresion": 12},
    ],
}

def obtener_esquema_catalogo(codigo):
    """Como ``obtener_esquema`` pero incluye el SCI-211 para la vista de catálogo."""
    if codigo == "211":
        return ESQUEMA_CATALOGO_211
    return ESQUEMAS_SCI.get(codigo)
