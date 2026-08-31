from django.contrib import admin

from .models import CategoriaRecurso, HistorialEstadoRecurso, Recurso, TipoRecurso

@admin.register(CategoriaRecurso)
class CategoriaRecursoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "activo", "fecha_actualizacion")
    search_fields = ("nombre", "codigo", "descripcion")
    list_filter = ("activo",)
    readonly_fields = ("fecha_creacion", "fecha_actualizacion")
    fieldsets = (
        ("Identificación", {"fields": ("nombre", "codigo", "activo")}),
        ("Descripción", {"fields": ("descripcion",)}),
        ("Auditoría", {"fields": ("fecha_creacion", "fecha_actualizacion")}),
    )

@admin.register(TipoRecurso)
class TipoRecursoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "categoria", "es_unidad_desplegable", "activo", "fecha_actualizacion")
    search_fields = ("nombre", "codigo", "descripcion", "categoria__nombre", "categoria__codigo")
    list_filter = ("activo", "es_unidad_desplegable", "categoria")
    list_select_related = ("categoria",)
    readonly_fields = ("fecha_creacion", "fecha_actualizacion")
    fieldsets = (
        ("Clasificación", {"fields": ("categoria", "nombre", "codigo", "es_unidad_desplegable", "activo")}),
        ("Descripción", {"fields": ("descripcion",)}),
        ("Auditoría", {"fields": ("fecha_creacion", "fecha_actualizacion")}),
    )

@admin.register(Recurso)
class RecursoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo_interno",
        "nombre",
        "tipo",
        "estacion",
        "estado_operativo",
        "disponibilidad",
        "fecha_confirmacion_disponibilidad",
        "activo",
    )
    search_fields = (
        "codigo_interno",
        "nombre",
        "marca",
        "modelo",
        "numero_serie",
        "estacion__nombre",
        "estacion__codigo",
        "estacion__cuerpo_bomberos__nombre",
        "estacion__cuerpo_bomberos__sigla",
    )
    list_filter = (
        "estado_operativo",
        "disponibilidad",
        "activo",
        "estacion__cuerpo_bomberos__canton",
        "estacion__cuerpo_bomberos",
        "estacion",
        "tipo__categoria",
    )
    list_select_related = (
        "estacion",
        "estacion__cuerpo_bomberos",
        "tipo",
        "tipo__categoria",
    )
    readonly_fields = ("fecha_creacion", "fecha_actualizacion", "fecha_confirmacion_disponibilidad")
    fieldsets = (
        (
            "Identificación y clasificación",
            {"fields": ("estacion", "tipo", "codigo_interno", "nombre", "activo")},
        ),
        ("Descripción", {"fields": ("descripcion", "marca", "modelo", "numero_serie", "anio_fabricacion")}),
        ("Estado", {"fields": ("estado_operativo", "disponibilidad")}),
        ("Observaciones", {"fields": ("observaciones",)}),
        ("Auditoría", {"fields": ("fecha_confirmacion_disponibilidad", "fecha_creacion", "fecha_actualizacion")}),
    )

@admin.register(HistorialEstadoRecurso)
class HistorialEstadoRecursoAdmin(admin.ModelAdmin):
    list_display = (
        "recurso",
        "estado_anterior",
        "estado_nuevo",
        "disponibilidad_anterior",
        "disponibilidad_nueva",
        "registrado_por",
        "fecha_registro",
    )
    list_filter = (
        "estado_anterior",
        "estado_nuevo",
        "disponibilidad_anterior",
        "disponibilidad_nueva",
        "fecha_registro",
    )
    search_fields = (
        "recurso__codigo_interno",
        "recurso__nombre",
        "motivo",
        "observaciones",
        "registrado_por__username",
        "registrado_por__cedula",
        "registrado_por__first_name",
        "registrado_por__last_name",
    )
    list_select_related = ("recurso", "registrado_por")
    readonly_fields = (
        "recurso",
        "estado_anterior",
        "estado_nuevo",
        "disponibilidad_anterior",
        "disponibilidad_nueva",
        "motivo",
        "observaciones",
        "registrado_por",
        "fecha_registro",
    )
    fieldsets = (
        ("Recurso y responsable", {"fields": ("recurso", "registrado_por", "fecha_registro")}),
        (
            "Cambio registrado",
            {
                "fields": (
                    "estado_anterior",
                    "estado_nuevo",
                    "disponibilidad_anterior",
                    "disponibilidad_nueva",
                )
            },
        ),
        ("Justificación", {"fields": ("motivo", "observaciones")}),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
