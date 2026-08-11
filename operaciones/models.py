from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def validar_fecha_no_futura(value):
    """Compatibilidad requerida por la migración histórica 0001."""
    if value > timezone.localdate():
        raise ValidationError("La fecha de ingreso no puede estar en el futuro.")


class TipoCapacidadOperativa(models.Model):
    nombre = models.CharField("nombre", max_length=150)
    codigo = models.CharField("código", max_length=30, unique=True)
    descripcion = models.TextField("descripción", blank=True)
    activo = models.BooleanField("activo", default=True)
    fecha_creacion = models.DateTimeField("fecha de creación", auto_now_add=True)
    fecha_actualizacion = models.DateTimeField("fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "tipo de capacidad operativa"
        verbose_name_plural = "tipos de capacidades operativas"
        ordering = ("nombre",)

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class RequisitoRecursoCapacidad(models.Model):
    capacidad = models.ForeignKey(
        TipoCapacidadOperativa,
        on_delete=models.PROTECT,
        related_name="requisitos_recursos",
        verbose_name="capacidad operativa",
    )
    tipo_recurso = models.ForeignKey(
        "inventario.TipoRecurso",
        on_delete=models.PROTECT,
        related_name="requisitos_capacidades",
        verbose_name="tipo de recurso",
    )
    cantidad_minima = models.PositiveIntegerField(
        "cantidad mínima",
        validators=[MinValueValidator(1)],
    )
    obligatorio = models.BooleanField("obligatorio", default=True)
    observaciones = models.TextField("observaciones", blank=True)

    class Meta:
        verbose_name = "requisito de recurso para capacidad"
        verbose_name_plural = "requisitos de recursos para capacidades"
        ordering = ("capacidad__nombre", "tipo_recurso__nombre")
        constraints = [
            models.UniqueConstraint(
                fields=("capacidad", "tipo_recurso"),
                name="operaciones_requisito_recurso_unico_por_capacidad",
            ),
            models.CheckConstraint(
                condition=models.Q(cantidad_minima__gte=1),
                name="operaciones_requisito_recurso_cantidad_positiva",
            ),
        ]

    def __str__(self):
        return f"{self.capacidad.nombre}: {self.cantidad_minima} × {self.tipo_recurso.nombre}"


class EvaluacionCapacidadEstacion(models.Model):
    class Estado(models.TextChoices):
        CUMPLE = "cumple", "Cumple"
        PARCIAL = "parcial", "Cumplimiento parcial"
        NO_CUMPLE = "no_cumple", "No cumple"

    estacion = models.ForeignKey(
        "instituciones.Estacion",
        on_delete=models.PROTECT,
        related_name="evaluaciones_capacidades",
        verbose_name="estación",
    )
    capacidad = models.ForeignKey(
        TipoCapacidadOperativa,
        on_delete=models.PROTECT,
        related_name="evaluaciones_estaciones",
        verbose_name="capacidad operativa",
    )
    estado = models.CharField("estado", max_length=15, choices=Estado.choices)
    porcentaje_cumplimiento = models.DecimalField(
        "porcentaje de cumplimiento",
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    detalle_recursos = models.JSONField("detalle de recursos", default=list)
    observaciones = models.TextField("observaciones", blank=True)
    evaluado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="evaluaciones_capacidades_realizadas",
        verbose_name="evaluado por",
        null=True,
        blank=True,
    )
    fecha_evaluacion = models.DateTimeField("fecha de evaluación", auto_now_add=True)

    class Meta:
        verbose_name = "evaluación de capacidad de estación"
        verbose_name_plural = "evaluaciones de capacidades de estaciones"
        ordering = ("-fecha_evaluacion", "-pk")

    def __str__(self):
        return f"{self.estacion} - {self.capacidad.nombre} - {self.get_estado_display()}"
