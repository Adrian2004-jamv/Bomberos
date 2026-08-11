from django.urls import path

from . import views

app_name = "emergencias"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("despliegues/<int:pk>/gps/", views.transmitir_gps, name="transmitir_gps"),
    path("api/despliegues/<int:pk>/posiciones/", views.registrar_posicion, name="registrar_posicion"),
    path("api/despliegues/<int:pk>/ultima-posicion/", views.ultima_posicion, name="ultima_posicion"),
]
