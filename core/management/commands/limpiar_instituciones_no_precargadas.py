"""Retira las instituciones que quedaron fuera de la carga inicial.

El sistema entra en servicio como piloto en Latacunga, pero las bases creadas
antes de esa decisión ya tienen los siete Cuerpos de Bomberos de la provincia.
Quitarlos de ``cargar_datos_cotopaxi`` no los borra: este comando lo hace.

Solo elimina lo que nunca llegó a usarse. Las emergencias, los despliegues y
los usuarios asignados son historia de operación: si una estación tiene
alguno, se conserva y se informa, sin excepción.

Las evaluaciones de capacidad también detienen el borrado, pero pueden
incluirse con ``--incluir-evaluaciones``: solo describen a la estación que se
va, y fuera de ella no significan nada.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.management.commands.cargar_datos_cotopaxi import INSTITUCIONES_COTOPAXI


class Command(BaseCommand):
    help = (
        "Elimina los Cuerpos de Bomberos que ya no forman parte de la carga "
        "inicial, siempre que no tengan información operativa."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--ejecutar",
            action="store_true",
            help="Aplica los borrados. Sin esta opción solo se informa qué se haría.",
        )
        parser.add_argument(
            "--incluir-evaluaciones",
            action="store_true",
            help=(
                "Borra también las evaluaciones de capacidad de esas estaciones. "
                "Las emergencias, los despliegues y los usuarios siguen deteniendo "
                "el borrado."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from instituciones.models import CuerpoBomberos
        from inventario.models import Recurso

        siglas_precargadas = {item["sigla"] for item in INSTITUCIONES_COTOPAXI}
        sobrantes = CuerpoBomberos.objects.exclude(
            sigla__in=siglas_precargadas
        ).prefetch_related("estaciones")

        if not sobrantes:
            self.stdout.write(self.style.SUCCESS(
                "No hay instituciones fuera de la carga inicial."
            ))
            return

        eliminadas = []
        conservadas = []
        for cuerpo in sobrantes:
            impedimentos = self._impedimentos(cuerpo, options["incluir_evaluaciones"])
            if impedimentos:
                conservadas.append((cuerpo, impedimentos))
                continue
            eliminadas.append(cuerpo)

        for cuerpo, impedimentos in conservadas:
            detalle = ", ".join(f"{cantidad} {nombre}" for nombre, cantidad in impedimentos)
            self.stdout.write(self.style.WARNING(
                f"Se conserva {cuerpo.nombre}: tiene {detalle}."
            ))

        if not options["ejecutar"]:
            for cuerpo in eliminadas:
                estaciones = cuerpo.estaciones.count()
                recursos = Recurso.objects.filter(estacion__cuerpo_bomberos=cuerpo).count()
                self.stdout.write(
                    f"Se eliminaría {cuerpo.nombre}: {estaciones} estación(es) "
                    f"y {recursos} recurso(s)."
                )
            self.stdout.write(self.style.NOTICE(
                "Simulación. Repita con --ejecutar para aplicar los borrados."
            ))
            return

        total_recursos = 0
        total_estaciones = 0
        total_evaluaciones = 0
        for cuerpo in eliminadas:
            if options["incluir_evaluaciones"]:
                from operaciones.models import EvaluacionCapacidadEstacion

                borradas, _ = EvaluacionCapacidadEstacion.objects.filter(
                    estacion__cuerpo_bomberos=cuerpo
                ).delete()
                total_evaluaciones += borradas
            borrados, _ = Recurso.objects.filter(
                estacion__cuerpo_bomberos=cuerpo
            ).delete()
            total_recursos += borrados
            total_estaciones += cuerpo.estaciones.count()
            cuerpo.estaciones.all().delete()
            cuerpo.delete()

        self.stdout.write(self.style.SUCCESS(
            f"Se eliminaron {len(eliminadas)} institución(es), {total_estaciones} "
            f"estación(es), sus recursos y {total_evaluaciones} evaluación(es). "
            f"Conservadas: {len(conservadas)}."
        ))

    def _impedimentos(self, cuerpo, incluir_evaluaciones):
        """Cuenta la información operativa que impide borrar la institución."""
        from emergencias.models import DespliegueUnidad, Emergencia
        from operaciones.models import EvaluacionCapacidadEstacion
        from usuarios.models import Usuario

        estaciones = cuerpo.estaciones.all()
        conteos = (
            ("emergencia(s)", Emergencia.objects.filter(estacion_responsable__in=estaciones)),
            ("despliegue(s)", DespliegueUnidad.objects.filter(estacion_procedencia__in=estaciones)),
            ("usuario(s)", Usuario.objects.filter(estacion__in=estaciones)),
        )
        if not incluir_evaluaciones:
            conteos += (
                ("evaluación(es)",
                 EvaluacionCapacidadEstacion.objects.filter(estacion__in=estaciones)),
            )
        return [(nombre, consulta.count()) for nombre, consulta in conteos if consulta.exists()]
