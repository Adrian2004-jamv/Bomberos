from datetime import timedelta

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

class CategoriaRecurso(models.Model):
    nombre = models.CharField("nombre", max_length=100)
    codigo = models.CharField("código", max_length=20, unique=True)
    descripcion = models.TextField("descripción", blank=True)
    activo = models.BooleanField("activo", default=True)
    fecha_creacion = models.DateTimeField("fecha de creación", auto_now_add=True)
    fecha_actualizacion = models.DateTimeField("fecha de actualización", auto_now=True)
    class Meta:
        verbose_name = "categoría de recurso"
        verbose_name_plural = "categorías de recursos"
        ordering = ("nombre",)

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

class TipoRecurso(models.Model):
    categoria = models.ForeignKey(
        CategoriaRecurso,
        on_delete=models.PROTECT,
        related_name="tipos_recurso",
        verbose_name="categoría",
    )
    nombre = models.CharField("nombre", max_length=100)
    codigo = models.CharField("código", max_length=20)
    descripcion = models.TextField("descripción", blank=True)
    activo = models.BooleanField("activo", default=True)
    es_unidad_desplegable = models.BooleanField(
        "es unidad desplegable",
        default=False,
        help_text="Indica si los recursos de este tipo pueden despacharse a emergencias.",
    )
    fecha_creacion = models.DateTimeField("fecha de creación", auto_now_add=True)
    fecha_actualizacion = models.DateTimeField("fecha de actualización", auto_now=True)
    class Meta:
        verbose_name = "tipo de recurso"
        verbose_name_plural = "tipos de recursos"
        ordering = ("categoria__nombre", "nombre")
        constraints = [
            models.UniqueConstraint(
                fields=("categoria", "codigo"),
                name="inventario_tipo_codigo_unico_por_categoria",
            ),
        ]

    def __str__(self):
        return f"{self.categoria.codigo} / {self.codigo} - {self.nombre}"

class Recurso(models.Model):
    class EstadoOperativo(models.TextChoices):
        OPERATIVO = "operativo", "Operativo"
        MANTENIMIENTO = "mantenimiento", "En mantenimiento"
        FUERA_SERVICIO = "fuera_servicio", "Fuera de servicio"
        DADO_BAJA = "dado_baja", "Dado de baja"

    class Disponibilidad(models.TextChoices):
        DISPONIBLE = "disponible", "Disponible"
        ASIGNADO = "asignado", "Asignado"
        RESERVADO = "reservado", "Reservado"
        NO_DISPONIBLE = "no_disponible", "No disponible"

    estacion = models.ForeignKey(
        "instituciones.Estacion",
        on_delete=models.PROTECT,
        related_name="recursos",
        verbose_name="estación",
    )
    tipo = models.ForeignKey(
        TipoRecurso,
        on_delete=models.PROTECT,
        related_name="recursos",
        verbose_name="tipo de recurso",
    )
    codigo_interno = models.CharField("código interno", max_length=50)
    nombre = models.CharField("nombre", max_length=150)
    descripcion = models.TextField("descripción", blank=True)
    marca = models.CharField("marca", max_length=100, blank=True)
    modelo = models.CharField("modelo", max_length=100, blank=True)
    numero_serie = models.CharField("número de serie", max_length=100, blank=True)
    anio_fabricacion = models.PositiveIntegerField(
        "año de fabricación",
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    estado_operativo = models.CharField(
        "estado operativo",
        max_length=20,
        choices=EstadoOperativo.choices,
        default=EstadoOperativo.OPERATIVO,
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
    fecha_confirmacion_disponibilidad = models.DateTimeField(
        "fecha de confirmación de disponibilidad", null=True, blank=True
    )

    @property
    def disponibilidad_actualizada(self):
        """La confirmación operativa se considera vigente durante 24 horas."""
        if not self.fecha_confirmacion_disponibilidad:
            return False
        return self.fecha_confirmacion_disponibilidad >= timezone.now() - timedelta(hours=24)

    class Meta:
        verbose_name = "recurso"
        verbose_name_plural = "recursos"
        ordering = ("estacion__nombre", "codigo_interno")
        constraints = [
            models.UniqueConstraint(
                fields=("estacion", "codigo_interno"),
                name="inventario_recurso_codigo_unico_por_estacion",
            ),
        ]

    def __str__(self):
        return f"{self.codigo_interno} - {self.nombre}"

class HistorialEstadoRecurso(models.Model):
    recurso = models.ForeignKey(
        Recurso,
        on_delete=models.CASCADE,
        related_name="historial_estados",
        verbose_name="recurso",
    )
    estado_anterior = models.CharField(
        "estado anterior", max_length=20, choices=Recurso.EstadoOperativo.choices
    )
    estado_nuevo = models.CharField(
        "estado nuevo", max_length=20, choices=Recurso.EstadoOperativo.choices
    )
    disponibilidad_anterior = models.CharField(
        "disponibilidad anterior",
        max_length=20,
        choices=Recurso.Disponibilidad.choices,
    )
    disponibilidad_nueva = models.CharField(
        "disponibilidad nueva",
        max_length=20,
        choices=Recurso.Disponibilidad.choices,
    )
    motivo = models.CharField("motivo", max_length=255)
    observaciones = models.TextField("observaciones", blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cambios_estado_recursos",
        verbose_name="registrado por",
    )
    fecha_registro = models.DateTimeField("fecha de registro", auto_now_add=True)

    class Meta:
        verbose_name = "historial de estado de recurso"
        verbose_name_plural = "historiales de estado de recursos"
        ordering = ("-fecha_registro", "-pk")

    def __str__(self):
        return f"{self.recurso} - {self.fecha_registro:%Y-%m-%d %H:%M:%S}"
