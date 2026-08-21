from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from instituciones.models import Estacion
from inventario.models import Recurso

from emergencias.models import (
    DespliegueUnidad,
    Emergencia,
    FormularioSCI,
    FormularioSCI211,
    RegistroRecursoSCI211,
)
from emergencias.services_sci import finalizar_sci211


DATOS_COMPLETOS = {
    "201": {
        "evaluacion": "Incendio confinado en una bodega de dos plantas, con humo denso y exposición a locales colindantes.",
        "amenazas": "Propagación por cubierta, cilindros de GLP y afectación por humo. Sin víctimas reportadas.",
        "objetivos": "Proteger vidas, confinar el incendio, extinguir focos y verificar puntos calientes.",
        "organizacion": "Comando único; grupos de ataque, abastecimiento, búsqueda, seguridad y atención prehospitalaria.",
        "croquis": "Acceso principal por la calle Quito; puesto de comando al norte y zona segura en el parqueadero oriental.",
        "aprobacion": "Comandante del Incidente - Cuerpo de Bomberos de Latacunga",
    },
    "202": {
        "periodo": "20/08/2026 08:15 - 20/08/2026 12:00",
        "objetivos": "Confinar el fuego, evitar propagación, completar búsqueda primaria y proteger al personal.",
        "estrategias": "Ataque interior coordinado, ventilación controlada y abastecimiento continuo.",
        "tacticas": "Línea de 1,5 pulgadas por acceso principal; respaldo exterior y control de servicios básicos.",
        "recursos": "Autobomba AB-01, ambulancia AMB-01, dos binomios ERA y equipo de extricación en reserva.",
        "aprobado_por": "Comandante del Incidente",
    },
    "203": {
        "comandante": "Comandante institucional de Latacunga",
        "seguridad": "Oficial de Seguridad Operacional",
        "operaciones": "Jefe de Operaciones",
        "planificacion": "Responsable de Planificación",
        "logistica": "Responsable de Logística",
        "finanzas": "Responsable Administrativo",
        "organizacion": "Enlace con ECU 911 y Policía Nacional para seguridad perimetral.",
    },
    "204": {
        "rama": "Operaciones",
        "division_grupo": "Grupo de control de incendios",
        "supervisor": "Jefe de Operaciones",
        "recursos": "AB-01, dos equipos ERA, dos EPP estructurales y una cámara térmica.",
        "instrucciones": "Ataque ofensivo desde el acceso norte, búsqueda primaria y revisión térmica posterior.",
        "comunicaciones": "Canal operativo 1; reporte de condiciones cada diez minutos.",
    },
    "205": {
        "periodo": "20/08/2026 08:15 - 20/08/2026 12:00",
        "sistemas": "Red institucional VHF y telefonía móvil de respaldo.",
        "canales": "Comando: canal 1; Operaciones: canal 2; Logística: canal 3.",
        "indicativos": "Comando Latacunga, Ataque 1, Abastecimiento 1 y APH 1.",
        "asignaciones": "Canal 1 para mando; canal 2 para ingreso y búsqueda; canal 3 para soporte.",
        "observaciones": "Mantener mensajes breves y confirmar toda orden crítica.",
    },
    "206": {
        "responsable": "Coordinador de Atención Prehospitalaria",
        "instalaciones": "Área de concentración de víctimas en el parqueadero oriental.",
        "ambulancias": "AMB-01 del Cuerpo de Bomberos de Latacunga.",
        "hospitales": "Hospital General de Latacunga como establecimiento de referencia.",
        "procedimientos": "Evaluación primaria, estabilización, comunicación médica y traslado según prioridad.",
        "aprobado_por": "Comandante del Incidente",
    },
    "207": {
        "responsable": "Coordinador de Atención Prehospitalaria",
        "pacientes": "No se registraron pacientes ni víctimas durante la operación.",
        "clasificacion": "Sin clasificación de triaje requerida.",
        "atencion": "Evaluación preventiva al personal al finalizar la intervención.",
        "traslados": "No se efectuaron traslados.",
        "observaciones": "Operación concluida sin lesionados civiles ni operativos.",
    },
    "214": {
        "responsable": "Responsable de Planificación",
        "periodo": "20/08/2026 08:10 - 20/08/2026 11:45",
        "actividades": "08:10 alerta; 08:16 despacho; 08:28 arribo; 08:35 ataque; 09:20 incendio controlado; 11:10 liquidación; 11:45 cierre.",
        "decisiones": "Evacuación preventiva, corte eléctrico, ataque interior y ventilación posterior al control.",
        "observaciones": "Se realizó inspección térmica antes de entregar la edificación.",
        "firma": "Responsable de Planificación SCI",
    },
    "215": {
        "preparado_por": "Oficial de Seguridad Operacional",
        "areas": "Bodega, local colindante, cubierta y zona de abastecimiento.",
        "peligros": "Humo, calor, colapso parcial, superficies resbalosas y cilindros presurizados.",
        "riesgos": "Riesgo alto durante ataque inicial y moderado durante remoción de escombros.",
        "mitigacion": "Uso obligatorio de ERA y EPP, binomios, control de acceso, hidratación y monitoreo térmico.",
        "responsables": "Oficial de Seguridad y supervisores de cada grupo.",
    },
    "221": {
        "responsable": "Responsable de Desmovilización",
        "planificacion": "Objetivos cumplidos, documentación reunida y cierre autorizado.",
        "recursos": "AB-01 y AMB-01 liberadas, revisadas y retornadas a la Estación Central.",
        "logistica": "Equipos contabilizados; ERA enviados a recarga y mangueras dispuestas para limpieza.",
        "comunicaciones": "ECU 911 y unidades informadas del cierre de operaciones.",
        "observaciones": "Sin novedades pendientes. Firmas registradas por responsables de sección.",
    },
    "222": {
        "preparado_por": "Jefe de Operaciones",
        "prioridades": "1. Seguridad de personas; 2. Confinamiento; 3. Extinción; 4. Protección de bienes.",
        "requeridos": "Una autobomba, una ambulancia preventiva, cuatro bomberos estructurales y dos ERA.",
        "disponibles": "AB-01, AMB-01, ERA-01, ERA-02, EPP-E-01 y EPP-E-02.",
        "asignaciones": "Autobomba a ataque; ambulancia a APH; ERA y EPP al grupo de control.",
        "observaciones": "No fue necesario solicitar recursos interinstitucionales adicionales.",
    },
}

