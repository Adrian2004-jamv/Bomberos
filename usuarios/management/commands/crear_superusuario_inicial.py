"""Crea o recupera el acceso del superusuario en entornos sin consola."""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

_AFIRMATIVOS = ("1", "true", "yes", "on", "si", "sí")


class Command(BaseCommand):
    help = (
        "Crea el superusuario inicial a partir de variables de entorno. "
        "Con --reiniciar-clave actualiza la clave de uno que ya exista, "
        "que es la unica via de recuperar el acceso donde no hay consola."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reiniciar-clave",
            action="store_true",
            help="Actualiza la clave del usuario indicado si ya existe.",
        )

    def handle(self, *args, **opciones):
        Usuario = get_user_model()

        nombre = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        clave = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        reiniciar = opciones["reiniciar_clave"] or (
            os.environ.get("DJANGO_SUPERUSER_REINICIAR_CLAVE", "").lower() in _AFIRMATIVOS
        )

        if not nombre or not clave:
            self.stdout.write(
                "Sin DJANGO_SUPERUSER_USERNAME y DJANGO_SUPERUSER_PASSWORD "
                "definidas; no se crea ningun superusuario."
            )
            return

        existente = Usuario.objects.filter(username=nombre).first()
        if existente is not None:
            if not reiniciar:
                self.stdout.write(
                    f"El usuario «{nombre}» ya existe y no se modifica. Para "
                    "cambiarle la clave, defina DJANGO_SUPERUSER_REINICIAR_CLAVE=1."
                )
                return
            existente.set_password(clave)
            existente.is_superuser = True
            existente.is_staff = True
            existente.is_active = True
            existente.save()
            self.stdout.write(f"Clave del superusuario «{nombre}» actualizada.")
            return

        if Usuario.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                "Ya existe un superusuario con otro nombre; no se crea ninguno."
            )
            return

        Usuario.objects.create_superuser(
            username=nombre,
            email=os.environ.get("DJANGO_SUPERUSER_EMAIL", ""),
            password=clave,
            cedula=os.environ.get("DJANGO_SUPERUSER_CEDULA", ""),
        )
        self.stdout.write(f"Superusuario «{nombre}» creado.")
