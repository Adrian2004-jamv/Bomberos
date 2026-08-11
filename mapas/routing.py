from django.urls import path

from .consumers import MapaPosicionesConsumer


websocket_urlpatterns = [
    path("ws/mapa/posiciones/", MapaPosicionesConsumer.as_asgi()),
]
