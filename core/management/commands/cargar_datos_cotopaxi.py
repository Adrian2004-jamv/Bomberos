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
        self.stdout.write(self.style.SUCCESS(
            f"Cantones de Cotopaxi disponibles: 7 ({creados} creados, {actualizados} actualizados)."
        ))
