from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Emergencia(models.Model):
    class Prioridad(models.TextChoices):
        BAJA = "baja", "Baja"
        MEDIA = "media", "Media"
        ALTA = "alta", "Alta"
        CRITICA = "critica", "Crítica"

    class Estado(models.TextChoices):
        REPORTADA = "reportada", "Reportada"
        EN_ATENCION = "en_atencion", "En atención"
        CONTROLADA = "controlada", "Controlada"
        CERRADA = "cerrada", "Cerrada"
        CANCELADA = "cancelada", "Cancelada"

    codigo = models.CharField("código", max_length=30, unique=True)
    tipo_emergencia = models.CharField("tipo de emergencia", max_length=120)
    descripcion = models.TextField("descripción", blank=True)
    prioridad = models.CharField(
        "prioridad", max_length=10, choices=Prioridad.choices, default=Prioridad.MEDIA
    )
    estado = models.CharField(
        "estado", max_length=15, choices=Estado.choices, default=Estado.REPORTADA
    )
    fecha_reporte = models.DateTimeField("fecha y hora del reporte", default=timezone.now)
    fecha_cierre = models.DateTimeField("fecha y hora de cierre", null=True, blank=True)
    direccion = models.CharField("dirección o referencia", max_length=255)
    latitud = models.DecimalField(
        "latitud",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitud = models.DecimalField(
        "longitud",
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    estacion_responsable = models.ForeignKey(
        "instituciones.Estacion",
        on_delete=models.PROTECT,
        related_name="emergencias_responsables",
        verbose_name="estación responsable",
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="emergencias_registradas",
        verbose_name="registrado por",
    )
    fecha_creacion = models.DateTimeField("fecha de creación", auto_now_add=True)
    fecha_actualizacion = models.DateTimeField("fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "emergencia"
        verbose_name_plural = "emergencias"
        ordering = ("-fecha_reporte", "-pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fecha_cierre__isnull=True)
                | models.Q(fecha_cierre__gte=models.F("fecha_reporte")),
                name="emergencias_cierre_no_anterior_reporte",
            )
        ]

    def clean(self):
        super().clean()
        if self.fecha_cierre and self.fecha_reporte and self.fecha_cierre < self.fecha_reporte:
            raise ValidationError(
                {"fecha_cierre": "La fecha de cierre no puede ser anterior al reporte."}
            )

    @property
    def admite_despliegues(self):
        return self.estado not in {self.Estado.CERRADA, self.Estado.CANCELADA}

    def __str__(self):
        return f"{self.codigo} - {self.tipo_emergencia}"


class DespliegueUnidad(models.Model):
    class Estado(models.TextChoices):
        ASIGNADA = "asignada", "Asignada"
        EN_RUTA = "en_ruta", "En ruta"
        EN_SITIO = "en_sitio", "En sitio"
        RETORNANDO = "retornando", "Retornando"
        FINALIZADA = "finalizada", "Finalizada"
        CANCELADA = "cancelada", "Cancelada"

    ESTADOS_ACTIVOS = (Estado.ASIGNADA, Estado.EN_RUTA, Estado.EN_SITIO, Estado.RETORNANDO)
    ESTADOS_FINALES = (Estado.FINALIZADA, Estado.CANCELADA)

    emergencia = models.ForeignKey(
        Emergencia,
        on_delete=models.PROTECT,
        related_name="despliegues",
        verbose_name="emergencia",
    )
    unidad = models.ForeignKey(
        "inventario.Recurso",
        on_delete=models.PROTECT,
        related_name="despliegues_emergencias",
        verbose_name="unidad",
    )
    estacion_procedencia = models.ForeignKey(
        "instituciones.Estacion",
        on_delete=models.PROTECT,
        related_name="despliegues_unidades",
        verbose_name="estación de procedencia",
    )
    despachado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="despliegues_despachados",
        verbose_name="despachado por",
    )
    estado = models.CharField(
        "estado", max_length=15, choices=Estado.choices, default=Estado.ASIGNADA
    )
    fecha_asignacion = models.DateTimeField("fecha de asignación", auto_now_add=True)
    fecha_salida = models.DateTimeField("fecha de salida", null=True, blank=True)
    fecha_llegada = models.DateTimeField("fecha de llegada", null=True, blank=True)
    fecha_retorno = models.DateTimeField("fecha de retorno o finalización", null=True, blank=True)
    observaciones = models.TextField("observaciones", blank=True)

    class Meta:
        verbose_name = "despliegue de unidad"
        verbose_name_plural = "despliegues de unidades"
        ordering = ("-fecha_asignacion", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("unidad",),
                condition=models.Q(estado__in=("asignada", "en_ruta", "en_sitio", "retornando")),
                name="emergencias_unidad_un_despliegue_activo",
            )
        ]

    @property
    def activo(self):
        return self.estado in self.ESTADOS_ACTIVOS

    def __str__(self):
        return f"{self.emergencia.codigo} - {self.unidad.codigo_interno} ({self.get_estado_display()})"
