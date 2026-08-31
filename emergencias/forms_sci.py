from django import forms
from django.forms import inlineformset_factory
from django.db.models import Q

from inventario.models import Recurso
from inventario.permissions import estaciones_permitidas, recursos_permitidos

from .models import FormularioSCI211, RegistroRecursoSCI211

class FormularioSCI211Form(forms.ModelForm):
    class Meta:
        model = FormularioSCI211
        fields = ("punto_registro", "registrador_1", "registrador_2", "registrador_3")
        widgets = {"punto_registro": forms.TextInput(attrs={"autocomplete": "organization"})}

class SelectRecursoInventario(forms.Select):
    """Lleva los datos del recurso a cada opción del desplegable.

    El servidor ya los copia al guardar, pero quien llena el formulario no los
    veía hasta entonces. Con estos atributos el navegador puede completar la
    clase, el tipo, la institución y la matrícula en cuanto se elige el recurso.
    """

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcion = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        recurso = getattr(value, "instance", None)
        if recurso is not None:
            # Se muestra bloqueada en lugar de esconderse: así se entiende
            # que la unidad existe y por qué no está disponible ahora.
            if motivo_no_disponible(recurso):
                opcion["attrs"]["disabled"] = True
            opcion["attrs"].update({
                "data-clase": recurso.tipo.categoria.nombre,
                "data-tipo": recurso.tipo.nombre,
                "data-institucion": recurso.estacion.cuerpo_bomberos.nombre,
                "data-matricula": recurso.codigo_interno,
                "data-desplegable": "1" if recurso.tipo.es_unidad_desplegable else "0",
            })
        return opcion

def motivo_no_disponible(recurso):
    """Explica por qué una unidad no puede registrarse, o None si sí puede.

    Antes la lista simplemente omitía lo que no estaba libre y la ambulancia
    desaparecía sin explicación. El motivo importa tanto como el hecho: no es
    lo mismo una unidad ya despachada a otra emergencia que una averiada.
    """
    if not recurso.activo:
        return "dada de baja"
    if recurso.estado_operativo == Recurso.EstadoOperativo.FUERA_SERVICIO:
        return "fuera de servicio"
    if recurso.estado_operativo == Recurso.EstadoOperativo.MANTENIMIENTO:
        return "en mantenimiento"
    if recurso.disponibilidad == Recurso.Disponibilidad.ASIGNADO:
        return "ya asignada a otra emergencia"
    if recurso.disponibilidad != Recurso.Disponibilidad.DISPONIBLE:
        return recurso.get_disponibilidad_display().lower()
    return None

def etiqueta_de_recurso(recurso):
    """Nombra el recurso y explica su situación cuando no está libre.

    La confirmación de disponibilidad caduca a las 24 horas. Antes ese
    vencimiento borraba la unidad de la lista y quien despachaba no entendía
    por qué su ambulancia no aparecía; ahora se muestra con la nota y decide.
    """
    texto = f"{recurso.codigo_interno} - {recurso.nombre} ({recurso.estacion.nombre})"
    motivo = motivo_no_disponible(recurso)
    if motivo:
        return f"{texto} · {motivo}"
    if not recurso.disponibilidad_actualizada:
        texto += " · disponibilidad sin confirmar hoy"
    return texto

class RegistroRecursoSCI211Form(forms.ModelForm):
    class Meta:
        model = RegistroRecursoSCI211
        exclude = ("formulario", "despliegue", "orden")
        widgets = {
            "fecha_hora_solicitud": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "fecha_hora_arribo": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "fecha_hora_desmovilizacion": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
            "recurso_inventario": SelectRecursoInventario(
                attrs={"data-recurso-inventario": ""}
            ),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Recurso.objects.none()
        if usuario and usuario.is_authenticated:
            # Se ofrece el inventario completo del ámbito. Lo que no puede
            # salir aparece bloqueado y con el motivo al lado; ocultarlo dejaba
            # a quien despacha buscando una ambulancia que sí existe.
            vigentes = Q(activo=True)
            # Un recurso ya vinculado debe seguir visible para consultar y
            # guardar el registro aunque después haya sido dado de baja.
            if self.instance and self.instance.recurso_inventario_id:
                vigentes |= Q(pk=self.instance.recurso_inventario_id)
            queryset = recursos_permitidos(usuario).filter(vigentes).select_related(
                "estacion", "estacion__cuerpo_bomberos", "tipo", "tipo__categoria"
            ).order_by(
                "estacion__nombre", "tipo__categoria__nombre", "nombre"
            )
        self.fields["recurso_inventario"].queryset = queryset
        self.fields["recurso_inventario"].empty_label = (
            "Seleccione un recurso del inventario"
        )
        self.fields["recurso_inventario"].label_from_instance = etiqueta_de_recurso
        self.preparar_responsable(usuario)
        for nombre, marca in (
            ("clase_recurso", "clase"), ("tipo_recurso", "tipo"),
            ("institucion_procedencia", "institucion"),
            ("matricula_identificacion", "matricula"),
        ):
            self.fields[nombre].required = False
            self.fields[nombre].widget.attrs["data-derivado"] = marca

    def preparar_responsable(self, usuario):
        """Ofrece los choferes de la institución para ponerlos al volante.

        Solo aparecen quienes tienen el perfil de chofer: son los únicos que
        podrán abrir la consola de transmisión, de modo que asignar a otro
        dejaría la unidad sin nadie que informe su ubicación.
        """
        from usuarios.models import Usuario

        from .permissions import GRUPO_CHOFER

        campo = self.fields["responsable_unidad"]
        candidatos = Usuario.objects.none()
        if usuario and usuario.is_authenticated:
            candidatos = Usuario.objects.filter(
                is_active=True,
                groups__name=GRUPO_CHOFER,
                estacion__in=estaciones_permitidas(usuario),
            ).select_related("estacion").order_by("first_name", "last_name", "username")
            # Un chofer ya asignado sigue visible aunque cambie de estación.
            if self.instance and self.instance.responsable_unidad_id:
                candidatos = candidatos | Usuario.objects.filter(
                    pk=self.instance.responsable_unidad_id
                )
        campo.queryset = candidatos.distinct()
        campo.empty_label = "Sin responsable asignado"
        campo.label_from_instance = (
            lambda persona: f"{persona.get_full_name() or persona.username}"
                            f"{f' ({persona.estacion.codigo})' if persona.estacion_id else ''}"
        )

    def clean(self):
        datos = super().clean()
        recurso = datos.get("recurso_inventario")
        if recurso:
            # La opción va bloqueada en el desplegable, pero el navegador no es
            # la única forma de enviar el formulario. Se admite el recurso que
            # ya estaba guardado aunque después haya dejado de estar libre.
            motivo = motivo_no_disponible(recurso)
            if motivo and recurso.pk != self.instance.recurso_inventario_id:
                self.add_error(
                    "recurso_inventario",
                    f"La unidad {recurso.codigo_interno} está {motivo}.",
                )
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

# El formulario vacío que clona «Agregar otro recurso» sale del propio formset,
# de modo que el guion no construye campos a mano y no se desincroniza si el
# registro cambia de columnas.
RegistroRecursoSCI211FormSet = inlineformset_factory(
    FormularioSCI211, RegistroRecursoSCI211, form=RegistroRecursoSCI211Form,
    extra=1, can_delete=True, min_num=1, validate_min=True,
)
