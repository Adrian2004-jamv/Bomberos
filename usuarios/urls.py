from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views


app_name = "usuarios"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nuevo/", views.crear, name="crear"),
    path("cambiar-clave/", views.cambiar_clave, name="cambiar_clave"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/actividad/", views.cambiar_actividad, name="cambiar_actividad"),
    path("<int:pk>/restablecer-clave/", views.restablecer_clave, name="restablecer_clave"),
    path(
        "iniciar-sesion/",
        LoginView.as_view(template_name="usuarios/login.html"),
        name="login",
    ),
    path("cerrar-sesion/", LogoutView.as_view(), name="logout"),
]
