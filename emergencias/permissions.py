from inventario.permissions import estaciones_permitidas, tiene_alcance_global

GRUPOS_CONSULTA = {
    "Operador de sistemas institucional",
    "Responsable institucional",
    "Responsable de estación",
    "Encargado de inventario",
    "Operador de consulta",
}
GRUPOS_GESTION = {
    "Responsable institucional",
    "Responsable de estación",
    "Operador de sistemas institucional",
}

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

# ==========================================
# MÓDULO: CHOFER DE UNIDAD
# ==========================================

# El chofer no entra por estaciones_permitidas, que concede la estación entera.
# Su alcance es una sola fila: el despliegue que conduce. Por eso vive en su
# propio eje de permisos y no como un grupo más en las listas de arriba.
GRUPO_CHOFER = "Chofer de unidad"

def es_chofer(usuario):
    return bool(usuario.is_authenticated and GRUPO_CHOFER in _grupos(usuario))

def solo_es_chofer(usuario):
    """El perfil no tiene ningún otro rol operativo.

    Un jefe de estación que además conduzca conserva sus permisos; quien solo
    es chofer ve únicamente su unidad.
    """
    if not es_chofer(usuario):
        return False
    return not (_grupos(usuario) & (GRUPOS_CONSULTA | GRUPOS_GESTION))

def despliegues_asignados(usuario):
    """Despliegues activos que el usuario conduce."""
    from .models import DespliegueUnidad

    if not usuario.is_authenticated:
        return DespliegueUnidad.objects.none()
    return DespliegueUnidad.objects.filter(
        responsable_unidad=usuario,
        estado__in=DespliegueUnidad.ESTADOS_ACTIVOS,
    ).select_related("unidad", "emergencia", "emergencia__estacion_responsable")

def conduce_el_despliegue(usuario, despliegue):
    return bool(
        usuario.is_authenticated
        and despliegue.responsable_unidad_id == usuario.pk
    )