DATOS_PARCIALES = {
    "201": {
        "evaluacion": "Incendio de vegetación en ladera con viento variable. Evaluación todavía en desarrollo.",
        "amenazas": "Posible propagación hacia cultivos y una vivienda aislada.",
        "objetivos": "Detener el avance hacia la zona habitada.",
        "organizacion": "Comando y grupo de ataque inicial establecidos.",
        "croquis": "Pendiente de completar después del reconocimiento del flanco oriental.",
        "aprobacion": "",
    },
    "202": {
        "periodo": "Periodo operacional en curso",
        "objetivos": "Proteger viviendas y contener los flancos norte y oriental.",
        "estrategias": "Ataque directo donde las condiciones sean seguras.",
        "tacticas": "En evaluación según dirección del viento.",
        "recursos": "AB-01 y personal forestal; solicitud adicional pendiente.",
        "aprobado_por": "",
    },
    "205": {
        "periodo": "Periodo operacional en curso",
        "sistemas": "Radio VHF institucional.",
        "canales": "Canal operativo 1.",
        "indicativos": "Comando Latacunga y Forestal 1.",
        "asignaciones": "Pendiente de ampliar con el arribo de nuevas unidades.",
        "observaciones": "Documento provisional.",
    },
}


class Command(BaseCommand):
    help = "Crea un incidente SCI completo y otro en elaboración con información coherente."

    @transaction.atomic
    def handle(self, *args, **options):
        Usuario = get_user_model()
        usuario = Usuario.objects.filter(username="comandante.latacunga").first()
        if usuario is None:
            usuario = Usuario.objects.filter(is_superuser=True).first()
        if usuario is None:
            raise CommandError("No existe comandante.latacunga ni un superusuario para registrar los incidentes.")

        estacion = Estacion.objects.filter(
            cuerpo_bomberos__canton__nombre="Latacunga", activo=True
        ).select_related("cuerpo_bomberos").first()
        if estacion is None:
            raise CommandError("No existe una estación activa para Latacunga.")

        recursos = {
            recurso.codigo_interno: recurso
            for recurso in Recurso.objects.filter(
                estacion=estacion, codigo_interno__in=("AB-01", "AMB-01")
            ).select_related("tipo__categoria")
        }
        if set(recursos) != {"AB-01", "AMB-01"}:
            raise CommandError("Ejecute primero: python manage.py cargar_inventario_bomberil")

        ahora = timezone.now()
        reporte_completo = ahora - timedelta(days=1, hours=4)
        cierre_completo = reporte_completo + timedelta(hours=3, minutes=35)
        completa, _ = Emergencia.objects.update_or_create(
            codigo="INC-2026-001",
            defaults={
                "tipo_emergencia": "Incendio estructural",
                "descripcion": "Incendio estructural controlado en una bodega comercial; operación cerrada sin víctimas.",
                "prioridad": Emergencia.Prioridad.ALTA,
                "estado": Emergencia.Estado.CERRADA,
                "fecha_reporte": reporte_completo,
                "fecha_cierre": cierre_completo,
                "direccion": "Sector El Salto, zona urbana de Latacunga",
                "latitud": "-0.934850",
                "longitud": "-78.614780",
                "estacion_responsable": estacion,
                "registrado_por": usuario,
            },
        )
        despliegues_completos = []
        for indice, codigo in enumerate(("AB-01", "AMB-01"), start=1):
            despliegue, _ = DespliegueUnidad.objects.update_or_create(
                emergencia=completa,
                unidad=recursos[codigo],
                defaults={
                    "estacion_procedencia": estacion,
                    "despachado_por": usuario,
                    "estado": DespliegueUnidad.Estado.FINALIZADA,
                    "fecha_salida": reporte_completo + timedelta(minutes=5 + indice),
                    "fecha_llegada": reporte_completo + timedelta(minutes=16 + indice),
                    "fecha_retorno": cierre_completo - timedelta(minutes=10 - indice),
                    "observaciones": "Unidad desmovilizada sin novedades y retornada a estación.",
                },
            )
            DespliegueUnidad.objects.filter(pk=despliegue.pk).update(
                fecha_asignacion=reporte_completo + timedelta(minutes=indice)
            )
            despliegue.refresh_from_db()
            despliegues_completos.append(despliegue)

        for codigo, datos in DATOS_COMPLETOS.items():
            FormularioSCI.objects.update_or_create(
                emergencia=completa,
                codigo_sci=codigo,
                defaults={"datos": datos, "creado_por": usuario, "modificado_por": usuario},
            )
        FormularioSCI.objects.filter(emergencia=completa).exclude(
            codigo_sci__in=DATOS_COMPLETOS
        ).delete()
        sci_completo, _ = FormularioSCI211.objects.update_or_create(
            emergencia=completa,
            defaults={
                "codigo": "SCI-211-INC-2026-001",
                "estado": FormularioSCI211.Estado.BORRADOR,
                "punto_registro": "Puesto de Comando - El Salto",
                "registrador_1": "Responsable de Planificación",
                "registrador_2": "Jefe de Operaciones",
                "registrador_3": "Responsable de Logística",
                "creado_por": usuario,
                "modificado_por": usuario,
                "finalizado_por": None,
                "fecha_finalizacion": None,
            },
        )
        sci_completo.registros.all().delete()
        for orden, despliegue in enumerate(despliegues_completos, start=1):
            unidad = despliegue.unidad
            RegistroRecursoSCI211.objects.create(
                formulario=sci_completo,
                despliegue=despliegue,
                solicitado_por=usuario.get_full_name() or usuario.username,
                fecha_hora_solicitud=despliegue.fecha_asignacion,
                clase_recurso=unidad.tipo.categoria.nombre,
                tipo_recurso=unidad.tipo.nombre,
                fecha_hora_arribo=despliegue.fecha_llegada,
                institucion_procedencia=estacion.cuerpo_bomberos.nombre,
                matricula_identificacion=unidad.codigo_interno,
                numero_personas=4 if unidad.codigo_interno == "AB-01" else 2,
                estado_recurso=RegistroRecursoSCI211.EstadoRecurso.DISPONIBLE,
                asignado_a="Sector El Salto - zona de operaciones",
                desmovilizado_por="Comandante del Incidente",
                fecha_hora_desmovilizacion=despliegue.fecha_retorno,
                observaciones="Recurso liberado y retornado a la Estación Central.",
                orden=orden,
            )
        sci_completo = finalizar_sci211(sci_completo, usuario)
        FormularioSCI211.objects.filter(pk=sci_completo.pk).update(fecha_finalizacion=cierre_completo)

        reporte_incompleto = ahora - timedelta(hours=1, minutes=20)
        incompleta, _ = Emergencia.objects.update_or_create(
            codigo="INC-2026-002",
            defaults={
                "tipo_emergencia": "Incendio forestal",
                "descripcion": "Incendio de vegetación en ladera; reconocimiento y control de flancos en curso.",
                "prioridad": Emergencia.Prioridad.CRITICA,
                "estado": Emergencia.Estado.EN_ATENCION,
                "fecha_reporte": reporte_incompleto,
                "fecha_cierre": None,
                "direccion": "Sector Loma Grande, parroquia Aláquez, Latacunga",
                "latitud": "-0.879420",
                "longitud": "-78.572630",
                "estacion_responsable": estacion,
                "registrado_por": usuario,
            },
        )
        despliegue_activo, _ = DespliegueUnidad.objects.update_or_create(
            emergencia=incompleta,
            unidad=recursos["AB-01"],
            defaults={
                "estacion_procedencia": estacion,
                "despachado_por": usuario,
                "estado": DespliegueUnidad.Estado.EN_SITIO,
                "fecha_salida": reporte_incompleto + timedelta(minutes=5),
                "fecha_llegada": reporte_incompleto + timedelta(minutes=24),
                "fecha_retorno": None,
                "observaciones": "Unidad en ataque inicial; solicitud de apoyo en evaluación.",
            },
        )
        DespliegueUnidad.objects.filter(pk=despliegue_activo.pk).update(
            fecha_asignacion=reporte_incompleto + timedelta(minutes=2)
        )
        despliegue_activo.refresh_from_db()
        DespliegueUnidad.objects.filter(emergencia=incompleta).exclude(pk=despliegue_activo.pk).delete()

        for codigo, datos in DATOS_PARCIALES.items():
            FormularioSCI.objects.update_or_create(
                emergencia=incompleta,
                codigo_sci=codigo,
                defaults={"datos": datos, "creado_por": usuario, "modificado_por": usuario},
            )
        FormularioSCI.objects.filter(emergencia=incompleta).exclude(
            codigo_sci__in=DATOS_PARCIALES
        ).delete()
        sci_incompleto, _ = FormularioSCI211.objects.update_or_create(
            emergencia=incompleta,
            defaults={
                "codigo": "SCI-211-INC-2026-002",
                "estado": FormularioSCI211.Estado.BORRADOR,
                "punto_registro": "Puesto de Comando - Loma Grande",
                "registrador_1": "Responsable de Planificación",
                "registrador_2": "",
                "registrador_3": "",
                "creado_por": usuario,
                "modificado_por": usuario,
                "finalizado_por": None,
                "fecha_finalizacion": None,
                "emergencia_codigo_emitido": "",
                "incidente_nombre_emitido": "",
                "incidente_fecha_emitida": None,
                "incidente_direccion_emitida": "",
                "institucion_emitida": "",
                "estacion_emitida": "",
                "coordenadas_emitidas": "",
            },
        )
        sci_incompleto.registros.all().delete()
        RegistroRecursoSCI211.objects.create(
            formulario=sci_incompleto,
            despliegue=despliegue_activo,
            solicitado_por=usuario.get_full_name() or usuario.username,
            fecha_hora_solicitud=despliegue_activo.fecha_asignacion,
            clase_recurso=recursos["AB-01"].tipo.categoria.nombre,
            tipo_recurso=recursos["AB-01"].tipo.nombre,
            fecha_hora_arribo=despliegue_activo.fecha_llegada,
            institucion_procedencia=estacion.cuerpo_bomberos.nombre,
            matricula_identificacion="AB-01",
            numero_personas=4,
            estado_recurso=RegistroRecursoSCI211.EstadoRecurso.DISPONIBLE,
            asignado_a="Flanco norte - Loma Grande",
            observaciones="Recurso activo; desmovilización pendiente.",
            orden=1,
        )

        Recurso.objects.filter(pk=recursos["AB-01"].pk).update(
            estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
            disponibilidad=Recurso.Disponibilidad.ASIGNADO,
            fecha_confirmacion_disponibilidad=ahora,
        )
        Recurso.objects.filter(pk=recursos["AMB-01"].pk).update(
            estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
            disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
            fecha_confirmacion_disponibilidad=ahora,
        )

        self.stdout.write(self.style.SUCCESS(
            "Escenarios creados: INC-2026-001 (cerrado, 12/12 SCI) e "
            "INC-2026-002 (en atención, 4/12 SCI)."
        ))
