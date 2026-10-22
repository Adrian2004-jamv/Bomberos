from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.principal, name="principal"),
    path("emergencia/<int:pk>/resumen/", views.resumen_emergencia, name="resumen_emergencia"),
    path("emergencia/<int:pk>/pdf/", views.descargar_pdf_emergencia, name="pdf_emergencia"),
]
