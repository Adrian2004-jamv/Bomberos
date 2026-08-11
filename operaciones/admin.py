from django.contrib import admin

from .models import (
    EvaluacionCapacidadEstacion,
    RequisitoRecursoCapacidad,
    TipoCapacidadOperativa,
)


class RequisitoRecursoCapacidadInline(admin.TabularInline):
    model = RequisitoRecursoCapacidad
    extra = 0
    autocomplete_fields = ("tipo_recurso",)
    fields = ("tipo_recurso", "cantidad_minima", "obligatorio", "observaciones")


@admin.register(TipoCapacidadOperativa)
class TipoCapacidadOperativaAdmin(admin.ModelAdmin):
    inlines = (RequisitoRecursoCapacidadInline,)
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
        "observaciones",
        "evaluado_por",
        "fecha_evaluacion",
    )
    fieldsets = (
        ("Evaluación", {"fields": ("estacion", "capacidad", "estado", "porcentaje_cumplimiento")}),
        ("Detalle de recursos", {"fields": ("detalle_recursos",)}),
        ("Auditoría", {"fields": ("observaciones", "evaluado_por", "fecha_evaluacion")}),
    )

    @admin.display(description="Cuerpo de Bomberos", ordering="estacion__cuerpo_bomberos__nombre")
    def mostrar_cuerpo_bomberos(self, obj):
        return obj.estacion.cuerpo_bomberos

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
