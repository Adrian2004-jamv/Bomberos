"""Traslada a Latacunga lo que quedó en las instituciones fuera de la carga.

El sistema entra en servicio como piloto en Latacunga, pero las bases creadas
antes de esa decisión ya tienen los siete Cuerpos de Bomberos de la provincia.
Quitarlos de ``cargar_datos_cotopaxi`` no los borra: este comando lo hace.

Nada se pierde. Antes de eliminar una estación se lleva a la de destino todo lo
que colgaba de ella: emergencias, despliegues, recursos, usuarios asignados y
evaluaciones de capacidad. Solo entonces se retira la estación vacía.

El código interno de un recurso es único dentro de su estación, y las estaciones
sembradas comparten los mismos códigos (AB-01, ERA-01, ERA-02). Al trasladar un
recurso cuyo código ya existe en el destino se le añade el de su estación de
origen, de modo que se conserva la trazabilidad en lugar de fallar o de
sobrescribir.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.management.commands.cargar_datos_cotopaxi import INSTITUCIONES_COTOPAXI

DESTINO_PREDETERMINADO = "LAT-CENTRAL"
LARGO_CODIGO_RECURSO = 50

class Command(BaseCommand):
    help = (
        "Traslada la información de los Cuerpos de Bomberos que ya no forman "
        "parte de la carga inicial y luego los elimina."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--destino",
            default=DESTINO_PREDETERMINADO,
            help=(
                "Código de la estación que recibe la información. "
                f"Por omisión {DESTINO_PREDETERMINADO}."
            ),
        )
        parser.add_argument(
            "--ejecutar",
            action="store_true",
            help="Aplica los cambios. Sin esta opción solo se informa qué se haría.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from instituciones.models import CuerpoBomberos, Estacion

        siglas_precargadas = {item["sigla"] for item in INSTITUCIONES_COTOPAXI}
        destino = Estacion.objects.filter(
            codigo=options["destino"],
            cuerpo_bomberos__sigla__in=siglas_precargadas,
        ).first()
        if destino is None:
            raise CommandError(
                f"No existe la estación de destino «{options['destino']}» entre "
                "las instituciones de la carga inicial."
            )

        sobrantes = list(
            CuerpoBomberos.objects.exclude(sigla__in=siglas_precargadas)
            .prefetch_related("estaciones")
        )
        if not sobrantes:
            self.stdout.write(self.style.SUCCESS(
                "No hay instituciones fuera de la carga inicial."
            ))
            return

        estaciones = Estacion.objects.filter(cuerpo_bomberos__in=sobrantes)
        resumen = self._contar(estaciones)

        for nombre, cantidad in resumen:
            self.stdout.write(f"  {cantidad} {nombre}")
        self.stdout.write(
            f"{len(sobrantes)} institución(es) y {estaciones.count()} estación(es) "
            f"se retirarían; lo anterior pasa a {destino.codigo} - {destino.nombre}."
        )

        if not options["ejecutar"]:
            self.stdout.write(self.style.NOTICE(
                "Simulación. Repita con --ejecutar para aplicar los cambios."
            ))
            return

        movidos = self._trasladar(estaciones, destino)
        for cuerpo in sobrantes:
            cuerpo.estaciones.all().delete()
            cuerpo.delete()

        detalle = ", ".join(f"{cantidad} {nombre}" for nombre, cantidad in movidos) or "nada"
        self.stdout.write(self.style.SUCCESS(
            f"Se trasladó a {destino.codigo}: {detalle}. "
            f"Se eliminaron {len(sobrantes)} institución(es)."
        ))

    def _contar(self, estaciones):
        from emergencias.models import DespliegueUnidad, Emergencia
        from inventario.models import Recurso
        from operaciones.models import EvaluacionCapacidadEstacion
        from usuarios.models import Usuario

        conteos = (
            ("emergencia(s)", Emergencia.objects.filter(estacion_responsable__in=estaciones)),
            ("despliegue(s)", DespliegueUnidad.objects.filter(estacion_procedencia__in=estaciones)),
            ("recurso(s)", Recurso.objects.filter(estacion__in=estaciones)),
            ("usuario(s)", Usuario.objects.filter(estacion__in=estaciones)),
            ("evaluación(es)", EvaluacionCapacidadEstacion.objects.filter(estacion__in=estaciones)),
        )
        return [(nombre, consulta.count()) for nombre, consulta in conteos if consulta.exists()]

    def _trasladar(self, estaciones, destino):
        from emergencias.models import DespliegueUnidad, Emergencia
        from inventario.models import Recurso
        from operaciones.models import EvaluacionCapacidadEstacion
        from usuarios.models import Usuario

        movidos = []
        recursos = self._trasladar_recursos(estaciones, destino)
        if recursos:
            movidos.append(("recurso(s)", recursos))

        simples = (
            ("emergencia(s)", Emergencia.objects.filter(estacion_responsable__in=estaciones),
             {"estacion_responsable": destino}),
            ("despliegue(s)", DespliegueUnidad.objects.filter(estacion_procedencia__in=estaciones),
             {"estacion_procedencia": destino}),
            ("usuario(s)", Usuario.objects.filter(estacion__in=estaciones), {"estacion": destino}),
            ("evaluación(es)", EvaluacionCapacidadEstacion.objects.filter(estacion__in=estaciones),
             {"estacion": destino}),
        )
        for nombre, consulta, cambio in simples:
            cantidad = consulta.update(**cambio)
            if cantidad:
                movidos.append((nombre, cantidad))
        return movidos

    def _trasladar_recursos(self, estaciones, destino):
        """Mueve los recursos renombrando los códigos que ya existan en destino."""
        from inventario.models import Recurso

        ocupados = set(
            Recurso.objects.filter(estacion=destino).values_list("codigo_interno", flat=True)
        )
        movidos = 0
        for recurso in Recurso.objects.filter(estacion__in=estaciones).select_related("estacion"):
            codigo = recurso.codigo_interno
            if codigo in ocupados:
                codigo = self._codigo_libre(recurso, ocupados)
            ocupados.add(codigo)
            recurso.estacion = destino
            recurso.codigo_interno = codigo
            recurso.save(update_fields=["estacion", "codigo_interno"])
            movidos += 1
        return movidos

    def _codigo_libre(self, recurso, ocupados):
        origen = recurso.estacion.codigo
        base = f"{recurso.codigo_interno}-{origen}"[:LARGO_CODIGO_RECURSO]
        if base not in ocupados:
            return base
        # Caso extremo: dos estaciones de origen con el mismo código y sufijo.
        for intento in range(2, 100):
            sufijo = f"-{intento}"
            candidato = base[: LARGO_CODIGO_RECURSO - len(sufijo)] + sufijo
            if candidato not in ocupados:
                return candidato
        raise CommandError(f"No se pudo asignar un código libre para {recurso}.")
