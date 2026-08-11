GRUPOS_GESTION_INSTITUCIONAL = {
    "Administrador del sistema",
    "Responsable provincial",
}


def puede_gestionar_instituciones(usuario):
    if not usuario.is_authenticated:
        return False
    if usuario.is_superuser:
        return True
    return usuario.groups.filter(name__in=GRUPOS_GESTION_INSTITUCIONAL).exists()
