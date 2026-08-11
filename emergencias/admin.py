from django.contrib import admin

from .models import DespliegueUnidad, Emergencia, PosicionUnidad


class DespliegueUnidadInline(admin.TabularInline):
    model = DespliegueUnidad
    extra = 0
    can_delete = False
    fields = (
        "unidad",
        "estacion_procedencia",
        "estado",
        "fecha_asignacion",
        "fecha_salida",
        "fecha_llegada",
        "fecha_retorno",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Emergencia)
class EmergenciaAdmin(admin.ModelAdmin):
    inlines = (DespliegueUnidadInline,)
    list_display = (
        "codigo",
        "tipo_emergencia",
        "prioridad",
        "estado",
        "estacion_responsable",
        "fecha_reporte",
    )
    list_filter = (
        "estado",
        "prioridad",
        "estacion_responsable__cuerpo_bomberos",
        "estacion_responsable",
        "fecha_reporte",
    )
    search_fields = (
        "codigo",
        "tipo_emergencia",
        "descripcion",
        "direccion",
        "estacion_responsable__nombre",
        "estacion_responsable__cuerpo_bomberos__nombre",
        "registrado_por__username",
    )
    list_select_related = (
        "estacion_responsable",
        "estacion_responsable__cuerpo_bomberos",
        "registrado_por",
    )
    readonly_fields = ("fecha_creacion", "fecha_actualizacion")
    fieldsets = (
        ("Identificación", {"fields": ("codigo", "tipo_emergencia", "prioridad")}),
        ("Situación", {"fields": ("descripcion", "direccion", "latitud", "longitud")}),
        ("Responsabilidad", {"fields": ("estacion_responsable", "registrado_por")}),
        ("Estado e historial", {"fields": ("estado", "fecha_reporte", "fecha_cierre")}),
        ("Auditoría", {"fields": ("fecha_creacion", "fecha_actualizacion")}),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + (
                "codigo",
                "estacion_responsable",
                "registrado_por",
                "estado",
                "fecha_reporte",
                "fecha_cierre",
            )
        return self.readonly_fields


@admin.register(DespliegueUnidad)
class DespliegueUnidadAdmin(admin.ModelAdmin):
    list_display = (
        "emergencia",
        "unidad",
        "estacion_procedencia",
        "estado",
        "despachado_por",
        "fecha_asignacion",
    )
    list_filter = (
        "estado",
        "estacion_procedencia__cuerpo_bomberos",
        "estacion_procedencia",
        "fecha_asignacion",
    )
    search_fields = (
        "emergencia__codigo",
        "unidad__codigo_interno",
        "unidad__nombre",
        "estacion_procedencia__nombre",
        "despachado_por__username",
    )
    list_select_related = (
        "emergencia",
        "unidad",
        "estacion_procedencia",
        "estacion_procedencia__cuerpo_bomberos",
        "despachado_por",
    )
    readonly_fields = (
        "emergencia",
        "unidad",
        "estacion_procedencia",
        "despachado_por",
        "estado",
        "fecha_asignacion",
        "fecha_salida",
        "fecha_llegada",
        "fecha_retorno",
        "observaciones",
    )
    fields = readonly_fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PosicionUnidad)
class PosicionUnidadAdmin(admin.ModelAdmin):
    list_display = ("despliegue", "latitud", "longitud", "precision", "reportado_por", "fecha_recepcion")
    list_filter = ("fuente", "fecha_recepcion", "despliegue__estacion_procedencia")
    search_fields = ("despliegue__emergencia__codigo", "despliegue__unidad__codigo_interno", "reportado_por__username")
    list_select_related = ("despliegue", "despliegue__emergencia", "despliegue__unidad", "reportado_por")
    readonly_fields = (
        "despliegue", "latitud", "longitud", "precision", "velocidad", "rumbo",
        "altitud", "fecha_dispositivo", "fecha_recepcion", "reportado_por", "fuente",
    )
    fields = readonly_fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
