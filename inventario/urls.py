from django.urls import path

from . import views

app_name = "inventario"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("crear/", views.crear, name="crear"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/cambiar-estado/", views.cambiar_estado, name="cambiar_estado"),
    path("<int:pk>/confirmar-disponibilidad/", views.confirmar_disponibilidad, name="confirmar_disponibilidad"),
    path("<int:pk>/historial/", views.historial, name="historial"),
]
