from .permissions import solo_es_chofer

def perfil_chofer(request):
    """Marca al usuario cuyo único rol es conducir.

    El menú lateral lo usa para no ofrecerle secciones que su perfil no puede
    abrir: vería una lista de enlaces que solo devuelven «sin autorización».
    """
    return {"solo_chofer": solo_es_chofer(request.user)}
