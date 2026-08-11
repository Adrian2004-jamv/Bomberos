from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Información institucional",
            {
                "fields": (
                    "estacion",
                    "cedula",
                    "telefono",
                    "cargo_institucional",
                    "debe_cambiar_clave",
                    "fecha_actualizacion",
                )
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Información institucional",
            {
                "fields": (
                    "estacion",
                    "cedula",
                    "telefono",
                    "cargo_institucional",
                    "debe_cambiar_clave",
                )
            },
        ),
    )
    readonly_fields = ("fecha_actualizacion",)
    list_display = (
        "username",
        "cedula",
        "first_name",
        "last_name",
        "cargo_institucional",
        "estacion",
        "is_staff",
        "is_active",
    )
    list_filter = ("estacion", "groups", "is_staff", "is_active")
    list_select_related = ("estacion",)
    search_fields = (
        "username",
        "cedula",
        "first_name",
        "last_name",
        "email",
        "estacion__nombre",
        "estacion__codigo",
    )
