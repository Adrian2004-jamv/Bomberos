from instituciones.models import Estacion


GRUPOS_GLOBALES = {"Administrador del sistema", "Responsable provincial"}
GRUPOS_INSTITUCIONALES = {
    "Responsable institucional",
    "Operador de sistemas institucional",
}
GRUPOS_ESTACION_GESTION = {"Responsable de estación", "Encargado de inventario"}
GRUPO_CONSULTA = "Operador de consulta"


def _grupos(usuario):
    if not usuario.is_authenticated:
        return set()
    return set(usuario.groups.values_list("name", flat=True))


def tiene_alcance_global(usuario):
    return usuario.is_authenticated and (
        usuario.is_superuser or bool(_grupos(usuario) & GRUPOS_GLOBALES)
    )


def puede_consultar_inventario(usuario):
    if tiene_alcance_global(usuario):
        return True
    grupos = _grupos(usuario)
    return bool(
        usuario.estacion_id
        and (
            grupos & GRUPOS_INSTITUCIONALES
            or grupos & GRUPOS_ESTACION_GESTION
            or GRUPO_CONSULTA in grupos
        )
    )


def puede_gestionar_inventario(usuario):
    if tiene_alcance_global(usuario):
        return True
    grupos = _grupos(usuario)
    return bool(
        usuario.estacion_id
        and (grupos & GRUPOS_INSTITUCIONALES or grupos & GRUPOS_ESTACION_GESTION)
    )


def estaciones_permitidas(usuario):
    estaciones = Estacion.objects.select_related("cuerpo_bomberos", "cuerpo_bomberos__canton")
    if tiene_alcance_global(usuario):
        return estaciones
    grupos = _grupos(usuario)
    if usuario.estacion_id and grupos & GRUPOS_INSTITUCIONALES:
        return estaciones.filter(
            cuerpo_bomberos_id=usuario.estacion.cuerpo_bomberos_id
        )
    if usuario.estacion_id and (
        grupos & GRUPOS_ESTACION_GESTION or GRUPO_CONSULTA in grupos
    ):
        return estaciones.filter(pk=usuario.estacion_id)
    return estaciones.none()


def recursos_permitidos(usuario):
    from .models import Recurso

    return Recurso.objects.filter(estacion__in=estaciones_permitidas(usuario))


def puede_gestionar_recurso(usuario, recurso):
    return puede_gestionar_inventario(usuario) and estaciones_permitidas(usuario).filter(
        pk=recurso.estacion_id
    ).exists()


def puede_gestionar_catalogos(usuario):
    """Los catálogos son provinciales, no de cada institución.

    Categorías, tipos de recurso y capacidades operativas los comparten todos
    los Cuerpos de Bomberos, y el motor de evaluación compara el inventario de
    cada estación contra ellos. Una estación que inventara tipos propios
    alteraría la medición de las demás, así que solo los edita quien tiene
    alcance sobre toda la provincia.
    """
    return tiene_alcance_global(usuario)
