from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def validar_fecha_no_futura(value):
    if value > timezone.localdate():
        raise ValidationError("La fecha de ingreso no puede estar en el futuro.")


class PersonalOperativo(models.Model):
    class Disponibilidad(models.TextChoices):
        DISPONIBLE = "disponible", "Disponible"
        ASIGNADO = "asignado", "Asignado"
        DESCANSO = "descanso", "Descanso"
        LICENCIA = "licencia", "Licencia"
        NO_DISPONIBLE = "no_disponible", "No disponible"

    estacion = models.ForeignKey(
        "instituciones.Estacion",
        on_delete=models.PROTECT,
        related_name="personal_operativo",
        verbose_name="estación",
    )
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="personal_operativo",
        verbose_name="cuenta de usuario",
        null=True,
        blank=True,
        help_text=(
            "La correspondencia entre la estación de esta cuenta y la del personal "
            "se validará en una etapa posterior."
        ),
    )
    codigo_institucional = models.CharField("código institucional", max_length=50)
    cedula = models.CharField("cédula", max_length=10, unique=True, null=True, blank=True)
    nombres = models.CharField("nombres", max_length=150)
    apellidos = models.CharField("apellidos", max_length=150)
    rango = models.CharField("rango", max_length=100, blank=True)
    cargo_operativo = models.CharField("cargo operativo", max_length=100, blank=True)
    telefono = models.CharField("teléfono", max_length=20, blank=True)
    fecha_ingreso = models.DateField(
        "fecha de ingreso",
        validators=[validar_fecha_no_futura],
    )
    disponibilidad = models.CharField(
        "disponibilidad",
        max_length=20,
        choices=Disponibilidad.choices,
        default=Disponibilidad.DISPONIBLE,
    )
    observaciones = models.TextField("observaciones", blank=True)
    activo = models.BooleanField("activo", default=True)
    fecha_creacion = models.DateTimeField("fecha de creación", auto_now_add=True)
    fecha_actualizacion = models.DateTimeField("fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "personal operativo"
        verbose_name_plural = "personal operativo"
        ordering = ("apellidos", "nombres")
        constraints = [
            models.UniqueConstraint(
                fields=("estacion", "codigo_institucional"),
                name="operaciones_personal_codigo_unico_por_estacion",
            ),
        ]

    @property
    def nombre_completo(self):
        return " ".join(part for part in (self.nombres, self.apellidos) if part).strip()

    @property
    def institucion(self):
        return self.estacion.cuerpo_bomberos

    def __str__(self):
        return f"{self.codigo_institucional} - {self.nombre_completo}"
