from django.urls import path

from . import views

app_name = "mapas"

urlpatterns = [
    path("", views.mapa_operativo, name="operativo"),
    path("datos/", views.datos_operativos, name="datos"),
    path("recorridos/<int:pk>/", views.recorrido_despliegue, name="recorrido"),
]
