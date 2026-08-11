from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path


app_name = "usuarios"

urlpatterns = [
    path(
        "iniciar-sesion/",
        LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("cerrar-sesion/", LogoutView.as_view(), name="logout"),
]
