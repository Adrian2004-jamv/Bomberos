from .permissions import puede_gestionar_usuarios

def acceso_usuarios(request):
    return {"puede_gestionar_usuarios": puede_gestionar_usuarios(request.user)}
