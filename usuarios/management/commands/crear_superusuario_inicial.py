"""Crea el primer superusuario en entornos sin acceso a consola."""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Crea el superusuario inicial a partir de variables de entorno, "
        "solo si la base todavia no tiene ninguno."
    )

    def handle(self, *args, **opciones):
        Usuario = get_user_model()
        if Usuario.objects.filter(is_superuser=True).exists():
            self.stdout.write("Ya existe un superusuario; no se crea ninguno.")
            return

        nombre = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        clave = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if not nombre or not clave:
            self.stdout.write(
                "Sin DJANGO_SUPERUSER_USERNAME y DJANGO_SUPERUSER_PASSWORD "
                "definidas; no se crea ningun superusuario."
            )
            return

        Usuario.objects.create_superuser(
            username=nombre,
            email=os.environ.get("DJANGO_SUPERUSER_EMAIL", ""),
            password=clave,
            cedula=os.environ.get("DJANGO_SUPERUSER_CEDULA", ""),
        )
        self.stdout.write(f"Superusuario «{nombre}» creado.")
