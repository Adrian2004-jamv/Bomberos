from django.conf import settings
from django.contrib.gis.db import models as gis_models
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
    ubicacion = gis_models.PointField(
        "ubicación", srid=4326, spatial_index=True,
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
            models.CheckConstraint(condition=models.Q(precision__isnull=True) | models.Q(precision__gte=0), name="pos_precision_valida"),
            models.CheckConstraint(condition=models.Q(velocidad__isnull=True) | models.Q(velocidad__gte=0), name="pos_velocidad_valida"),
            models.CheckConstraint(condition=models.Q(rumbo__isnull=True) | models.Q(rumbo__gte=0, rumbo__lte=360), name="pos_rumbo_valido"),
        ]

    @property
    def latitud(self):
        return self.ubicacion.y

    @property
    def longitud(self):
        return self.ubicacion.x

    def clean(self):
        super().clean()
        errores = {}
        if self.ubicacion:
            if not -90 <= self.ubicacion.y <= 90:
                errores["ubicacion"] = "La latitud debe estar entre -90 y 90."
            if not -180 <= self.ubicacion.x <= 180:
                errores["ubicacion"] = "La longitud debe estar entre -180 y 180."
            if self.ubicacion.srid != 4326:
                errores["ubicacion"] = "La ubicación debe utilizar SRID 4326."
        if errores:
            raise ValidationError(errores)

    def __str__(self):
        return f"{self.despliegue} @ {self.fecha_recepcion:%Y-%m-%d %H:%M:%S}"


class FormularioSCI211(models.Model):
    """Encabezado único del Registro y Control de Recursos de una emergencia."""

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        FINALIZADO = "finalizado", "Finalizado"

    emergencia = models.OneToOneField(
        Emergencia, on_delete=models.PROTECT, related_name="formulario_sci_211",
        verbose_name="emergencia",
    )
    codigo = models.CharField("número del formulario", max_length=40, unique=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.BORRADOR)
    punto_registro = models.CharField(
        "punto de registro", max_length=150,
        help_text="Ejemplo: Puesto de Comando, Base, Helibase o Área de Espera.",
    )
    registrador_1 = models.CharField("nombre del registrador 1", max_length=150)
    registrador_2 = models.CharField("nombre del registrador 2", max_length=150, blank=True)
    registrador_3 = models.CharField("nombre del registrador 3", max_length=150, blank=True)
    emergencia_codigo_emitido = models.CharField(max_length=30, blank=True, editable=False)
    incidente_nombre_emitido = models.CharField(max_length=120, blank=True, editable=False)
    incidente_fecha_emitida = models.DateTimeField(null=True, blank=True, editable=False)
    incidente_direccion_emitida = models.CharField(max_length=255, blank=True, editable=False)
    institucion_emitida = models.CharField(max_length=150, blank=True, editable=False)
    estacion_emitida = models.CharField(max_length=150, blank=True, editable=False)
    coordenadas_emitidas = models.CharField(max_length=50, blank=True, editable=False)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sci211_creados",
        editable=False,
    )
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sci211_modificados",
        editable=False,
    )
    finalizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sci211_finalizados",
        null=True, blank=True, editable=False,
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    fecha_finalizacion = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "formulario SCI-211"
        verbose_name_plural = "formularios SCI-211"
        ordering = ("-fecha_creacion",)

    def __str__(self):
        return f"{self.codigo} - {self.emergencia.codigo}"

    @property
    def es_editable(self):
        return self.estado == self.Estado.BORRADOR


class RegistroRecursoSCI211(models.Model):
    class EstadoRecurso(models.TextChoices):
        DISPONIBLE = "disponible", "Disponible"
        NO_DISPONIBLE = "no_disponible", "No disponible"
        FUERA_SERVICIO = "fuera_servicio", "Fuera de servicio"

    formulario = models.ForeignKey(
        FormularioSCI211, on_delete=models.CASCADE, related_name="registros",
        verbose_name="formulario SCI-211",
    )
    despliegue = models.ForeignKey(
        DespliegueUnidad, on_delete=models.PROTECT, related_name="registros_sci211",
        null=True, blank=True, verbose_name="despliegue de origen",
    )
    solicitado_por = models.CharField("solicitado por", max_length=150)
    fecha_hora_solicitud = models.DateTimeField("fecha y hora de solicitud")
    clase_recurso = models.CharField("clase de recurso", max_length=120)
    tipo_recurso = models.CharField("tipo de recurso", max_length=120, blank=True)
    fecha_hora_arribo = models.DateTimeField("fecha y hora de arribo", null=True, blank=True)
    institucion_procedencia = models.CharField("institución de procedencia", max_length=150)
    matricula_identificacion = models.CharField("matrícula o identificación", max_length=80)
    numero_personas = models.PositiveSmallIntegerField("número de personas", default=1)
    estado_recurso = models.CharField(max_length=20, choices=EstadoRecurso.choices)
    asignado_a = models.CharField(
        "asignado a", max_length=180, blank=True,
        help_text="Ubicación geográfica o asignación actual del recurso.",
    )
    desmovilizado_por = models.CharField("desmovilización autorizada por", max_length=150, blank=True)
    fecha_hora_desmovilizacion = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(max_length=1500, blank=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "registro de recurso SCI-211"
        verbose_name_plural = "registros de recursos SCI-211"
        ordering = ("orden", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("formulario", "despliegue"),
                condition=models.Q(despliegue__isnull=False),
                name="sci211_despliegue_unico_por_formulario",
            )
        ]

    def clean(self):
        super().clean()
        errores = {}
        if self.fecha_hora_arribo and self.fecha_hora_arribo < self.fecha_hora_solicitud:
            errores["fecha_hora_arribo"] = "El arribo no puede ser anterior a la solicitud."
        if bool(self.desmovilizado_por) != bool(self.fecha_hora_desmovilizacion):
            errores["desmovilizado_por"] = "Indique responsable y fecha de desmovilización juntos."
        if self.estado_recurso == self.EstadoRecurso.DISPONIBLE and not self.asignado_a:
            errores["asignado_a"] = "Indique dónde está asignado el recurso disponible."
        if errores:
            raise ValidationError(errores)
