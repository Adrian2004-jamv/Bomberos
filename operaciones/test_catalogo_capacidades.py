"""Catálogo de capacidades operativas y sus requisitos.

Una capacidad sin requisitos no mide nada, así que ambos se guardan juntos.
Estas pruebas cubren ese guardado, el alcance provincial que exige y qué pasa
con las evaluaciones ya registradas.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso

from .models import (EvaluacionCapacidadEstacion, RequisitoRecursoCapacidad,
                     TipoCapacidadOperativa)
from .services import evaluar_capacidad_estacion


class BaseCapacidadesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="LAT-CC")
        cls.cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Capacidades", sigla="CBCC-CC",
            ruc="0596000000701", direccion="Centro",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo, nombre="Central Capacidades", codigo="CCC-CC",
            direccion="Centro", latitud="-0.930000", longitud="-78.610000",
        )
        categoria = CategoriaRecurso.objects.create(nombre="Vehículos", codigo="VEH-CC")
        cls.tipo = TipoRecurso.objects.create(
            categoria=categoria, nombre="Autobomba", codigo="AUT-CC"
        )
        cls.tipo_secundario = TipoRecurso.objects.create(
            categoria=categoria, nombre="Motobomba", codigo="MOT-CC"
        )
        cls.provincial = cls.crear_usuario(
            "provincial-cc", "0630000001", "Responsable provincial", None
        )
        cls.institucional = cls.crear_usuario(
            "institucional-cc", "0630000002", "Responsable institucional", cls.estacion
        )

    @classmethod
    def crear_usuario(cls, username, cedula, grupo, estacion):
        usuario = get_user_model().objects.create_user(
            username=username, cedula=cedula, password="clave", estacion=estacion
        )
        usuario.groups.add(Group.objects.get(name=grupo))
        return usuario

    def datos(self, **cambios):
        base = {
            "nombre": "Respuesta a incendio estructural",
            "codigo": "rie-cc",
            "descripcion": "Ataque directo con agua a presión.",
            "activo": "on",
            "requisitos_recursos-TOTAL_FORMS": "3",
            "requisitos_recursos-INITIAL_FORMS": "0",
            "requisitos_recursos-MIN_NUM_FORMS": "0",
            "requisitos_recursos-MAX_NUM_FORMS": "1000",
            "requisitos_recursos-0-tipo_recurso": str(self.tipo.pk),
            "requisitos_recursos-0-cantidad_minima": "1",
            "requisitos_recursos-0-obligatorio": "on",
            "requisitos_recursos-0-observaciones": "",
            "requisitos_recursos-1-tipo_recurso": "",
            "requisitos_recursos-1-cantidad_minima": "",
            "requisitos_recursos-1-observaciones": "",
            "requisitos_recursos-2-tipo_recurso": "",
            "requisitos_recursos-2-cantidad_minima": "",
            "requisitos_recursos-2-observaciones": "",
        }
        base.update(cambios)
        return base


class AccesoTests(BaseCapacidadesTests):
    def test_solo_el_alcance_provincial_edita_el_catalogo(self):
        self.client.force_login(self.institucional)
        self.assertEqual(
            self.client.get(reverse("operaciones:crear_capacidad")).status_code, 403
        )

    def test_el_alcance_provincial_abre_el_formulario(self):
        self.client.force_login(self.provincial)
        respuesta = self.client.get(reverse("operaciones:crear_capacidad"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Requisitos de recursos")

    def test_el_listado_ofrece_crear_solo_a_quien_puede(self):
        self.client.force_login(self.provincial)
        self.assertContains(
            self.client.get(reverse("operaciones:lista_capacidades")), "Nueva capacidad"
        )
        self.client.force_login(self.institucional)
        self.assertNotContains(
            self.client.get(reverse("operaciones:lista_capacidades")), "Nueva capacidad"
        )


class CreacionTests(BaseCapacidadesTests):
    def test_crea_la_capacidad_con_sus_requisitos(self):
        self.client.force_login(self.provincial)
        respuesta = self.client.post(reverse("operaciones:crear_capacidad"), self.datos())
        capacidad = TipoCapacidadOperativa.objects.get(codigo="RIE-CC")
        self.assertRedirects(
            respuesta, reverse("operaciones:detalle_capacidad", args=[capacidad.pk])
        )
        requisito = capacidad.requisitos_recursos.get()
        self.assertEqual(requisito.tipo_recurso, self.tipo)
        self.assertEqual(requisito.cantidad_minima, 1)
        self.assertTrue(requisito.obligatorio)

    def test_las_filas_en_blanco_no_crean_requisitos(self):
        self.client.force_login(self.provincial)
        self.client.post(reverse("operaciones:crear_capacidad"), self.datos())
        self.assertEqual(RequisitoRecursoCapacidad.objects.count(), 1)

    def test_un_requisito_invalido_no_deja_la_capacidad_a_medias(self):
        """Se guardan juntos: una capacidad sin sus requisitos mediría mal a
        todas las estaciones hasta que alguien completara la otra mitad."""
        self.client.force_login(self.provincial)
        respuesta = self.client.post(reverse("operaciones:crear_capacidad"), self.datos(**{
            "requisitos_recursos-0-cantidad_minima": "0",
        }))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(TipoCapacidadOperativa.objects.filter(codigo="RIE-CC").exists())
        self.assertFalse(RequisitoRecursoCapacidad.objects.exists())

    def test_no_admite_el_mismo_tipo_dos_veces(self):
        self.client.force_login(self.provincial)
        respuesta = self.client.post(reverse("operaciones:crear_capacidad"), self.datos(**{
            "requisitos_recursos-1-tipo_recurso": str(self.tipo.pk),
            "requisitos_recursos-1-cantidad_minima": "2",
        }))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(TipoCapacidadOperativa.objects.filter(codigo="RIE-CC").exists())


class EdicionTests(BaseCapacidadesTests):
    def setUp(self):
        self.capacidad = TipoCapacidadOperativa.objects.create(
            nombre="Rescate vehicular", codigo="RV-CC"
        )
        self.requisito = RequisitoRecursoCapacidad.objects.create(
            capacidad=self.capacidad, tipo_recurso=self.tipo, cantidad_minima=1
        )
        self.client.force_login(self.provincial)

    def datos_edicion(self, **cambios):
        base = {
            "nombre": self.capacidad.nombre,
            "codigo": self.capacidad.codigo,
            "descripcion": "",
            "activo": "on",
            "requisitos_recursos-TOTAL_FORMS": "1",
            "requisitos_recursos-INITIAL_FORMS": "1",
            "requisitos_recursos-MIN_NUM_FORMS": "0",
            "requisitos_recursos-MAX_NUM_FORMS": "1000",
            "requisitos_recursos-0-id": str(self.requisito.pk),
            "requisitos_recursos-0-capacidad": str(self.capacidad.pk),
            "requisitos_recursos-0-tipo_recurso": str(self.tipo.pk),
            "requisitos_recursos-0-cantidad_minima": "1",
            "requisitos_recursos-0-observaciones": "",
        }
        base.update(cambios)
        return base

    def test_cambia_la_cantidad_minima_de_un_requisito(self):
        self.client.post(
            reverse("operaciones:editar_capacidad", args=[self.capacidad.pk]),
            self.datos_edicion(**{"requisitos_recursos-0-cantidad_minima": "3"}),
        )
        self.requisito.refresh_from_db()
        self.assertEqual(self.requisito.cantidad_minima, 3)

    def test_marcar_eliminar_retira_el_requisito(self):
        self.client.post(
            reverse("operaciones:editar_capacidad", args=[self.capacidad.pk]),
            self.datos_edicion(**{"requisitos_recursos-0-DELETE": "on"}),
        )
        self.assertFalse(RequisitoRecursoCapacidad.objects.filter(pk=self.requisito.pk).exists())
        self.assertTrue(TipoCapacidadOperativa.objects.filter(pk=self.capacidad.pk).exists())

    def test_desactivar_conserva_las_evaluaciones_historicas(self):
        Recurso.objects.create(
            estacion=self.estacion, tipo=self.tipo,
            codigo_interno="AB-CC-01", nombre="Autobomba 1",
        )
        evaluacion = evaluar_capacidad_estacion(
            estacion=self.estacion, tipo_capacidad=self.capacidad,
            usuario_evaluador=self.provincial,
        )
        self.client.post(
            reverse("operaciones:editar_capacidad", args=[self.capacidad.pk]),
            self.datos_edicion(activo=""),
        )
        self.capacidad.refresh_from_db()
        evaluacion.refresh_from_db()
        self.assertFalse(self.capacidad.activo)
        self.assertTrue(
            EvaluacionCapacidadEstacion.objects.filter(pk=evaluacion.pk).exists()
        )
        self.assertTrue(evaluacion.detalle_recursos)

    def test_el_formulario_llega_con_los_requisitos_existentes(self):
        respuesta = self.client.get(
            reverse("operaciones:editar_capacidad", args=[self.capacidad.pk])
        )
        self.assertEqual(respuesta.context["requisitos"].initial_form_count(), 1)
        self.assertContains(respuesta, "Rescate vehicular")
