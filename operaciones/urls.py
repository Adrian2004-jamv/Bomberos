from django.urls import path

from . import views

app_name = "operaciones"

urlpatterns = [
    path("capacidades/", views.lista_capacidades, name="lista_capacidades"),
    path("capacidades/<int:pk>/", views.detalle_capacidad, name="detalle_capacidad"),
    path("evaluar/", views.evaluar_capacidad, name="evaluar_capacidad"),
    path("evaluaciones/", views.historial_evaluaciones, name="historial_evaluaciones"),
    path("evaluaciones/<int:pk>/", views.detalle_evaluacion, name="detalle_evaluacion"),
]
