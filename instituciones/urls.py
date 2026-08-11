from django.urls import path

from . import views

app_name = "instituciones"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("crear/", views.crear_cuerpo, name="crear_cuerpo"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/editar/", views.editar_cuerpo, name="editar_cuerpo"),
    path(
        "<int:cuerpo_pk>/estaciones/crear/",
        views.crear_estacion,
        name="crear_estacion",
    ),
    path("estaciones/<int:pk>/editar/", views.editar_estacion, name="editar_estacion"),
]
