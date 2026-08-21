from django.core.management.base import BaseCommand
from django.db import transaction

from instituciones.models import Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso


CATEGORIAS = (
    ("VEH", "Vehículos", "Vehículos destinados a respuesta y atención de emergencias."),
    ("EPP", "Equipos de protección personal", "Protección respiratoria, estructural y forestal."),
    ("SUP", "Supresión de incendios", "Equipos para abastecimiento y aplicación de agentes extintores."),
    ("RES", "Rescate", "Herramientas para búsqueda, rescate y extricación."),
    ("APH", "Atención prehospitalaria", "Recursos para estabilización y traslado de pacientes."),
    ("COM", "Comunicaciones", "Equipos para coordinación y comunicaciones operativas."),
)

TIPOS = (
    ("VEH", "AUT", "Autobomba", True),
    ("VEH", "AMB-II", "Ambulancia tipo II", True),
    ("VEH", "VIR-4X4", "Vehículo de intervención rápida 4x4", True),
    ("EPP", "ERA", "Equipo de respiración autónoma", False),
    ("EPP", "EPP-EST", "Equipo de protección estructural", False),
    ("EPP", "EPP-FOR", "Equipo de protección forestal", False),
    ("SUP", "MANG-15", "Manguera contra incendios de 1,5 pulgadas", False),
    ("SUP", "MANG-25", "Manguera contra incendios de 2,5 pulgadas", False),
    ("SUP", "MOTOBOMBA", "Motobomba portátil", False),
    ("RES", "EXT-HID", "Equipo hidráulico de extricación", False),
    ("RES", "CAM-TERM", "Cámara térmica", False),
    ("RES", "DET-GAS", "Detector multigás", False),
    ("APH", "DEA", "Desfibrilador externo automático", False),
    ("APH", "CAM-EM", "Camilla de emergencia", False),
    ("COM", "RAD-PORT", "Radio portátil", False),
)

RECURSOS_POR_ESTACION = (
    ("AB-01", "AUT", "Autobomba de primera intervención"),
    ("AMB-01", "AMB-II", "Ambulancia tipo II"),
    ("ERA-01", "ERA", "Equipo de respiración autónoma 01"),
    ("ERA-02", "ERA", "Equipo de respiración autónoma 02"),
    ("EPP-E-01", "EPP-EST", "Equipo de protección estructural 01"),
    ("EPP-E-02", "EPP-EST", "Equipo de protección estructural 02"),
    ("EPP-F-01", "EPP-FOR", "Equipo de protección forestal 01"),
    ("EXT-01", "EXT-HID", "Equipo hidráulico de extricación"),
    ("MB-01", "MOTOBOMBA", "Motobomba portátil"),
    ("CT-01", "CAM-TERM", "Cámara térmica"),
    ("RAD-01", "RAD-PORT", "Radio portátil de operaciones"),
    ("MG-15-01", "MANG-15", "Manguera contra incendios de 1,5 pulgadas"),
)

OBSERVACION_REFERENCIAL = (
    "Registro inicial basado en denominaciones de contratación pública bomberil ecuatoriana. "
    "La institución debe validar físicamente marca, modelo, serie, año y existencia del bien."
)


class Command(BaseCommand):
    help = "Carga un catálogo bomberil y un inventario inicial verificable para cada estación activa."

    @transaction.atomic
    def handle(self, *args, **options):
        categoria_heredada = CategoriaRecurso.objects.filter(codigo="EQU").first()
        if categoria_heredada and not CategoriaRecurso.objects.filter(codigo="EPP").exists():
            categoria_heredada.codigo = "EPP"
            categoria_heredada.save(update_fields=["codigo"])

        categorias = {}
        for codigo, nombre, descripcion in CATEGORIAS:
            categoria, _ = CategoriaRecurso.objects.update_or_create(
                codigo=codigo,
                defaults={"nombre": nombre, "descripcion": descripcion, "activo": True},
            )
            categorias[codigo] = categoria

        tipos = {}
        for categoria_codigo, codigo, nombre, desplegable in TIPOS:
            tipo, _ = TipoRecurso.objects.update_or_create(
                categoria=categorias[categoria_codigo],
                codigo=codigo,
                defaults={
                    "nombre": nombre,
                    "descripcion": "Denominación normalizada para inventario institucional.",
                    "activo": True,
                    "es_unidad_desplegable": desplegable,
                },
            )
            tipos[codigo] = tipo

        creados = 0
        existentes = 0
        estaciones = Estacion.objects.filter(activo=True).select_related(
            "cuerpo_bomberos", "cuerpo_bomberos__canton"
        )
        for estacion in estaciones:
            for codigo, tipo_codigo, nombre in RECURSOS_POR_ESTACION:
                _, creado = Recurso.objects.get_or_create(
                    estacion=estacion,
                    codigo_interno=codigo,
                    defaults={
                        "tipo": tipos[tipo_codigo],
                        "nombre": nombre,
                        "descripcion": f"Recurso asignado a {estacion.nombre}.",
                        "estado_operativo": Recurso.EstadoOperativo.OPERATIVO,
                        "disponibilidad": Recurso.Disponibilidad.DISPONIBLE,
                        "observaciones": OBSERVACION_REFERENCIAL,
                        "activo": True,
                        "fecha_confirmacion_disponibilidad": None,
                    },
                )
                creados += int(creado)
                existentes += int(not creado)

        self.stdout.write(self.style.SUCCESS(
            f"Catálogo actualizado. Recursos creados: {creados}; existentes conservados: {existentes}."
        ))
