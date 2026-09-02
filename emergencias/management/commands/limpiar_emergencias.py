"""Retira emergencias de prueba junto con todo lo que cuelga de ellas.

Las emergencias se protegen a nivel de base de datos: sus formularios SCI y
sus despliegues las referencian con ``PROTECT``, de modo que el botón de
borrar de la interfaz solo sirve para una que aún no tenga historia. Para
vaciar el padrón de pruebas hace falta desmontar esa dependencia en orden, y
eso es lo que hace este comando.

Ensaya por omisión. Sin ``--ejecutar`` cuenta lo que retiraría y no toca nada.

Uso:
    python manage.py limpiar_emergencias --antes-de 2026-09-02
    python manage.py limpiar_emergencias --codigo IF-02092026-001 --ejecutar
    python manage.py limpiar_emergencias --todas --ejecutar
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date

from emergencias.models import (DespliegueUnidad, Emergencia, FormularioSCI,
                                FormularioSCI211, PosicionUnidad)
from emergencias.services import retirar_emergencias


class Command(BaseCommand):
    help = "Retira emergencias y su documentación. Ensaya salvo que se pase --ejecutar."

    def add_arguments(self, parser):
        parser.add_argument(
            "--antes-de", dest="antes_de", metavar="AAAA-MM-DD",
            help="Retira las reportadas antes de esa fecha, sin incluirla.",
        )
        parser.add_argument(
            "--codigo", dest="codigos", action="append", default=[],
            help="Código concreto. Puede repetirse.",
        )
        parser.add_argument(
            "--estacion", dest="estacion",
            help="Código de la estación responsable.",
        )
        parser.add_argument(
            "--todas", action="store_true",
            help="Retira todas las del ámbito indicado. Úselo con cuidado.",
        )
        parser.add_argument(
            "--ejecutar", action="store_true",
            help="Aplica los cambios. Sin esto solo se informa.",
        )

    def seleccionar(self, opciones):
        """Traduce las opciones a la consulta, exigiendo al menos un criterio.

        Un comando destructivo que sin argumentos borra el padrón entero es un
        accidente esperando su turno, así que aquí no hay comportamiento por
        omisión: o se acota, o se pide «--todas» a conciencia.
        """
        consulta = Emergencia.objects.all()
        acotada = False

        if opciones["antes_de"]:
            fecha = parse_date(opciones["antes_de"])
            if fecha is None:
                raise CommandError(
                    f"«{opciones['antes_de']}» no es una fecha AAAA-MM-DD."
                )
            consulta = consulta.filter(fecha_reporte__date__lt=fecha)
            acotada = True
        if opciones["codigos"]:
            consulta = consulta.filter(codigo__in=opciones["codigos"])
            acotada = True
        if opciones["estacion"]:
            consulta = consulta.filter(
                estacion_responsable__codigo=opciones["estacion"]
            )
            acotada = True

        if not acotada and not opciones["todas"]:
            raise CommandError(
                "Indique --antes-de, --codigo o --estacion, o bien --todas "
                "para retirar el padrón completo."
            )
        return consulta.select_related("estacion_responsable")

    def handle(self, *args, **opciones):
        emergencias = self.seleccionar(opciones)
        identificadores = list(emergencias.values_list("pk", flat=True))
        if not identificadores:
            self.stdout.write(self.style.WARNING(
                "Ninguna emergencia coincide con el criterio."
            ))
            return

        despliegues = DespliegueUnidad.objects.filter(
            emergencia_id__in=identificadores
        )
        recuento = {
            "emergencias": len(identificadores),
            "despliegues": despliegues.count(),
            "posiciones": PosicionUnidad.objects.filter(
                despliegue__emergencia_id__in=identificadores
            ).count(),
            "formularios": FormularioSCI.objects.filter(
                emergencia_id__in=identificadores
            ).count(),
            "sci211": FormularioSCI211.objects.filter(
                emergencia_id__in=identificadores
            ).count(),
        }

        for emergencia in emergencias:
            self.stdout.write(
                f"  {emergencia.codigo} · {emergencia.tipo_emergencia} · "
                f"{emergencia.estacion_responsable.codigo} · "
                f"{emergencia.fecha_reporte:%d/%m/%Y %H:%M}"
            )
        self.stdout.write(
            f"\n{recuento['emergencias']} emergencia(s), "
            f"{recuento['sci211']} SCI-211, {recuento['formularios']} formulario(s) "
            f"genéricos, {recuento['despliegues']} despliegue(s) y "
            f"{recuento['posiciones']} posición(es) de GPS."
        )

        if not opciones["ejecutar"]:
            self.stdout.write(self.style.WARNING(
                "Simulación. Repita con --ejecutar para aplicar los cambios."
            ))
            return

        liberadas = retirar_emergencias(identificadores)
        self.stdout.write(self.style.SUCCESS(
            f"Retiradas {recuento['emergencias']} emergencia(s). "
            f"{liberadas} unidad(es) volvieron a estar disponibles."
        ))
