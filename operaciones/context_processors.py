from .permissions import puede_consultar_capacidades


def acceso_capacidades(request):
    return {
        "puede_consultar_capacidades": puede_consultar_capacidades(request.user),
    }
