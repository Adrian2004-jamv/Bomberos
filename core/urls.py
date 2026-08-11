from django.urls import path

from . import views


app_name = "core"

urlpatterns = [
    path("manifest.json", views.manifiesto, name="manifest"),
    path("service-worker.js", views.service_worker, name="service_worker"),
    path("sin-conexion/", views.sin_conexion, name="sin_conexion"),
    path("", views.inicio, name="inicio"),
]
