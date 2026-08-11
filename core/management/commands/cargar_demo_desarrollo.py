from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from emergencias.models import Emergencia
from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso
from operaciones.models import RequisitoRecursoCapacidad, TipoCapacidadOperativa
from operaciones.services import evaluar_capacidad_estacion


class Command(BaseCommand):
    help = "Carga datos mínimos identificados como DEMO para recorrer los módulos existentes."

    @transaction.atomic
    def handle(self, *args, **options):
        usuario = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
        if not usuario:
            raise CommandError("Debe existir un superusuario antes de cargar la demostración.")

        canton, _ = Canton.objects.get_or_create(
            codigo="DEMO-LAT", defaults={"nombre": "Latacunga [DEMO]"}
        )
        cuerpo, _ = CuerpoBomberos.objects.get_or_create(
            sigla="CBD-LAT",
            defaults={
                "canton": canton,
                "nombre": "Cuerpo de Bomberos de Latacunga [DEMO]",
                "ruc": "0599999999001",
                "direccion": "Dirección referencial de demostración",
                "telefono": "0000000000",
                "correo": "demo@example.invalid",
            },
        )
        estacion, _ = Estacion.objects.get_or_create(
            cuerpo_bomberos=cuerpo,
            codigo="CENTRAL-DEMO",
            defaults={
                "nombre": "Estación Central [DEMO]",
                "direccion": "Ubicación referencial de demostración",
                "telefono": "0000000000",
                "latitud": "-0.933333",
                "longitud": "-78.616667",
            },
        )
        vehiculos, _ = CategoriaRecurso.objects.get_or_create(
            codigo="VEH-DEMO", defaults={"nombre": "Vehículos [DEMO]"}
        )
        equipos, _ = CategoriaRecurso.objects.get_or_create(
            codigo="EQU-DEMO", defaults={"nombre": "Equipos [DEMO]"}
        )
        autobomba, _ = TipoRecurso.objects.get_or_create(
            categoria=vehiculos,
            codigo="AUT-DEMO",
            defaults={"nombre": "Autobomba [DEMO]", "es_unidad_desplegable": True},
        )
        respiracion, _ = TipoRecurso.objects.get_or_create(
            categoria=equipos,
            codigo="ERA-DEMO",
            defaults={"nombre": "Equipo de respiración autónoma [DEMO]"},
        )
        Recurso.objects.get_or_create(
            estacion=estacion, codigo_interno="AB-01-DEMO",
            defaults={"tipo": autobomba, "nombre": "Autobomba de demostración", "marca": "Demo", "modelo": "AB-01"},
        )
        for numero in (1, 2):
            Recurso.objects.get_or_create(
                estacion=estacion, codigo_interno=f"ERA-{numero:02d}-DEMO",
                defaults={"tipo": respiracion, "nombre": f"ERA de demostración {numero}"},
            )
        capacidad, _ = TipoCapacidadOperativa.objects.get_or_create(
            codigo="INC-EST-DEMO",
            defaults={"nombre": "Respuesta a incendio estructural [DEMO]", "descripcion": "Capacidad referencial para visualizar el sistema."},
        )
        RequisitoRecursoCapacidad.objects.get_or_create(
            capacidad=capacidad, tipo_recurso=autobomba, defaults={"cantidad_minima": 1}
        )
        RequisitoRecursoCapacidad.objects.get_or_create(
            capacidad=capacidad, tipo_recurso=respiracion, defaults={"cantidad_minima": 2}
        )
        if not capacidad.evaluaciones_estaciones.filter(estacion=estacion).exists():
            evaluar_capacidad_estacion(estacion, capacidad, usuario, "Evaluación inicial de demostración.")
        Emergencia.objects.get_or_create(
            codigo="EM-DEMO-001",
            defaults={
                "tipo_emergencia": "Incendio estructural [DEMO]",
                "descripcion": "Registro de demostración; no corresponde a una emergencia real.",
                "prioridad": Emergencia.Prioridad.ALTA,
                "direccion": "Ubicación referencial de demostración",
                "estacion_responsable": estacion,
                "registrado_por": usuario,
            },
        )
        self.stdout.write(self.style.SUCCESS("Datos DEMO disponibles en dashboard y módulos."))
