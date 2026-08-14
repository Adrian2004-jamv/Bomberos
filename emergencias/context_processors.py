from .permissions import puede_consultar_emergencias


def acceso_formularios_sci(request):
    return {
        "puede_consultar_formularios_sci": puede_consultar_emergencias(request.user),
    }
