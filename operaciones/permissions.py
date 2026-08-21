from inventario.permissions import estaciones_permitidas, tiene_alcance_global


GRUPOS_CONSULTA_CAPACIDADES = {
    "Operador de sistemas institucional",
    "Responsable institucional",
    "Responsable de estación",
    "Encargado de inventario",
    "Operador de consulta",
}
GRUPOS_EVALUACION_CAPACIDADES = {
    "Operador de sistemas institucional",
    "Responsable institucional",
    "Responsable de estación",
}


def _grupos(usuario):
    if not usuario.is_authenticated:
        return set()
    return set(usuario.groups.values_list("name", flat=True))


def puede_consultar_capacidades(usuario):
    if tiene_alcance_global(usuario):
        return True
    return bool(
        usuario.is_authenticated
        and usuario.estacion_id
        and _grupos(usuario) & GRUPOS_CONSULTA_CAPACIDADES
    )


def puede_evaluar_capacidades(usuario):
    if tiene_alcance_global(usuario):
        return True
    return bool(
        usuario.is_authenticated
        and usuario.estacion_id
        and _grupos(usuario) & GRUPOS_EVALUACION_CAPACIDADES
    )


def estaciones_capacidades_permitidas(usuario):
    if not puede_consultar_capacidades(usuario):
        return estaciones_permitidas(usuario).none()
    return estaciones_permitidas(usuario)
