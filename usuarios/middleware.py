"""Obliga a reemplazar una clave que asignó otra persona.

Cuando el operador de sistemas crea una cuenta o restablece un acceso, elige la
clave y por tanto la conoce. Mientras el usuario no la sustituya, cualquier
página lo devuelve al formulario de cambio.
"""

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import cached_property


class ExigirCambioDeClave:
    def __init__(self, get_response):
        self.get_response = get_response

    @cached_property
    def rutas_libres(self):
        """Rutas que deben responder aunque la clave siga pendiente.

        Se resuelven la primera vez que se usan, no al importar el módulo,
        porque el mapa de rutas todavía no está cargado cuando Django arma la
        cadena de middleware.
        """
        return {
            reverse("usuarios:cambiar_clave"),
            reverse("usuarios:login"),
            reverse("usuarios:logout"),
            reverse("core:manifest"),
            reverse("core:service_worker"),
            reverse("core:sin_conexion"),
        }

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if (
            usuario is not None
            and usuario.is_authenticated
            and usuario.debe_cambiar_clave
            and request.path not in self.rutas_libres
        ):
            return redirect("usuarios:cambiar_clave")
        return self.get_response(request)
