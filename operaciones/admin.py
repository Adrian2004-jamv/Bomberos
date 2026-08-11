from django.contrib import admin

from .models import (
    CalificacionPersonal,
    EvaluacionCapacidadEstacion,
    EspecialidadOperativa,
    PersonalOperativo,
    RequisitoPersonalCapacidad,
    RequisitoRecursoCapacidad,
    TipoCapacidadOperativa,
)


class CalificacionPersonalInline(admin.TabularInline):
    model = CalificacionPersonal
    extra = 0
    autocomplete_fields = ("especialidad", "verificado_por")
    fields = (
        "especialidad",
        "nivel",
        "numero_certificado",
        "fecha_emision",
        "fecha_vencimiento",
        "activo",
        "mostrar_vigente",
        "verificado_por",
    )
    readonly_fields = ("mostrar_vigente",)

    @admin.display(description="vigente", boolean=True)
    def mostrar_vigente(self, obj):
        return obj.vigente if obj.pk else None


class RequisitoRecursoCapacidadInline(admin.TabularInline):
    model = RequisitoRecursoCapacidad
    extra = 0
    autocomplete_fields = ("tipo_recurso",)
    fields = ("tipo_recurso", "cantidad_minima", "obligatorio", "observaciones")


class RequisitoPersonalCapacidadInline(admin.TabularInline):
    model = RequisitoPersonalCapacidad
    extra = 0
    autocomplete_fields = ("especialidad",)
    fields = (
        "especialidad",
        "nivel_minimo",
        "cantidad_minima",
        "obligatorio",
        "observaciones",
    )


@admin.register(PersonalOperativo)
class PersonalOperativoAdmin(admin.ModelAdmin):
    inlines = (CalificacionPersonalInline,)
    list_display = (
        "mostrar_nombre_completo",
        "codigo_institucional",
        "estacion",
        "mostrar_cuerpo_bomberos",
        "rango",
        "cargo_operativo",
        "disponibilidad",
        "activo",
    )
    search_fields = (
        "codigo_institucional",
        "cedula",
        "nombres",
        "apellidos",
        "rango",
        "cargo_operativo",
        "estacion__nombre",
        "estacion__codigo",
        "estacion__cuerpo_bomberos__nombre",
        "estacion__cuerpo_bomberos__sigla",
        "usuario__username",
    )
    list_filter = (
        "disponibilidad",
        "activo",
        "estacion__cuerpo_bomberos__canton",
        "estacion__cuerpo_bomberos",
        "estacion",
        "rango",
    )
    list_select_related = (
        "estacion",
        "estacion__cuerpo_bomberos",
        "usuario",
    )
    readonly_fields = ("fecha_creacion", "fecha_actualizacion")
    fieldsets = (
        (
            "Identificación",
            {"fields": ("codigo_institucional", "cedula", "nombres", "apellidos", "activo")},
        ),
        ("Ubicación y acceso", {"fields": ("estacion", "usuario")}),
        ("Información operativa", {"fields": ("rango", "cargo_operativo", "fecha_ingreso", "disponibilidad")}),
        ("Contacto y observaciones", {"fields": ("telefono", "observaciones")}),
        ("Auditoría", {"fields": ("fecha_creacion", "fecha_actualizacion")}),
    )

    @admin.display(description="nombre completo", ordering="apellidos")
    def mostrar_nombre_completo(self, obj):
        return obj.nombre_completo

    @admin.display(description="Cuerpo de Bomberos", ordering="estacion__cuerpo_bomberos__nombre")
    def mostrar_cuerpo_bomberos(self, obj):
        return obj.institucion


@admin.register(EspecialidadOperativa)
class EspecialidadOperativaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "activo", "fecha_actualizacion")
    search_fields = ("nombre", "codigo", "descripcion")
    list_filter = ("activo",)
    readonly_fields = ("fecha_creacion", "fecha_actualizacion")
    fieldsets = (
        ("Identificación", {"fields": ("nombre", "codigo", "activo")}),
        ("Descripción", {"fields": ("descripcion",)}),
        ("Auditoría", {"fields": ("fecha_creacion", "fecha_actualizacion")}),
    )


