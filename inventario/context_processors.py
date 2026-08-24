from .permissions import puede_gestionar_catalogos


def acceso_catalogos(request):
    return {"puede_gestionar_catalogos": puede_gestionar_catalogos(request.user)}
