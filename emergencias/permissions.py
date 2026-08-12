from inventario.permissions import estaciones_permitidas, tiene_alcance_global


GRUPOS_CONSULTA = {
    "Responsable institucional",
    "Responsable de estación",
    "Encargado de inventario",
    "Operador de consulta",
}
GRUPOS_GESTION = {"Responsable institucional", "Responsable de estación"}


def _grupos(usuario):
    if not usuario.is_authenticated:
        return set()
    return set(usuario.groups.values_list("name", flat=True))


def puede_consultar_emergencias(usuario):
    return tiene_alcance_global(usuario) or bool(
        usuario.is_authenticated and usuario.estacion_id and _grupos(usuario) & GRUPOS_CONSULTA
    )


def puede_gestionar_emergencias(usuario):
    return tiene_alcance_global(usuario) or bool(
        usuario.is_authenticated and usuario.estacion_id and _grupos(usuario) & GRUPOS_GESTION
    )


def estacion_autorizada(usuario, estacion_id):
    return puede_gestionar_emergencias(usuario) and estaciones_permitidas(usuario).filter(
        pk=estacion_id
    ).exists()


def puede_editar_sci(usuario, emergencia):
    """SCI excluye inventario/consulta aunque esos grupos vean emergencias."""
    return puede_gestionar_emergencias(usuario) and estaciones_permitidas(usuario).filter(
        pk=emergencia.estacion_responsable_id
    ).exists()


def puede_consultar_sci(usuario, emergencia):
    return puede_consultar_emergencias(usuario) and estaciones_permitidas(usuario).filter(
        pk=emergencia.estacion_responsable_id
    ).exists()
