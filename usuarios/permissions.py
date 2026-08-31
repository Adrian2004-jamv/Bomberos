from django.contrib.auth import get_user_model

from instituciones.models import Estacion

GRUPO_SISTEMAS_INSTITUCIONAL = "Operador de sistemas institucional"
GRUPOS_CREABLES_INSTITUCION = (
    "Responsable institucional",
    "Responsable de estación",
    "Encargado de inventario",
    "Operador de consulta",
    # Conduce una unidad. Su cuenta solo alcanza el despliegue que se le asigne
    # en el SCI-211, de modo que puede crearla cualquier gestor de la
    # institución sin ampliar el acceso de nadie.
    "Chofer de unidad",
)

def es_operador_sistemas(usuario):
    return bool(
        usuario.is_authenticated
        and usuario.groups.filter(name=GRUPO_SISTEMAS_INSTITUCIONAL).exists()
    )

def puede_gestionar_usuarios(usuario):
    return bool(usuario.is_authenticated and (usuario.is_superuser or es_operador_sistemas(usuario)))

def estaciones_asignables(usuario):
    estaciones = Estacion.objects.select_related("cuerpo_bomberos", "cuerpo_bomberos__canton")
    if usuario.is_superuser:
        return estaciones
    if es_operador_sistemas(usuario) and usuario.estacion_id:
        return estaciones.filter(cuerpo_bomberos_id=usuario.estacion.cuerpo_bomberos_id)
    return estaciones.none()

def usuarios_administrables(usuario):
    Usuario = get_user_model()
    base = Usuario.objects.filter(is_superuser=False).select_related(
        "estacion", "estacion__cuerpo_bomberos", "estacion__cuerpo_bomberos__canton"
    ).prefetch_related("groups")
    if usuario.is_superuser:
        return base
    if es_operador_sistemas(usuario) and usuario.estacion_id:
        return base.filter(estacion__cuerpo_bomberos_id=usuario.estacion.cuerpo_bomberos_id)
    return base.none()
