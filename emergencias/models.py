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


class PosicionUnidad(models.Model):
    class Fuente(models.TextChoices):
        NAVEGADOR = "navegador", "Navegador web"

    despliegue = models.ForeignKey(
        DespliegueUnidad,
        on_delete=models.CASCADE,
        related_name="posiciones",
        verbose_name="despliegue",
    )
    latitud = models.DecimalField(
        "latitud", max_digits=9, decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitud = models.DecimalField(
        "longitud", max_digits=10, decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    precision = models.DecimalField(
        "precisión horizontal (m)", max_digits=9, decimal_places=2,
        null=True, blank=True, validators=[MinValueValidator(0)],
    )
    velocidad = models.DecimalField(
        "velocidad (m/s)", max_digits=9, decimal_places=3,
        null=True, blank=True, validators=[MinValueValidator(0)],
    )
    rumbo = models.DecimalField(
        "rumbo (grados)", max_digits=6, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(360)],
    )
    altitud = models.DecimalField(
        "altitud (m)", max_digits=10, decimal_places=2, null=True, blank=True,
    )
    fecha_dispositivo = models.DateTimeField("fecha del dispositivo", null=True, blank=True)
    fecha_recepcion = models.DateTimeField("fecha de recepción", auto_now_add=True)
    reportado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="posiciones_unidades_reportadas",
        verbose_name="reportado por",
    )
    fuente = models.CharField(
        "fuente", max_length=20, choices=Fuente.choices, default=Fuente.NAVEGADOR,
    )

    class Meta:
        verbose_name = "posición de unidad"
        verbose_name_plural = "posiciones de unidades"
        ordering = ("-fecha_recepcion", "-pk")
        indexes = [
            models.Index(fields=("despliegue", "-fecha_recepcion"), name="pos_despl_fecha_idx"),
            models.Index(fields=("-fecha_recepcion",), name="pos_fecha_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(latitud__gte=-90, latitud__lte=90), name="pos_latitud_valida"),
            models.CheckConstraint(condition=models.Q(longitud__gte=-180, longitud__lte=180), name="pos_longitud_valida"),
            models.CheckConstraint(condition=models.Q(precision__isnull=True) | models.Q(precision__gte=0), name="pos_precision_valida"),
            models.CheckConstraint(condition=models.Q(velocidad__isnull=True) | models.Q(velocidad__gte=0), name="pos_velocidad_valida"),
            models.CheckConstraint(condition=models.Q(rumbo__isnull=True) | models.Q(rumbo__gte=0, rumbo__lte=360), name="pos_rumbo_valido"),
        ]

    def __str__(self):
        return f"{self.despliegue} @ {self.fecha_recepcion:%Y-%m-%d %H:%M:%S}"
