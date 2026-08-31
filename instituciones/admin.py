from django.contrib import admin

from .models import Canton, CuerpoBomberos, Estacion

@admin.register(Canton)
class CantonAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "activo", "fecha_actualizacion")
    search_fields = ("nombre", "codigo")
    list_filter = ("activo",)
    readonly_fields = ("fecha_creacion", "fecha_actualizacion")
    fieldsets = (
        ("Identificación", {"fields": ("nombre", "codigo", "activo")}),
        ("Auditoría", {"fields": ("fecha_creacion", "fecha_actualizacion")}),
    )

@admin.register(CuerpoBomberos)
class CuerpoBomberosAdmin(admin.ModelAdmin):
    list_display = ("nombre", "sigla", "canton", "ruc", "telefono", "activo")
    search_fields = ("nombre", "sigla", "ruc", "canton__nombre")
    list_filter = ("activo", "canton")
    list_select_related = ("canton",)
    readonly_fields = ("fecha_creacion", "fecha_actualizacion")
    fieldsets = (
        ("Identificación", {"fields": ("canton", "nombre", "sigla", "ruc", "activo")}),
        ("Contacto", {"fields": ("direccion", "telefono", "correo", "sitio_web")}),
        ("Auditoría", {"fields": ("fecha_creacion", "fecha_actualizacion")}),
    )

@admin.register(Estacion)
class EstacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "cuerpo_bomberos", "telefono", "activo")
    search_fields = (
        "nombre",
        "codigo",
        "cuerpo_bomberos__nombre",
        "cuerpo_bomberos__sigla",
    )
    list_filter = ("activo", "cuerpo_bomberos__canton", "cuerpo_bomberos")
    list_select_related = ("cuerpo_bomberos", "cuerpo_bomberos__canton")
    readonly_fields = ("fecha_creacion", "fecha_actualizacion")
    fieldsets = (
        ("Identificación", {"fields": ("cuerpo_bomberos", "nombre", "codigo", "activo")}),
        ("Contacto", {"fields": ("direccion", "telefono")}),
        ("Ubicación", {"fields": ("latitud", "longitud")}),
        ("Auditoría", {"fields": ("fecha_creacion", "fecha_actualizacion")}),
    )
