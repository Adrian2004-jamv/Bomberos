from django.urls import path

from . import views

app_name = "emergencias"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("formularios-sci/211/", views.sci211_lista, name="sci211_lista"),
    path("formularios-sci/211/<int:pk>/", views.sci211_detalle, name="sci211_detalle"),
    path("formularios-sci/211/<int:pk>/editar/", views.sci211_editar, name="sci211_editar"),
    path("formularios-sci/211/<int:pk>/finalizar/", views.sci211_finalizar, name="sci211_finalizar"),
    path("formularios-sci/211/<int:pk>/imprimir/", views.sci211_imprimir, name="sci211_imprimir"),
    path("formularios-sci/211/<int:pk>/pdf/", views.sci211_pdf, name="sci211_pdf"),
    path("<int:emergencia_pk>/formularios-sci/211/crear/", views.sci211_crear, name="sci211_crear"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("despliegues/<int:pk>/gps/", views.transmitir_gps, name="transmitir_gps"),
    path("api/despliegues/<int:pk>/posiciones/", views.registrar_posicion, name="registrar_posicion"),
    path("api/despliegues/<int:pk>/ultima-posicion/", views.ultima_posicion, name="ultima_posicion"),
]
