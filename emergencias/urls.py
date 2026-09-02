from django.urls import path

from . import views

app_name = "emergencias"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("crear/", views.crear, name="crear"),
    path("exportar/", views.exportar, name="exportar"),
    path("formularios-sci/211/", views.sci211_lista, name="sci211_lista"),
    path("formularios-sci/catalogo/<str:codigo>/", views.formulario_sci_catalogo_detalle, name="sci_catalogo_detalle"),
    path("formularios-sci/catalogo/<str:codigo>/visualizar/", views.formulario_sci_catalogo_visualizar, name="sci_catalogo_visualizar"),
    path("formularios-sci/<str:codigo>/emergencia/<int:emergencia_pk>/visualizar/", views.formulario_sci_visualizar, name="sci_visualizar"),
    path("formularios-sci/<str:codigo>/emergencia/<int:emergencia_pk>/editar/", views.formulario_sci_editar, name="sci_editar"),
    path("formularios-sci/<str:codigo>/emergencia/<int:emergencia_pk>/finalizar/", views.formulario_sci_finalizar, name="sci_finalizar"),
    path("formularios-sci/211/<int:pk>/", views.sci211_detalle, name="sci211_detalle"),
    path("formularios-sci/211/<int:pk>/editar/", views.sci211_editar, name="sci211_editar"),
    path("formularios-sci/211/<int:pk>/finalizar/", views.sci211_finalizar, name="sci211_finalizar"),
    path("formularios-sci/211/<int:pk>/imprimir/", views.sci211_imprimir, name="sci211_imprimir"),
    path("<int:emergencia_pk>/formularios-sci/211/crear/", views.sci211_crear, name="sci211_crear"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/eliminar/", views.eliminar, name="eliminar"),
    path("<int:pk>/estado/", views.cambiar_estado, name="cambiar_estado"),
    path("<int:pk>/despachar/", views.despachar, name="despachar"),
    path("despliegues/<int:pk>/estado/", views.actualizar_despliegue, name="despliegue_estado"),
    path("mi-unidad/", views.mi_unidad, name="mi_unidad"),
    path("despliegues/<int:pk>/gps/", views.transmitir_gps, name="transmitir_gps"),
    path("api/despliegues/<int:pk>/posiciones/", views.registrar_posicion, name="registrar_posicion"),
    path("api/despliegues/<int:pk>/ultima-posicion/", views.ultima_posicion, name="ultima_posicion"),
]
