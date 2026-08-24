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
    # Marca que la clave vigente la asignó otra persona: el operador que creó
    # la cuenta o restableció el acceso, o las variables de entorno del
    # despliegue. Mientras esté activa, el middleware obliga a reemplazarla.
    # El valor por omisión es falso porque quien crea la cuenta desde código
    # elige la clave para sí mismo; los tres puntos donde alguien la asigna en
    # nombre de otro la activan de forma explícita.
    debe_cambiar_clave = models.BooleanField(
        "debe cambiar la clave", default=False
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.get_full_name() or self.username
