from django.contrib import admin

from .models import PersonalOperativo


@admin.register(PersonalOperativo)
class PersonalOperativoAdmin(admin.ModelAdmin):
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
