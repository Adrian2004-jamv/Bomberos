from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


def validar_fecha_no_futura(value):
    if value > timezone.localdate():
        raise ValidationError("La fecha de ingreso no puede estar en el futuro.")


class EspecialidadOperativa(models.Model):
    nombre = models.CharField("nombre", max_length=150)
    codigo = models.CharField("código", max_length=30, unique=True)
    descripcion = models.TextField("descripción", blank=True)
    activo = models.BooleanField("activo", default=True)
    fecha_creacion = models.DateTimeField("fecha de creación", auto_now_add=True)
    fecha_actualizacion = models.DateTimeField("fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "especialidad operativa"
        verbose_name_plural = "especialidades operativas"
        ordering = ("nombre",)

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


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
    especialidades = models.ManyToManyField(
        EspecialidadOperativa,
        through="CalificacionPersonal",
        related_name="personal_calificado",
        verbose_name="especialidades",
        blank=True,
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


class CalificacionPersonal(models.Model):
    class Nivel(models.TextChoices):
        BASICO = "basico", "Básico"
        INTERMEDIO = "intermedio", "Intermedio"
        AVANZADO = "avanzado", "Avanzado"
        INSTRUCTOR = "instructor", "Instructor"

    personal = models.ForeignKey(
        PersonalOperativo,
        on_delete=models.PROTECT,
        related_name="calificaciones",
        verbose_name="personal operativo",
    )
    especialidad = models.ForeignKey(
        EspecialidadOperativa,
        on_delete=models.PROTECT,
        related_name="calificaciones_personal",
        verbose_name="especialidad",
    )
    nivel = models.CharField(
        "nivel",
        max_length=15,
        choices=Nivel.choices,
        default=Nivel.BASICO,
    )
    numero_certificado = models.CharField("número de certificado", max_length=100, blank=True)
    entidad_emisora = models.CharField("entidad emisora", max_length=150, blank=True)
    fecha_emision = models.DateField("fecha de emisión")
    fecha_vencimiento = models.DateField("fecha de vencimiento", null=True, blank=True)
    verificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="calificaciones_verificadas",
        verbose_name="verificado por",
        null=True,
        blank=True,
    )
    observaciones = models.TextField("observaciones", blank=True)
    activo = models.BooleanField("activo", default=True)
    fecha_creacion = models.DateTimeField("fecha de creación", auto_now_add=True)
    fecha_actualizacion = models.DateTimeField("fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "calificación del personal"
        verbose_name_plural = "calificaciones del personal"
        ordering = ("personal__apellidos", "personal__nombres", "especialidad__nombre")
        constraints = [
            models.UniqueConstraint(
                fields=("personal", "especialidad"),
                name="operaciones_calificacion_especialidad_unica_por_personal",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(fecha_vencimiento__isnull=True)
                    | models.Q(fecha_vencimiento__gte=models.F("fecha_emision"))
                ),
                name="operaciones_calificacion_vencimiento_valido",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.fecha_vencimiento is not None
            and self.fecha_emision is not None
            and self.fecha_vencimiento < self.fecha_emision
        ):
            raise ValidationError(
                {"fecha_vencimiento": "La fecha de vencimiento no puede ser anterior a la fecha de emisión."}
            )

    @property
    def vigente(self):
        if not self.activo:
            return False
        if self.fecha_vencimiento is None:
            return True
        return self.fecha_vencimiento >= timezone.localdate()

    def __str__(self):
        return f"{self.personal.nombre_completo} - {self.especialidad.nombre} ({self.get_nivel_display()})"


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


class RequisitoPersonalCapacidad(models.Model):
    capacidad = models.ForeignKey(
        TipoCapacidadOperativa,
        on_delete=models.PROTECT,
        related_name="requisitos_personal",
        verbose_name="capacidad operativa",
    )
    especialidad = models.ForeignKey(
        EspecialidadOperativa,
        on_delete=models.PROTECT,
        related_name="requisitos_capacidades",
        verbose_name="especialidad operativa",
    )
    nivel_minimo = models.CharField(
        "nivel mínimo",
        max_length=15,
        choices=CalificacionPersonal.Nivel.choices,
        default=CalificacionPersonal.Nivel.BASICO,
    )
    cantidad_minima = models.PositiveIntegerField(
        "cantidad mínima",
        validators=[MinValueValidator(1)],
    )
    obligatorio = models.BooleanField("obligatorio", default=True)
    observaciones = models.TextField("observaciones", blank=True)

    class Meta:
        verbose_name = "requisito de personal para capacidad"
        verbose_name_plural = "requisitos de personal para capacidades"
        ordering = ("capacidad__nombre", "especialidad__nombre", "nivel_minimo")
        constraints = [
            models.UniqueConstraint(
                fields=("capacidad", "especialidad", "nivel_minimo"),
                name="operaciones_requisito_personal_unico_por_capacidad",
            ),
            models.CheckConstraint(
                condition=models.Q(cantidad_minima__gte=1),
                name="operaciones_requisito_personal_cantidad_positiva",
            ),
        ]

    def __str__(self):
        return (
            f"{self.capacidad.nombre}: {self.cantidad_minima} × "
            f"{self.especialidad.nombre} ({self.get_nivel_minimo_display()})"
        )
