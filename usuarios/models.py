from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    estacion = models.ForeignKey(
        "instituciones.Estacion",
        on_delete=models.PROTECT,
        related_name="usuarios",
        verbose_name="estación",
        null=True,
        blank=True,
    )
    cedula = models.CharField(max_length=10, unique=True)
    telefono = models.CharField(max_length=15, blank=True)
    cargo_institucional = models.CharField(max_length=100, blank=True)
    debe_cambiar_clave = models.BooleanField(default=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.get_full_name() or self.username
