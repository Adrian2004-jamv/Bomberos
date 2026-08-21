from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views


app_name = "usuarios"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nuevo/", views.crear, name="crear"),
    path(
        "iniciar-sesion/",
        LoginView.as_view(template_name="usuarios/login.html"),
        name="login",
    ),
    path("cerrar-sesion/", LogoutView.as_view(), name="logout"),
]
