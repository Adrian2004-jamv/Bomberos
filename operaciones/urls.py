from django.urls import path

from . import views

app_name = "operaciones"

urlpatterns = [
    path("capacidades/", views.lista_capacidades, name="lista_capacidades"),
    path("capacidades/crear/", views.crear_capacidad, name="crear_capacidad"),
    path("capacidades/<int:pk>/editar/", views.editar_capacidad, name="editar_capacidad"),
    path("capacidades/<int:pk>/", views.detalle_capacidad, name="detalle_capacidad"),
    path("evaluar/", views.evaluar_capacidad, name="evaluar_capacidad"),
    path("evaluaciones/", views.historial_evaluaciones, name="historial_evaluaciones"),
    path("evaluaciones/<int:pk>/", views.detalle_evaluacion, name="detalle_evaluacion"),
]