@admin.register(CalificacionPersonal)
class CalificacionPersonalAdmin(admin.ModelAdmin):
    list_display = (
        "personal",
        "especialidad",
        "nivel",
        "mostrar_estacion",
        "entidad_emisora",
        "fecha_vencimiento",
        "mostrar_vigente",
        "activo",
    )
    search_fields = (
        "personal__codigo_institucional",
        "personal__cedula",
        "personal__nombres",
        "personal__apellidos",
        "personal__estacion__nombre",
        "personal__estacion__codigo",
        "especialidad__nombre",
        "especialidad__codigo",
        "numero_certificado",
        "entidad_emisora",
        "verificado_por__username",
    )
    list_filter = (
        "nivel",
        "activo",
        "especialidad",
        "personal__estacion__cuerpo_bomberos",
        "personal__estacion",
        "entidad_emisora",
        "fecha_vencimiento",
    )
    list_select_related = (
        "personal",
        "personal__estacion",
        "personal__estacion__cuerpo_bomberos",
        "especialidad",
        "verificado_por",
    )
    readonly_fields = ("mostrar_vigente", "fecha_creacion", "fecha_actualizacion")
    autocomplete_fields = ("personal", "especialidad", "verificado_por")
    fieldsets = (
        ("Personal y especialidad", {"fields": ("personal", "especialidad", "nivel", "activo")}),
        (
            "Certificación",
            {
                "fields": (
                    "numero_certificado",
                    "entidad_emisora",
                    "fecha_emision",
                    "fecha_vencimiento",
                    "mostrar_vigente",
                )
            },
        ),
        ("Verificación", {"fields": ("verificado_por", "observaciones")}),
        ("Auditoría", {"fields": ("fecha_creacion", "fecha_actualizacion")}),
    )

    @admin.display(description="estación", ordering="personal__estacion__nombre")
    def mostrar_estacion(self, obj):
        return obj.personal.estacion

    @admin.display(description="vigente", boolean=True)
    def mostrar_vigente(self, obj):
        return obj.vigente


@admin.register(TipoCapacidadOperativa)
class TipoCapacidadOperativaAdmin(admin.ModelAdmin):
    inlines = (RequisitoRecursoCapacidadInline, RequisitoPersonalCapacidadInline)
    list_display = ("nombre", "codigo", "activo", "fecha_actualizacion")
    search_fields = ("nombre", "codigo", "descripcion")
    list_filter = ("activo",)
    readonly_fields = ("fecha_creacion", "fecha_actualizacion")
    fieldsets = (
        ("Identificación", {"fields": ("nombre", "codigo", "activo")}),
        ("Descripción", {"fields": ("descripcion",)}),
        ("Auditoría", {"fields": ("fecha_creacion", "fecha_actualizacion")}),
    )


@admin.register(EvaluacionCapacidadEstacion)
class EvaluacionCapacidadEstacionAdmin(admin.ModelAdmin):
    list_display = (
        "estacion",
        "mostrar_cuerpo_bomberos",
        "capacidad",
        "estado",
        "porcentaje_cumplimiento",
        "evaluado_por",
        "fecha_evaluacion",
    )
    search_fields = (
        "estacion__nombre",
        "estacion__codigo",
        "estacion__cuerpo_bomberos__nombre",
        "estacion__cuerpo_bomberos__sigla",
        "capacidad__nombre",
        "capacidad__codigo",
        "evaluado_por__username",
        "evaluado_por__first_name",
        "evaluado_por__last_name",
    )
    list_filter = (
        "estado",
        "capacidad",
        "estacion__cuerpo_bomberos",
        "estacion",
        "fecha_evaluacion",
    )
    list_select_related = (
        "estacion",
        "estacion__cuerpo_bomberos",
        "capacidad",
        "evaluado_por",
    )
    readonly_fields = (
        "estacion",
        "capacidad",
        "estado",
        "porcentaje_cumplimiento",
        "detalle_recursos",
        "detalle_personal",
        "observaciones",
        "evaluado_por",
        "fecha_evaluacion",
    )
    fieldsets = (
        ("Evaluación", {"fields": ("estacion", "capacidad", "estado", "porcentaje_cumplimiento")}),
        ("Detalles", {"fields": ("detalle_recursos", "detalle_personal")}),
        ("Auditoría", {"fields": ("observaciones", "evaluado_por", "fecha_evaluacion")}),
    )

    @admin.display(description="Cuerpo de Bomberos", ordering="estacion__cuerpo_bomberos__nombre")
    def mostrar_cuerpo_bomberos(self, obj):
        return obj.estacion.cuerpo_bomberos

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
