"""Comando de management para completar todos los formularios SCI de una emergencia.

Uso:
    python manage.py completar_formularios_sci <pk_emergencia>
    python manage.py completar_formularios_sci --todos   # aplica a todas

Genera datos operativos realistas — los mismos que completaría el personal
de bomberos en una emergencia real en la provincia de Cotopaxi.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from emergencias.models import (
    Emergencia, FormularioSCI, FormularioSCI211, RegistroRecursoSCI211
)
from emergencias.esquemas_sci import ESQUEMAS_SCI, TABLA
from emergencias.services_sci import crear_sci211_desde_emergencia


# ---------------------------------------------------------------------------
# Generador de datos operativos realistas según la emergencia
# ---------------------------------------------------------------------------

def _periodo(emergencia):
    """Devuelve strings de inicio y fin del periodo operacional."""
    inicio = emergencia.fecha_reporte
    fin = inicio + timezone.timedelta(hours=4)
    fmt = "%Y-%m-%dT%H:%M"
    return inicio.strftime(fmt), fin.strftime(fmt)


def _hora(emergencia, delta_minutos=0):
    dt = emergencia.fecha_reporte + timezone.timedelta(minutes=delta_minutos)
    return dt.strftime("%H:%M")


def _fecha_hora(emergencia, delta_minutos=0):
    dt = emergencia.fecha_reporte + timezone.timedelta(minutes=delta_minutos)
    return dt.strftime("%Y-%m-%dT%H:%M")


def _tipo(emergencia):
    """Devuelve el tipo de emergencia normalizado."""
    return (emergencia.tipo_emergencia or "Incendio estructural").strip()


def _direccion(emergencia):
    return emergencia.direccion or "Latacunga, Cotopaxi"


def _institucion(emergencia):
    try:
        return emergencia.estacion_responsable.cuerpo_bomberos.nombre
    except Exception:
        return "Cuerpo de Bomberos de Latacunga"


def _estacion(emergencia):
    try:
        return emergencia.estacion_responsable.nombre
    except Exception:
        return "Estación Central"


# ---------------------------------------------------------------------------
# Textos por sección — valores realistas por nombre de campo
# ---------------------------------------------------------------------------

def _textos_por_tipo(emergencia):
    """Devuelve un diccionario de textos operativos adaptados al tipo de emergencia."""
    tipo = _tipo(emergencia).lower()
    dir_ = _direccion(emergencia)
    inst = _institucion(emergencia)
    est  = _estacion(emergencia)
    p_inicio, p_fin = _periodo(emergencia)

    # Determinar contexto según tipo de emergencia
    if "forestal" in tipo:
        eval_inicial   = (f"Incendio forestal activo en {dir_}. Frente de fuego aproximado de 2 ha. "
                          "Viento del NE empuja las llamas hacia área poblada. Sin víctimas reportadas. "
                          "Vegetación seca favorece la propagación rápida.")
        objetivo_ini   = ("Controlar el frente de fuego activo en un radio de 500 m. "
                          "Evitar que el incendio alcance viviendas en el sector norte.")
        estrategias    = ("Ataque indirecto con cortafuegos perimetral. "
                          "Líneas de agua en puntas de fuego. "
                          "Retardo químico en sector de mayor riesgo.")
        tacticas       = ("División A ataca la cabeza del fuego desde el flanco izquierdo. "
                          "División B establece cortafuego en la franja Este. "
                          "Unidad de rescate en espera para evacuación de zona residencial.")
        msg_seg        = ("EPP ignífugo obligatorio. Zona de seguridad: 300 m a sotavento. "
                          "Cambio de viento activará protocolo de retirada. "
                          "Comunicación cada 15 min con PC.")
        croquis        = (f"Incendio forestal en {dir_}. "
                          "PC establecido en vía principal de acceso. "
                          "Área de espera al sur en terreno despejado. "
                          "Frente activo marcado en color rojo. Cortafuego en azul.")
        organigrama_0  = ("CI: Mayor Luis Andrade\nOf. Seguridad: Cap. Rosa Cárdenas\n"
                          "Of. Información: Sgt. Jorge Mena\nJSO: Cap. Pablo Ríos\n"
                          "JSL: Lt. Carmen Suárez")
    elif "rescate" in tipo or "vehicular" in tipo or "accidente" in tipo:
        eval_inicial   = (f"Accidente de tránsito en {dir_}. Colisión frontal entre dos vehículos. "
                          "Dos personas atrapadas en el habitáculo. Una persona con traumatismo leve "
                          "evacuada por sus propios medios. Riesgo de derrame de combustible.")
        objetivo_ini   = ("Excarcelar a las personas atrapadas sin agravar sus lesiones. "
                          "Controlar el derrame de combustible y prevenir incendio secundario.")
        estrategias    = ("Estabilización de vehículos. Excarcelación con herramienta hidráulica. "
                          "Cobertura con espuma química.")
        tacticas       = ("Equipo de excarcelación en vehículo 1. "
                          "Paramédico en zona caliente con apoyo de estabilización. "
                          "Línea de agua en standby con espuma.")
        msg_seg        = ("Uso de EPP de rescate técnico. Zona de trabajo delimitada 50 m. "
                          "Corte de batería de vehículos antes de excarcelación. "
                          "No fumar en perímetro de 100 m.")
        croquis        = (f"Colisión en {dir_}. Dos vehículos: V1 al norte, V2 al sur. "
                          "PC en cuneta Este. ACV a 80 m al sur.")
        organigrama_0  = ("CI: Cap. Hernán Villacís\nOf. Seguridad: Sgt. Ana Molina\n"
                          "JSO: Lt. Marco Espín\nJSL: Sgt. Patricia Lema")
    elif "médic" in tipo or "medic" in tipo:
        eval_inicial   = (f"Emergencia médica en {dir_}. Paciente masculino 58 años con "
                          "dolor precordial irradiado al brazo izquierdo. Diaforesis y disnea. "
                          "Familiar refiere antecedente de hipertensión arterial.")
        objetivo_ini   = ("Estabilizar al paciente y transportarlo al centro hospitalario más cercano "
                          "en el menor tiempo posible.")
        estrategias    = ("Evaluación primaria y secundaria in situ. "
                          "Oxigenoterapia y monitoreo de signos vitales. "
                          "Coordinación con hospital para recepción del paciente.")
        tacticas       = ("Paramédico: evaluación y manejo. "
                          "Conductor: ruta de evacuación Hospital General Latacunga.")
        msg_seg        = ("BSI obligatorio. Precauciones universales de bioseguridad. "
                          "Escena segura antes de ingreso del personal.")
        croquis        = f"Emergencia médica en {dir_}. PC en vía de acceso. ACV junto a la escena."
        organigrama_0  = ("CI: Lt. Verónica Pazmiño\nOf. Seguridad: Sgt. Roberto Alba\nJSO: Cap. Diego Toro")
    elif "inundación" in tipo or "inundacion" in tipo:
        eval_inicial   = (f"Inundación en {dir_} por desbordamiento del cause principal. "
                          "Nivel del agua: 0,80 m en calzada. Tres familias aisladas en planta alta. "
                          "Sin víctimas en el agua. Lluvia intensa continúa.")
        objetivo_ini   = ("Evacuar a las tres familias aisladas y prevenir pérdidas humanas. "
                          "Establecer perímetro de seguridad en zona de riesgo.")
        estrategias    = ("Rescate con bote de goma. Evacuación a punto seguro.")
        tacticas       = ("Equipo acuático con bote inflable. "
                          "Personal en orilla con cuerdas de seguridad.")
        msg_seg        = ("Traje de agua y chaleco salvavidas obligatorios. "
                          "No ingresar a zonas con corriente superior a 1 m/s.")
        croquis        = f"Inundación en {dir_}. Bote de rescate ingresa por calle principal."
        organigrama_0  = ("CI: Mayor Carlos Gutiérrez\nJSO: Cap. Norma Vásquez\nJSL: Lt. Esteban Cruz")
    else:
        # Incendio estructural (caso por defecto)
        eval_inicial   = (f"Incendio estructural en {dir_}. Involucra planta baja y parte del entrepiso. "
                          "Humo denso y negro visible a 500 m. Cuatro personas evacuadas por sus propios medios. "
                          "Sin víctimas atrapadas confirmadas. Riesgo de colapso en sector de cubierta.")
        objetivo_ini   = ("Extinguir el incendio en el menor tiempo posible y evitar su propagación "
                          "a las edificaciones adyacentes.")
        estrategias    = ("Ataque directo con dos líneas de manguera de 38 mm. "
                          "Ventilación positiva para desalojo de humo. "
                          "Perímetro de seguridad de 50 m.")
        tacticas       = ("División A: ataque interior planta baja por acceso principal. "
                          "División B: protección exposición norte con línea exterior. "
                          "Unidad de rescate: verificación de habitaciones superiores.")
        msg_seg        = ("EPP estructural nivel 3 obligatorio. Equipos de respiración autónoma en uso. "
                          "No ingresar al segundo piso sin autorización del CI. "
                          "Comunicación radial cada 10 minutos.")
        croquis        = (f"Edificación en {dir_}. Acceso principal al este. "
                          "PC frente al inmueble en acera norte. "
                          "Área de espera a 100 m al sur en parque. "
                          "Hidrante H1 a 80 m al este.")
        organigrama_0  = ("CI: Mayor Luis Andrade\nOf. Seguridad: Cap. Rosa Cárdenas\n"
                          "Of. Información: Sgt. Jorge Mena\nJSO: Cap. Pablo Ríos\nJSL: Lt. Carmen Suárez")

    return {
        # SCI-201
        "evaluacion_inicial":   eval_inicial,
        "objetivos_iniciales":  objetivo_ini,
        "estrategias":          estrategias,
        "tacticas":             tacticas,
        "ubicacion_pc":         f"Frente a {dir_}, acera norte",
        "ubicacion_e":          f"100 m al sur del PC, zona despejada",
        "ruta_ingreso":         "Avenida principal desde el norte, señalizada por personal de control de tráfico.",
        "ruta_egreso":          "Vía lateral sur hacia el hospital / zona de reagrupamiento.",
        "mensaje_seguridad":    msg_seg,
        "croquis":              croquis,
        "organigrama":          organigrama_0,
        # SCI-202
        "objetivos":            objetivo_ini,
        "plan":                 estrategias + " " + tacticas,
        "pronostico_tiempo":    "Parcialmente nublado. Temperatura: 17 °C. Humedad relativa: 72 %. Viento: 12 km/h del NE.",
        # SCI-204
        "posicion_operaciones": "Supervisor de División A",
        "nombre_especifico":    "División A — Sector de ataque principal",
        "instrucciones":        tacticas,
        "comunicaciones":       f"Canal 3 simplex. Repetidora CB-{est[:4].upper()}. Frecuencia de emergencia: 162.300 MHz.",
        # SCI-207
        "lugar_registro":       "Área de Concentración de Víctimas (ACV)",
        "responsable_posicion": "Sgt. María Torres — Líder Unidad Médica",
        # SCI-221
        "tiempo_conclusion":    p_fin,
        # SCI-222
        "identificacion_comando": f"Comando Unificado — {inst}",
        "total_requeridos":     "5",
        "total_existentes":     "4",
        "total_faltantes":      "1",
        # Periodos operacionales
        "periodo_numero":       "1",
        "periodo_inicio":       p_inicio,
        "periodo_fin":          p_fin,
    }


# ---------------------------------------------------------------------------
# Generador de filas de tabla realistas
# ---------------------------------------------------------------------------

PERSONAL_BOMBEROS = [
    ("Mayor Luis Andrade",      "Comandante de Incidente"),
    ("Cap. Pablo Ríos",         "Jefe Sección Operaciones"),
    ("Cap. Rosa Cárdenas",      "Oficial de Seguridad"),
    ("Lt. Carmen Suárez",       "Jefe Sección Logística"),
    ("Lt. Marco Espín",         "Supervisor División A"),
    ("Sgt. Jorge Mena",         "Oficial de Información Pública"),
    ("Sgt. Patricia Lema",      "Unidad de Recursos"),
    ("Sgt. Roberto Alba",       "Unidad de Situación"),
    ("Cbte. Fernanda Quispe",   "Paramédico"),
    ("Cbte. Andrés Moreno",     "Conductor Autobomba AB-01"),
    ("Cbte. Silvia Naranjo",    "Conductor Autobomba AB-02"),
    ("Cbte. Iván Cando",        "Integrante División A"),
]

INSTITUCIONES = [
    "Cuerpo de Bomberos de Latacunga",
    "Cuerpo de Bomberos de Salcedo",
    "Cuerpo de Bomberos de Pujilí",
    "Cruz Roja Ecuatoriana — Filial Cotopaxi",
    "SNGRE — Gestión de Riesgos Cotopaxi",
]

UNIDADES = [
    ("Autobomba", "AB-01-CBL", "Disponible"),
    ("Autobomba", "AB-02-CBL", "Disponible"),
    ("Tanquero",  "TQ-01-CBL", "Disponible"),
    ("Escalera",  "ES-01-CBL", "No disponible"),
    ("Ambulancia","AM-01-CRE", "Disponible"),
]


def _filas_tabla(seccion, emergencia, textos):
    """Genera filas realistas para cada tabla según nombre de la sección."""
    nombre = seccion["nombre"]
    columnas = seccion["columnas"]
    col_names = [c["nombre"] for c in columnas]

    # -----------------------------------------------------------------------
    # Tablas conocidas con datos específicos
    # -----------------------------------------------------------------------
    if nombre == "acciones":
        # SCI-201: resumen de acciones cronológico
        pasos = [
            (_fecha_hora(emergencia, 0),   "Recepción del despacho. CI Mayor Andrade asume el mando."),
            (_fecha_hora(emergencia, 5),   "Llegada de AB-01 y AB-02 a la escena. Evaluación inicial completada."),
            (_fecha_hora(emergencia, 12),  "Establecimiento del PC y área de espera. Perímetro delimitado."),
            (_fecha_hora(emergencia, 18),  "Primera línea de ataque operativa. Inicio del combate activo."),
            (_fecha_hora(emergencia, 35),  "Incendio bajo control en sector norte. División B refuerza flanco este."),
            (_fecha_hora(emergencia, 60),  "Incendio controlado al 80 %. Operaciones de enfriamiento iniciadas."),
            (_fecha_hora(emergencia, 90),  "Incendio extinguido. Reconocimiento de daños estructurales."),
            (_fecha_hora(emergencia, 110), "Desmovilizan AB-02 y TQ-01. AB-01 permanece en guardia fría."),
        ]
        filas = []
        for fh, accion in pasos:
            fila = {}
            for c in columnas:
                if c["nombre"] == "fecha_hora":
                    fila[c["nombre"]] = fh
                else:
                    fila[c["nombre"]] = accion
            filas.append(fila)
        return filas

    if nombre == "pacientes":
        # SCI-207: registro de pacientes
        return [
            {
                "nombre": "Jorge Alberto Molina Vera", "sexo": "M", "edad": "42",
                "clasificacion": "Verde", "lugar_traslado": "Hospital General Latacunga",
                "trasladado_por": "Cbte. Fernanda Quispe — AM-01",
                "fecha_hora": _fecha_hora(emergencia, 22),
            },
            {
                "nombre": "María Dolores Tipán Cruz", "sexo": "F", "edad": "67",
                "clasificacion": "Amarillo", "lugar_traslado": "Hospital IESS Latacunga",
                "trasladado_por": "Cbte. Andrés Moreno — AM-01",
                "fecha_hora": _fecha_hora(emergencia, 35),
            },
        ]

    if nombre == "canales":
        # SCI-205: plan de comunicaciones
        canales = [
            ("Radio portátil Kenwood TK-3402", "3", "Comando de Incidente",       "Puesto de Comando",   "Canal principal de mando"),
            ("Radio portátil Kenwood TK-3402", "4", "División A",                  "Sector de ataque",    "Canal táctico División A"),
            ("Radio portátil Kenwood TK-3402", "5", "División B",                  "Flanco este",         "Canal táctico División B"),
            ("Radio móvil Motorola CM300",     "1", "Centro de Comunicaciones",    "Estación Central",    "Frecuencia de despacho"),
            ("Celular",                         "—", "Oficial de Enlace",           "PC",                  "Contacto interinstitucional"),
        ]
        filas = []
        for sistema, canal, asignado, ubicacion, obs in canales:
            fila = {}
            for c in columnas:
                vals = {"sistema": sistema, "canal": canal, "asignado": asignado,
                        "ubicacion": ubicacion, "observaciones": obs}
                fila[c["nombre"]] = vals.get(c["nombre"], "—")
            filas.append(fila)
        return filas

    if nombre == "asistencia":
        # SCI-206: plan médico
        return [
            {"instalacion": "Puesto Médico Avanzado (PMA)", "institucion": "Cruz Roja — Cotopaxi",
             "ubicacion": "A 60 m del PC", "contacto": "Radio canal 3 / Tel. 0987654321"},
            {"instalacion": "Hospital General Latacunga",   "institucion": "Ministerio de Salud Pública",
             "ubicacion": "Av. Unidad Nacional y Félix Valencia", "contacto": "Tel. (03) 2812-323"},
            {"instalacion": "Hospital IESS Latacunga",      "institucion": "IESS",
             "ubicacion": "Av. Marco Aurelio Subía y Belisario Quevedo", "contacto": "Tel. (03) 2813-200"},
        ]

    if nombre == "ambulancias":
        return [
            {"clase_tipo": "Ambulancia tipo II", "institucion": "Cruz Roja Ecuatoriana — Cotopaxi",
             "observaciones": "AM-01. Disponible en el ACV."},
            {"clase_tipo": "Ambulancia tipo I",  "institucion": "Cuerpo de Bomberos de Latacunga",
             "observaciones": "AM-02. En standby a 500 m."},
        ]

    if nombre == "derivacion":
        return [
            {"clasificacion": "Rojo (crítico)",   "instalacion": "Hospital General Latacunga",
             "transporte": "Ambulancia AM-01 (avanzada)", "observaciones": "Prioridad máxima. Aviso previo al hospital."},
            {"clasificacion": "Amarillo (urgente)","instalacion": "Hospital IESS Latacunga",
             "transporte": "Ambulancia AM-02",            "observaciones": "Coordinar con médico de guardia."},
            {"clasificacion": "Verde (leve)",      "instalacion": "Centro de Salud N.º 1 Latacunga",
             "transporte": "Transporte propio o particular","observaciones": "Evaluación y alta en sitio si es posible."},
        ]

    if nombre == "recursos":
        # SCI-204: recursos asignados a División A
        return [
            {"recurso": "Autobomba AB-01", "responsable": "Cbte. Andrés Moreno",
             "funcion": "Abastecimiento de agua y línea de ataque principal", "observaciones": "Tanque lleno al inicio"},
            {"recurso": "Autobomba AB-02", "responsable": "Cbte. Silvia Naranjo",
             "funcion": "Línea de backup y protección de exposición norte",   "observaciones": "Relevará a AB-01 en h=2"},
            {"recurso": "ERA x4",          "responsable": "Cbte. Iván Cando",
             "funcion": "Entrada en zona con humo para verificación interior", "observaciones": "Cilindros al 100 %"},
        ]

    if nombre == "analisis":
        # SCI-215: análisis de seguridad
        return [
            {"area": "Interior de la edificación", "riesgo": "Colapso estructural por debilitamiento del entrepiso",
             "accion": "Prohibir acceso al segundo piso. Supervisor de seguridad en acceso."},
            {"area": "Zona de ataque",             "riesgo": "Retroceso de llama y explosión de gases calientes (backdraft)",
             "accion": "Ventilación positiva antes del ingreso. ERA obligatorio."},
            {"area": "Perímetro exterior",         "riesgo": "Atropellamiento por vehículos de emergencia",
             "accion": "Control de tráfico con conos y cinta. Personal asignado."},
            {"area": "Abastecimiento de agua",     "riesgo": "Corte de suministro por daño en red hidráulica",
             "accion": "Tanquero TQ-01 como reserva. Hidrante H2 como alternativa."},
            {"area": "Personal en escena",         "riesgo": "Golpe de calor y deshidratación",
             "accion": "Rotación de equipos cada 20 min. Hidratación en área de espera."},
        ]

    if nombre == "actividades":
        # SCI-214: bitácora
        entries = [
            (_hora(emergencia, 0),   "Despacho recibido. CI asume el mando."),
            (_hora(emergencia, 5),   "Llegada a la escena. Evaluación inicial."),
            (_hora(emergencia, 12),  "PC y perímetro establecidos."),
            (_hora(emergencia, 18),  "Inicio del ataque activo con dos líneas."),
            (_hora(emergencia, 35),  "Incendio bajo control. Sector norte estabilizado."),
            (_hora(emergencia, 60),  "Incendio extinguido. Operaciones de enfriamiento."),
            (_hora(emergencia, 90),  "Reconocimiento estructural. Sin víctimas en el interior."),
            (_hora(emergencia, 110), "Inicio de desmovilización de recursos secundarios."),
            (_hora(emergencia, 130), "Transferencia de la escena a Policía Nacional."),
            (_hora(emergencia, 135), "Retorno a base de AB-01. Cierre del incidente."),
        ]
        return [{"hora": h, "evento": ev} for h, ev in entries]

    if nombre == "personal":
        # SCI-214: lista de personal
        return [
            {"nombre": p[0], "posicion": p[1], "institucion": INSTITUCIONES[0]}
            for p in PERSONAL_BOMBEROS[:6]
        ]

    # SCI-203 tablas de organización
    if nombre in ("comando", "planificacion", "logistica", "operaciones", "finanzas"):
        asignaciones = {
            "comando": [
                ("Comandante de Incidente (Principal)",   "Mayor Luis Andrade"),
                ("Comandante de Incidente (Adjunto)",     "Cap. Pablo Ríos"),
                ("Oficial de Seguridad",                  "Cap. Rosa Cárdenas"),
                ("Oficial de Información Pública",        "Sgt. Jorge Mena"),
                ("Oficial de Enlace",                     "Lt. Marco Espín"),
            ],
            "representantes": [
                ("Cruz Roja Ecuatoriana — Cotopaxi",      "Dr. Eduardo Salinas"),
                ("SNGRE Cotopaxi",                        "Ing. Patricia Vega"),
            ],
            "planificacion": [
                ("Jefe de Sección",                       "Sgt. Patricia Lema"),
                ("Unidad de Recursos",                    "Cbte. Ana Chiriboga"),
                ("Unidad de Situación",                   "Sgt. Roberto Alba"),
                ("Unidad de Documentación",               "Cbte. Verónica Moreta"),
                ("Unidad de Desmovilización",             "Lt. Ramiro Tovar"),
                ("Técnicos especialistas",                "Ing. Carlos Salazar — Riesgos"),
            ],
            "logistica": [
                ("Jefe de Sección",                       "Lt. Carmen Suárez"),
                ("A. Rama de Soporte — Coordinador",      "Sgt. Nelson Espín"),
                ("A. Rama de Soporte — Unidad de Suministros",    "Cbte. Diana Cayo"),
                ("A. Rama de Soporte — Unidad de Instalaciones",  "Cbte. Freddy Taipe"),
                ("A. Rama de Soporte — Unidad de Transporte",     "Cbte. Andrés Moreno"),
                ("B. Rama de Servicios — Unidad de Comunicaciones","Sgt. Luis Enríquez"),
                ("B. Rama de Servicios — Unidad Médica",          "Cbte. Fernanda Quispe"),
                ("B. Rama de Servicios — Unidad de Alimentación", "Cbte. Miriam Oña"),
            ],
            "operaciones": [
                ("Jefe de Sección",             "Cap. Pablo Ríos"),
                ("A. Rama I",                   "Lt. Marco Espín"),
                ("B. Rama II",                  "Sgt. Henry Guamán"),
                ("C. Rama III",                 ""),
                ("D. Rama Operaciones Aéreas — Supervisor táctico",    ""),
                ("D. Rama Operaciones Aéreas — Supervisor de soporte",  ""),
                ("D. Rama Operaciones Aéreas — Supervisor de helicópteros", ""),
                ("D. Rama Operaciones Aéreas — Supervisor de ala fija",  ""),
            ],
            "finanzas": [
                ("Jefe de Sección",    "Cap. Daniel Flores"),
                ("Unidad de Tiempos",  "Cbte. Susana Tigse"),
                ("Unidad de Proveeduría", "Cbte. Xavier Pilco"),
                ("Unidad de Costos",   "Cbte. Blanca Ayme"),
                ("Unidad de Pagos",    ""),
            ],
        }
        filas_fijas = seccion.get("filas_fijas") or [r[0] for r in asignaciones.get(nombre, [])]
        datos_asignados = {etiqueta: nombre_p for etiqueta, nombre_p in asignaciones.get(nombre, [])}
        filas = []
        for etiqueta in filas_fijas:
            fila = {}
            for c in columnas:
                if c["nombre"] in ("posicion", "institucion"):
                    fila[c["nombre"]] = etiqueta
                elif c["nombre"] == "nombre":
                    fila[c["nombre"]] = datos_asignados.get(etiqueta, "")
                elif c["nombre"] == "division":
                    fila[c["nombre"]] = ""
                else:
                    fila[c["nombre"]] = datos_asignados.get(etiqueta, "")
            filas.append(fila)
        return filas

    if nombre == "representantes":
        return [
            {"institucion": "Cruz Roja Ecuatoriana — Cotopaxi", "nombre": "Dr. Eduardo Salinas"},
            {"institucion": "SNGRE Cotopaxi",                    "nombre": "Ing. Patricia Vega"},
            {"institucion": "Policía Nacional — Cotopaxi",       "nombre": "Tnte. Mauricio Acosta"},
        ]

    # Listas de verificación (SCI-221)
    if nombre in ("verif_planificacion", "verif_operaciones", "verif_logistica", "verif_finanzas"):
        secciones_verif = {
            "verif_planificacion": [
                "Documentación del incidente entregada a la Unidad de Documentación",
                "Informe de situación final elaborado",
                "Inventario de recursos devueltos actualizado",
                "Lecciones aprendidas registradas",
                "Plan de desmovilización comunicado a todas las secciones",
            ],
            "verif_operaciones": [
                "Personal desmovilizado notificado y en viaje de retorno",
                "Equipo revisado y reportado a Logística",
                "Herramientas e implementos contabilizados",
                "Escena transferida a autoridad competente",
                "Informe de operaciones firmado",
            ],
            "verif_logistica": [
                "Combustible y suministros devueltos o contabilizados",
                "Instalaciones y equipos de comunicación recuperados",
                "Unidades de transporte liberadas",
                "Alimentos y agua consumidos registrados",
                "Inventario de EPP devuelto",
            ],
            "verif_finanzas": [
                "Hojas de tiempo del personal completadas",
                "Facturas y recibos de compra recopilados",
                "Costos del incidente estimados",
                "Contratos y acuerdos documentados",
                "Informe financiero inicial preparado",
            ],
        }
        acciones = secciones_verif.get(nombre, [])
        return [{"accion": a, "cumplido": "Sí", "observaciones": ""} for a in acciones]

    if nombre == "matriz":
        # SCI-222
        tipo_em = _tipo(emergencia)
        return [
            {"prioridad": "1", "incidente": tipo_em, "recurso": "Autobomba",
             "tiene": "2", "falta": "1", "requiere": "3", "observaciones": "Solicitar apoyo mutual Salcedo"},
            {"prioridad": "2", "incidente": tipo_em, "recurso": "Tanquero",
             "tiene": "1", "falta": "0", "requiere": "1", "observaciones": ""},
            {"prioridad": "3", "incidente": tipo_em, "recurso": "Ambulancia",
             "tiene": "1", "falta": "1", "requiere": "2", "observaciones": "Cruz Roja en camino"},
        ]

    # -----------------------------------------------------------------------
    # Tabla genérica: genera filas con datos coherentes
    # -----------------------------------------------------------------------
    minimas = max(seccion.get("filas_minimas", 3), 3)
    filas = []
    for idx in range(min(minimas, 4)):
        fila = {}
        for c in columnas:
            cn = c["nombre"]
            tipo_c = c.get("tipo", "texto")
            if tipo_c == "fecha_hora":
                fila[cn] = _fecha_hora(emergencia, idx * 20)
            elif tipo_c == "hora":
                fila[cn] = _hora(emergencia, idx * 20)
            elif cn in ("nombre", "nombres"):
                fila[cn] = PERSONAL_BOMBEROS[idx % len(PERSONAL_BOMBEROS)][0]
            elif cn == "posicion":
                fila[cn] = PERSONAL_BOMBEROS[idx % len(PERSONAL_BOMBEROS)][1]
            elif cn in ("institucion", "instituciones"):
                fila[cn] = INSTITUCIONES[idx % len(INSTITUCIONES)]
            else:
                fila[cn] = ""
        filas.append(fila)
    return filas


# ---------------------------------------------------------------------------
# Función principal: genera el dict `datos` para cualquier esquema SCI
# ---------------------------------------------------------------------------

def generar_datos_reales(esquema, emergencia):
    """Genera datos operativos realistas para un formulario SCI."""
    from emergencias.esquemas_sci import campos_periodo, FECHA_HORA, HORA
    textos = _textos_por_tipo(emergencia)
    p_inicio, p_fin = _periodo(emergencia)
    datos = {}

    # Campos de periodo operacional
    for campo in campos_periodo(esquema):
        cn = campo["nombre"]
        datos[cn] = textos.get(cn, "")

    # Secciones
    for seccion in esquema["secciones"]:
        nombre = seccion["nombre"]
        tipo = seccion["tipo"]
        if tipo == TABLA:
            datos[nombre] = _filas_tabla(seccion, emergencia, textos)
            if seccion.get("firma"):
                datos[f"{nombre}__firma"] = "Mayor Luis Andrade"
        elif tipo in (FECHA_HORA, "fecha_hora"):
            datos[nombre] = textos.get(nombre, _fecha_hora(emergencia))
        elif tipo == "hora":
            datos[nombre] = textos.get(nombre, _hora(emergencia))
        else:
            datos[nombre] = textos.get(nombre, "")

    return datos


# ---------------------------------------------------------------------------
# Lógica de finalización
# ---------------------------------------------------------------------------

@transaction.atomic
def completar_sci_para_emergencia(emergencia, usuario, stdout=None):
    """Crea y finaliza todos los formularios SCI de la emergencia dada."""
    from emergencias.views import ORDEN_FORMULARIOS_SCI

    def log(msg):
        if stdout:
            stdout.write(msg)

    ahora = timezone.now()
    creados = 0
    ya_existian = 0

    for codigo in ORDEN_FORMULARIOS_SCI:
        if codigo == "211":
            sci211 = FormularioSCI211.objects.filter(emergencia=emergencia).first()
            if sci211 is None:
                sci211 = crear_sci211_desde_emergencia(emergencia, usuario)
                log(f"  ✓ SCI-211 creado")
                creados += 1
            else:
                log(f"  · SCI-211 ya existía ({sci211.get_estado_display()})")
                ya_existian += 1

            if sci211.estado != FormularioSCI211.Estado.FINALIZADO:
                if not sci211.registros.exists():
                    inst = _institucion(emergencia)
                    RegistroRecursoSCI211.objects.create(
                        formulario=sci211,
                        solicitado_por="Mayor Luis Andrade — Comandante de Incidente",
                        fecha_hora_solicitud=ahora,
                        clase_recurso="Vehículo contra incendios",
                        tipo_recurso="Autobomba",
                        institucion_procedencia=inst,
                        matricula_identificacion="AB-01-CBL",
                        numero_personas=3,
                        estado_recurso=RegistroRecursoSCI211.EstadoRecurso.DISPONIBLE,
                        asignado_a=emergencia.direccion or "Escena del incidente",
                        orden=1,
                    )
                sci211.emergencia_codigo_emitido = emergencia.codigo
                sci211.incidente_nombre_emitido = emergencia.tipo_emergencia
                sci211.incidente_fecha_emitida = emergencia.fecha_reporte
                sci211.incidente_direccion_emitida = emergencia.direccion
                sci211.institucion_emitida = _institucion(emergencia)
                sci211.estacion_emitida = _estacion(emergencia)
                if emergencia.latitud and emergencia.longitud:
                    sci211.coordenadas_emitidas = f"{emergencia.latitud}, {emergencia.longitud}"
                sci211.estado = FormularioSCI211.Estado.FINALIZADO
                sci211.finalizado_por = usuario
                sci211.modificado_por = usuario
                sci211.fecha_finalizacion = ahora
                sci211.save()
                log(f"    → SCI-211 finalizado")
            else:
                log(f"    · SCI-211 ya estaba finalizado")
            continue

        # Formularios SCI genéricos
        esquema = ESQUEMAS_SCI.get(codigo)
        if esquema is None:
            log(f"  ! SCI-{codigo}: esquema no encontrado, saltando")
            continue

        datos_reales = generar_datos_reales(esquema, emergencia)

        formulario, creado = FormularioSCI.objects.get_or_create(
            emergencia=emergencia,
            codigo_sci=codigo,
            defaults={
                "datos": datos_reales,
                "preparado_por": "Mayor Luis Andrade",
                "creado_por": usuario,
                "modificado_por": usuario,
            },
        )
        if creado:
            log(f"  ✓ SCI-{codigo} creado")
            creados += 1
        else:
            log(f"  · SCI-{codigo} ya existía ({formulario.get_estado_display()})")
            ya_existian += 1
            if not formulario.datos:
                formulario.datos = datos_reales
                formulario.modificado_por = usuario
                formulario.save(update_fields=["datos", "modificado_por"])

        if formulario.estado != FormularioSCI.Estado.FINALIZADO:
            formulario.datos = datos_reales
            formulario.estado = FormularioSCI.Estado.FINALIZADO
            formulario.finalizado_por = usuario
            formulario.modificado_por = usuario
            formulario.fecha_finalizacion = ahora
            formulario.save(update_fields=[
                "datos", "estado", "finalizado_por",
                "modificado_por", "fecha_finalizacion",
            ])
            log(f"    → SCI-{codigo} finalizado")
        else:
            log(f"    · SCI-{codigo} ya estaba finalizado")

    return creados, ya_existian


# ---------------------------------------------------------------------------
# Comando Django
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Rellena y finaliza todos los formularios SCI de una emergencia con datos "
        "operativos realistas (personal, unidades y protocolos reales de bomberos)."
    )

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("pk", nargs="?", type=int, help="PK de la emergencia")
        group.add_argument(
            "--todos", action="store_true",
            help="Aplica a todas las emergencias de la base de datos"
        )

    def handle(self, *args, **options):
        usuario = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
        if not usuario:
            raise CommandError("Debe existir un superusuario para ejecutar este comando.")

        if options["todos"]:
            emergencias = list(Emergencia.objects.select_related(
                "estacion_responsable__cuerpo_bomberos"
            ).all())
        else:
            pk = options["pk"]
            try:
                emergencias = [
                    Emergencia.objects.select_related(
                        "estacion_responsable__cuerpo_bomberos"
                    ).get(pk=pk)
                ]
            except Emergencia.DoesNotExist:
                raise CommandError(f"No existe ninguna emergencia con pk={pk}.")

        total_creados = 0
        total_existian = 0
        for emergencia in emergencias:
            self.stdout.write(
                self.style.HTTP_INFO(
                    f"\n→ {emergencia.codigo} — {emergencia.tipo_emergencia}"
                )
            )
            creados, existian = completar_sci_para_emergencia(
                emergencia, usuario, stdout=self.stdout
            )
            total_creados += creados
            total_existian += existian

        self.stdout.write(
            self.style.SUCCESS(
                f"\nListo. {total_creados} formulario(s) completados, "
                f"{total_existian} ya existían."
            )
        )
