from datetime import timedelta

from django import forms
from django.forms import inlineformset_factory
from django.db.models import Q
from django.utils import timezone

from inventario.models import Recurso
from inventario.permissions import recursos_permitidos

from .models import FormularioSCI211, RegistroRecursoSCI211


class FormularioSCI211Form(forms.ModelForm):
    class Meta:
        model = FormularioSCI211
        fields = ("punto_registro", "registrador_1", "registrador_2", "registrador_3")
        widgets = {"punto_registro": forms.TextInput(attrs={"autocomplete": "organization"})}


class RegistroRecursoSCI211Form(forms.ModelForm):
    class Meta:
        model = RegistroRecursoSCI211
        exclude = ("formulario", "despliegue", "orden")
        widgets = {
            "fecha_hora_solicitud": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "fecha_hora_arribo": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "fecha_hora_desmovilizacion": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Recurso.objects.none()
        if usuario and usuario.is_authenticated:
            vigentes = Q(
                activo=True,
                estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
                disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
                fecha_confirmacion_disponibilidad__gte=(
                    timezone.now() - timedelta(hours=24)
                ),
            )
            # Un recurso ya vinculado debe seguir visible para consultar y
            # guardar el registro aunque después haya sido asignado.
            if self.instance and self.instance.recurso_inventario_id:
                vigentes |= Q(pk=self.instance.recurso_inventario_id)
            queryset = recursos_permitidos(usuario).filter(vigentes).select_related(
                "estacion", "tipo", "tipo__categoria"
            ).order_by(
                "estacion__nombre", "tipo__categoria__nombre", "nombre"
            )
        self.fields["recurso_inventario"].queryset = queryset
        self.fields["recurso_inventario"].empty_label = (
            "Seleccione un recurso disponible y verificado"
        )
        for nombre in (
            "clase_recurso", "tipo_recurso", "institucion_procedencia",
            "matricula_identificacion",
        ):
            self.fields[nombre].required = False

    def clean(self):
        datos = super().clean()
        recurso = datos.get("recurso_inventario")
        if recurso:
            datos["clase_recurso"] = recurso.tipo.categoria.nombre
            datos["tipo_recurso"] = recurso.tipo.nombre
            datos["institucion_procedencia"] = recurso.estacion.cuerpo_bomberos.nombre
            datos["matricula_identificacion"] = recurso.codigo_interno
        else:
            for nombre in (
                "clase_recurso", "institucion_procedencia", "matricula_identificacion"
            ):
                if not str(datos.get(nombre) or "").strip():
                    self.add_error(nombre, "Seleccione un recurso verificado o complete este campo.")
        return datos


RegistroRecursoSCI211FormSet = inlineformset_factory(
    FormularioSCI211, RegistroRecursoSCI211, form=RegistroRecursoSCI211Form,
    extra=1, can_delete=True, min_num=1, validate_min=True,
)
