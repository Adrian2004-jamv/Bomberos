from django.core.management.base import BaseCommand
from django.db import transaction

from instituciones.models import Canton


CANTONES_COTOPAXI = (
    ("LATACUNGA", "Latacunga"),
    ("LA-MANA", "La Maná"),
    ("PANGUA", "Pangua"),
    ("PUJILI", "Pujilí"),
    ("SALCEDO", "Salcedo"),
    ("SAQUISILI", "Saquisilí"),
    ("SIGCHOS", "Sigchos"),
)

INSTITUCIONES_COTOPAXI = (
    ("LATACUNGA", "Cuerpo de Bomberos de Latacunga", "CBL", "PEND000000001", "LAT-CENTRAL", "Estación Central", "-0.933333", "-78.616667"),
    ("LA-MANA", "Cuerpo de Bomberos de La Maná", "CBLM", "PEND000000002", "LAM-CENTRAL", "Estación Principal de La Maná", "-0.940940", "-79.225060"),
    ("PANGUA", "Cuerpo de Bomberos de Pangua", "CBP", "PEND000000003", "PAN-CENTRAL", "Estación Principal de Pangua", "-1.126000", "-79.084000"),
    ("PUJILI", "Cuerpo de Bomberos de Pujilí", "CBPU", "PEND000000004", "PUJ-CENTRAL", "Estación Principal de Pujilí", "-0.957600", "-78.696400"),
    ("SALCEDO", "Cuerpo de Bomberos de Salcedo", "CBS", "PEND000000005", "SAL-CENTRAL", "Estación Principal de Salcedo", "-1.045500", "-78.590600"),
    ("SAQUISILI", "Cuerpo de Bomberos de Saquisilí", "CBSA", "PEND000000006", "SAQ-CENTRAL", "Estación Principal de Saquisilí", "-0.839900", "-78.667000"),
    ("SIGCHOS", "Cuerpo de Bomberos de Sigchos", "CBSI", "PEND000000007", "SIG-CENTRAL", "Estación Principal de Sigchos", "-0.701000", "-78.889000"),
)


class Command(BaseCommand):
    help = "Carga el catálogo inicial de los siete cantones de Cotopaxi."

    @transaction.atomic
    def handle(self, *args, **options):
        canton_anterior = Canton.objects.filter(codigo="DEMO-LAT").first()
        if canton_anterior and not Canton.objects.filter(codigo="LATACUNGA").exists():
            canton_anterior.codigo = "LATACUNGA"
            canton_anterior.nombre = "Latacunga"
            canton_anterior.save(update_fields=("codigo", "nombre", "fecha_actualizacion"))

        # Normaliza los registros iniciales antiguos sin alterar sus relaciones.
        from emergencias.models import Emergencia
        from instituciones.models import CuerpoBomberos, Estacion
        from inventario.models import CategoriaRecurso, Recurso, TipoRecurso
        from operaciones.models import TipoCapacidadOperativa

        CuerpoBomberos.objects.filter(sigla="CBD-LAT").update(
            sigla="CBL", nombre="Cuerpo de Bomberos de Latacunga"
        )
        Estacion.objects.filter(codigo="CENTRAL-DEMO").update(
            codigo="CENTRAL", nombre="Estación Central"
        )
        CategoriaRecurso.objects.filter(codigo="VEH-DEMO").update(codigo="VEH", nombre="Vehículos")
        CategoriaRecurso.objects.filter(codigo="EQU-DEMO").update(codigo="EQU", nombre="Equipos")
        TipoRecurso.objects.filter(codigo="AUT-DEMO").update(codigo="AUT", nombre="Autobomba")
        TipoRecurso.objects.filter(codigo="ERA-DEMO").update(
            codigo="ERA", nombre="Equipo de respiración autónoma"
        )
        Recurso.objects.filter(codigo_interno="AB-01-DEMO").update(
            codigo_interno="AB-01", nombre="Autobomba", marca="Sin registrar"
        )
        for numero in (1, 2):
            Recurso.objects.filter(codigo_interno=f"ERA-{numero:02d}-DEMO").update(
                codigo_interno=f"ERA-{numero:02d}", nombre=f"Equipo ERA {numero:02d}"
            )
        Emergencia.objects.filter(codigo="EM-DEMO-001").update(
            codigo="EM-001", tipo_emergencia="Incendio estructural",
            descripcion="Incendio estructural registrado", direccion="Latacunga",
        )
        TipoCapacidadOperativa.objects.filter(codigo="INC-EST-DEMO").update(
            codigo="INC-EST", nombre="Respuesta a incendio estructural",
            descripcion="Capacidad de respuesta ante incendios estructurales.",
        )

        creados = 0
        actualizados = 0
        for codigo, nombre in CANTONES_COTOPAXI:
            _, creado = Canton.objects.update_or_create(
                codigo=codigo, defaults={"nombre": nombre, "activo": True}
            )
            creados += int(creado)
            actualizados += int(not creado)

        cuerpos_creados = 0
        estaciones_creadas = 0
        for canton_codigo, nombre, sigla, ruc, codigo_estacion, nombre_estacion, latitud, longitud in INSTITUCIONES_COTOPAXI:
            canton = Canton.objects.get(codigo=canton_codigo)
            cuerpo, cuerpo_creado = CuerpoBomberos.objects.update_or_create(
                sigla=sigla,
                defaults={
                    "canton": canton,
                    "nombre": nombre,
                    "ruc": ruc,
                    "direccion": "Dirección pendiente de registro",
                    "telefono": "",
                    "correo": "",
                    "sitio_web": "",
                    "activo": True,
                },
            )
            cuerpos_creados += int(cuerpo_creado)
            if canton_codigo == "LATACUNGA":
                Estacion.objects.filter(cuerpo_bomberos=cuerpo, codigo="CENTRAL").update(
                    codigo=codigo_estacion, nombre=nombre_estacion
                )
            estacion, estacion_creada = Estacion.objects.get_or_create(
                cuerpo_bomberos=cuerpo,
                codigo=codigo_estacion,
                defaults={
                    "nombre": nombre_estacion,
                    "direccion": "Dirección pendiente de registro",
                    "telefono": "",
                    "latitud": latitud,
                    "longitud": longitud,
                    "activo": True,
                },
            )
            estaciones_creadas += int(estacion_creada)
        self.stdout.write(self.style.SUCCESS(
            f"Cotopaxi disponible: 7 cantones, 7 Cuerpos de Bomberos y 7 estaciones principales. "
            f"Nuevos: {creados} cantones, {cuerpos_creados} cuerpos y {estaciones_creadas} estaciones."
        ))
