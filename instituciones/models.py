from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Canton(models.Model):
    nombre = models.CharField("nombre", max_length=100)
    codigo = models.CharField("código", max_length=10, unique=True)
    activo = models.BooleanField("activo", default=True)
    fecha_creacion = models.DateTimeField("fecha de creación", auto_now_add=True)
    fecha_actualizacion = models.DateTimeField("fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "cantón"
        verbose_name_plural = "cantones"
        ordering = ("nombre",)

    def __str__(self):
        return self.nombre


class CuerpoBomberos(models.Model):
    canton = models.ForeignKey(
        Canton,
        on_delete=models.PROTECT,
        related_name="cuerpos_bomberos",
        verbose_name="cantón",
    )
    nombre = models.CharField("nombre", max_length=150)
    sigla = models.CharField("sigla", max_length=20, unique=True)
    ruc = models.CharField("RUC", max_length=13, unique=True)
    direccion = models.CharField("dirección", max_length=255)
    telefono = models.CharField("teléfono", max_length=20, blank=True)
    correo = models.EmailField("correo electrónico", blank=True)
    sitio_web = models.URLField("sitio web", blank=True)
    activo = models.BooleanField("activo", default=True)
    fecha_creacion = models.DateTimeField("fecha de creación", auto_now_add=True)
    fecha_actualizacion = models.DateTimeField("fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "Cuerpo de Bomberos"
        verbose_name_plural = "Cuerpos de Bomberos"
        ordering = ("nombre",)

    def __str__(self):
        return f"{self.sigla} - {self.nombre}"


class Estacion(models.Model):
    cuerpo_bomberos = models.ForeignKey(
        CuerpoBomberos,
        on_delete=models.PROTECT,
        related_name="estaciones",
        verbose_name="Cuerpo de Bomberos",
    )
    nombre = models.CharField("nombre", max_length=150)
    codigo = models.CharField("código", max_length=20)
    direccion = models.CharField("dirección", max_length=255)
    telefono = models.CharField("teléfono", max_length=20, blank=True)
    latitud = models.DecimalField(
        "latitud",
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitud = models.DecimalField(
        "longitud",
        max_digits=10,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    activo = models.BooleanField("activo", default=True)
    fecha_creacion = models.DateTimeField("fecha de creación", auto_now_add=True)
    fecha_actualizacion = models.DateTimeField("fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "estación"
        verbose_name_plural = "estaciones"
        ordering = ("cuerpo_bomberos__nombre", "nombre")
        constraints = [
            models.UniqueConstraint(
                fields=("cuerpo_bomberos", "codigo"),
                name="instituciones_estacion_codigo_unico_por_cuerpo",
            ),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
