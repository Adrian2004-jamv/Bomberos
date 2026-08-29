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

# El sistema arranca como piloto en Latacunga: es la única institución que se
# precarga, con sus tres estaciones. Los demás cantones siguen en
# CANTONES_COTOPAXI porque son el catálogo geográfico de la provincia —una
# emergencia puede ubicarse en cualquiera de ellos— y sus Cuerpos de Bomberos se
# sumarán cuando se incorporen al sistema.
#
# Cada institución lleva su lista de estaciones, declaradas como
# (código, nombre, dirección, latitud, longitud).
#
# Las tres estaciones de Latacunga y sus coordenadas provienen de la ficha
# pública de cada una en Google Maps. Las direcciones deben confirmarse con la
# institución: solo la de Sánchez de Orellana figura con nombre de calle; las
# otras dos aparecen con código plus (29XW+X5R y 69WQ+PM3) y su calle se tomó
# del trazado del mapa.
INSTITUCIONES_COTOPAXI = (
    {
        "canton": "LATACUNGA", "nombre": "Cuerpo de Bomberos de Latacunga",
        "sigla": "CBL", "ruc": "PEND000000001",
        "estaciones": (
            ("LAT-CENTRAL", "Estación Central",
             "C. Fernando Sánchez de Orellana, Latacunga",
             "-0.936987", "-78.613233"),
            ("LAT-ABRIL", "Estación Primero de Abril",
             "Av. Primero de Abril, Latacunga",
             "-0.949780", "-78.604278"),
            ("LAT-LASSO", "Estación Lasso",
             "Parroquia Lasso, cantón Latacunga",
             "-0.752976", "-78.610577"),
        ),
    },
)


class Command(BaseCommand):
    help = "Carga los cantones de Cotopaxi y el Cuerpo de Bomberos de Latacunga."

    @transaction.atomic
    def handle(self, *args, **options):
        canton_anterior = Canton.objects.filter(codigo="DEMO-LAT").first()
        if canton_anterior and not Canton.objects.filter(codigo="LATACUNGA").exists():
            canton_anterior.codigo = "LATACUNGA"
            canton_anterior.nombre = "Latacunga"
            canton_anterior.save(update_fields=("codigo", "nombre", "fecha_actualizacion"))

        # Normaliza los registros iniciales antiguos sin alterar sus relaciones.
        from emergencias.codigos import codigo_fijo
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
        # El registro de demostración se promueve a incidente real. Se busca por
        # su dirección porque el código ya no es un literal fijo, y se recodifica
        # con el formato oficial a partir de su propia fecha de reporte.
        demostracion = Emergencia.objects.filter(
            direccion="Ubicación referencial de demostración"
        ).first()
        if demostracion:
            demostracion.tipo_emergencia = "Incendio estructural"
            demostracion.descripcion = "Incendio estructural registrado"
            demostracion.direccion = "Latacunga"
            demostracion.codigo = codigo_fijo(
                demostracion.tipo_emergencia, demostracion.fecha_reporte
            )
            demostracion.save(update_fields=[
                "tipo_emergencia", "descripcion", "direccion", "codigo",
            ])
        TipoCapacidadOperativa.objects.filter(codigo="INC-EST-DEMO").update(
            codigo="INC-EST", nombre="Respuesta a incendio estructural",
            descripcion="Capacidad de respuesta ante incendios estructurales.",
        )

        Estacion.objects.filter(
            codigo="LAT-CENTRAL", latitud="-0.933333", longitud="-78.616667"
        ).update(
            latitud="-0.936987", longitud="-78.613233",
            direccion="C. Fernando Sánchez de Orellana, Latacunga",
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
        estaciones_principales = []
        for institucion in INSTITUCIONES_COTOPAXI:
            canton = Canton.objects.get(codigo=institucion["canton"])
            cuerpo, cuerpo_creado = CuerpoBomberos.objects.update_or_create(
                sigla=institucion["sigla"],
                defaults={
                    "canton": canton,
                    "nombre": institucion["nombre"],
                    "ruc": institucion["ruc"],
                    "direccion": "Dirección pendiente de registro",
                    "telefono": "",
                    "correo": "",
                    "sitio_web": "",
                    "activo": True,
                },
            )
            cuerpos_creados += int(cuerpo_creado)
            for indice, (codigo_estacion, nombre_estacion, direccion_estacion,
                          latitud, longitud) in enumerate(institucion["estaciones"]):
                if institucion["canton"] == "LATACUNGA" and indice == 0:
                    # Renombra la estación genérica que dejaba la carga anterior.
                    Estacion.objects.filter(cuerpo_bomberos=cuerpo, codigo="CENTRAL").update(
                        codigo=codigo_estacion, nombre=nombre_estacion
                    )
                estacion, estacion_creada = Estacion.objects.get_or_create(
                    cuerpo_bomberos=cuerpo,
                    codigo=codigo_estacion,
                    defaults={
                        "nombre": nombre_estacion,
                        "direccion": direccion_estacion,
                        "telefono": "",
                        "latitud": latitud,
                        "longitud": longitud,
                        "activo": True,
                    },
                )
                estaciones_creadas += int(estacion_creada)
                estaciones_principales.append(estacion)

        categoria_vehiculos, _ = CategoriaRecurso.objects.update_or_create(
            codigo="VEH", defaults={"nombre": "Vehículos", "activo": True}
        )
        categoria_equipos, _ = CategoriaRecurso.objects.update_or_create(
            codigo="EQU", defaults={"nombre": "Equipos", "activo": True}
        )
        tipo_autobomba, _ = TipoRecurso.objects.update_or_create(
            categoria=categoria_vehiculos,
            codigo="AUT",
            defaults={"nombre": "Autobomba", "es_unidad_desplegable": True, "activo": True},
        )
        tipo_era, _ = TipoRecurso.objects.update_or_create(
            categoria=categoria_equipos,
            codigo="ERA",
            defaults={"nombre": "Equipo de respiración autónoma", "activo": True},
        )
        recursos_creados = 0
        for estacion in estaciones_principales:
            recursos_iniciales = (
                (tipo_autobomba, "AB-01", "Autobomba"),
                (tipo_era, "ERA-01", "Equipo ERA 01"),
                (tipo_era, "ERA-02", "Equipo ERA 02"),
            )
            for tipo, codigo, nombre in recursos_iniciales:
                _, recurso_creado = Recurso.objects.get_or_create(
                    estacion=estacion,
                    codigo_interno=codigo,
                    defaults={
                        "tipo": tipo,
                        "nombre": nombre,
                        "descripcion": "Carga inicial pendiente de actualización institucional.",
                        "observaciones": "Verificar características, identificación y estado con la institución responsable.",
                    },
                )
                recursos_creados += int(recurso_creado)
        self.stdout.write(self.style.SUCCESS(
            f"Cotopaxi disponible: {len(CANTONES_COTOPAXI)} cantones, "
            f"{len(INSTITUCIONES_COTOPAXI)} "
            f"{'Cuerpo' if len(INSTITUCIONES_COTOPAXI) == 1 else 'Cuerpos'} de Bomberos y "
            f"{sum(len(i['estaciones']) for i in INSTITUCIONES_COTOPAXI)} estaciones. "
            f"Nuevos: {creados} cantones, {cuerpos_creados} cuerpos, {estaciones_creadas} estaciones "
            f"y {recursos_creados} recursos iniciales."
        ))
