"""Perfil de chofer: solo ve la unidad que conduce y transmite su ubicación."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso

from .models import DespliegueUnidad, Emergencia
from .permissions import es_chofer, solo_es_chofer
from .services import desplegar_unidad

class BaseChoferTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="CHO-T")
        cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Chofer", sigla="CHO-T",
            ruc="0596000000800", direccion="Centro",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo, nombre="Estación Chofer", codigo="EC-CHO",
            direccion="Centro", latitud="-0.930000", longitud="-78.610000",
        )
        cls.jefe = get_user_model().objects.create_user(
            username="jefe-cho", cedula="1000000001", password="clave",
            estacion=cls.estacion,
        )
        cls.jefe.groups.add(Group.objects.get(name="Responsable institucional"))

        cls.chofer = get_user_model().objects.create_user(
            username="chofer-uno", cedula="1000000002", password="clave",
            first_name="Luis", last_name="Herrera", estacion=cls.estacion,
        )
        cls.chofer.groups.add(Group.objects.get(name="Chofer de unidad"))

        cls.otro_chofer = get_user_model().objects.create_user(
            username="chofer-dos", cedula="1000000003", password="clave",
            estacion=cls.estacion,
        )
        cls.otro_chofer.groups.add(Group.objects.get(name="Chofer de unidad"))

    def crear_emergencia(self, codigo="IE-01012026-800", **campos):
        valores = {
            "codigo": codigo, "tipo_emergencia": "Incendio estructural",
            "direccion": "Centro", "latitud": "-0.933333", "longitud": "-78.616667",
            "estacion_responsable": self.estacion, "registrado_por": self.jefe,
        }
        valores.update(campos)
        return Emergencia.objects.create(**valores)

    def crear_unidad(self, codigo="AB-CHO-01"):
        categoria, _ = CategoriaRecurso.objects.get_or_create(
            codigo="CAT-CHO", defaults={"nombre": "Vehículos"}
        )
        tipo, _ = TipoRecurso.objects.get_or_create(
            categoria=categoria, codigo="TIP-CHO",
            defaults={"nombre": "Autobomba", "es_unidad_desplegable": True},
        )
        return Recurso.objects.create(
            estacion=self.estacion, tipo=tipo, codigo_interno=codigo,
            nombre="Autobomba", estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
            disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
            fecha_confirmacion_disponibilidad=timezone.now(),
        )

    def desplegar_con_chofer(self, chofer=None, codigo="IE-01012026-800"):
        emergencia = self.crear_emergencia(codigo=codigo)
        unidad = self.crear_unidad(f"AB-{codigo[-3:]}")
        despliegue = desplegar_unidad(emergencia, unidad, self.jefe)
        despliegue.responsable_unidad = chofer or self.chofer
        despliegue.save(update_fields=["responsable_unidad"])
        return despliegue

# ==========================================
# MÓDULO: ALCANCE DEL PERFIL
# ==========================================

class AlcanceDelChoferTests(BaseChoferTests):
    def test_el_chofer_se_reconoce_como_tal(self):
        self.assertTrue(es_chofer(self.chofer))
        self.assertTrue(solo_es_chofer(self.chofer))

    def test_un_jefe_que_ademas_conduce_conserva_sus_permisos(self):
        self.jefe.groups.add(Group.objects.get(name="Chofer de unidad"))
        self.assertTrue(es_chofer(self.jefe))
        self.assertFalse(solo_es_chofer(self.jefe))

    def test_el_chofer_no_entra_al_registro_de_emergencias(self):
        self.desplegar_con_chofer()
        self.client.force_login(self.chofer)
        respuesta = self.client.get(reverse("emergencias:lista"))
        self.assertRedirects(respuesta, reverse("emergencias:mi_unidad"))

    def test_el_chofer_no_abre_los_formularios_sci(self):
        despliegue = self.desplegar_con_chofer()
        self.client.force_login(self.chofer)
        respuesta = self.client.get(reverse(
            "emergencias:sci_editar", args=["201", despliegue.emergencia.pk]
        ))
        self.assertIn(respuesta.status_code, (403, 404))

    def test_el_chofer_no_abre_el_inventario(self):
        self.client.force_login(self.chofer)
        self.assertEqual(self.client.get(reverse("inventario:lista")).status_code, 403)

# ==========================================
# MÓDULO: PANTALLA DE LA UNIDAD
# ==========================================

class PantallaDelChoferTests(BaseChoferTests):
    def test_muestra_la_emergencia_de_su_unidad(self):
        despliegue = self.desplegar_con_chofer()
        self.client.force_login(self.chofer)
        respuesta = self.client.get(reverse("emergencias:mi_unidad"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, despliegue.emergencia.codigo)
        self.assertContains(respuesta, despliegue.unidad.codigo_interno)

    def test_ofrece_iniciar_navegacion_con_las_coordenadas(self):
        self.desplegar_con_chofer()
        self.client.force_login(self.chofer)
        respuesta = self.client.get(reverse("emergencias:mi_unidad"))
        self.assertContains(respuesta, "google.com/maps/dir/")
        self.assertContains(respuesta, "destination=-0.933333,-78.616667")

    def test_sin_coordenadas_lo_explica_en_vez_de_ofrecer_un_enlace_roto(self):
        emergencia = self.crear_emergencia(
            codigo="IE-01012026-801", latitud=None, longitud=None
        )
        despliegue = desplegar_unidad(emergencia, self.crear_unidad("AB-SIN"), self.jefe)
        despliegue.responsable_unidad = self.chofer
        despliegue.save(update_fields=["responsable_unidad"])
        self.client.force_login(self.chofer)
        respuesta = self.client.get(reverse("emergencias:mi_unidad"))
        self.assertContains(respuesta, "no tiene coordenadas registradas")
        self.assertNotContains(respuesta, "google.com/maps/dir/")

    def test_no_ve_la_unidad_de_otro_chofer(self):
        self.desplegar_con_chofer(chofer=self.otro_chofer)
        self.client.force_login(self.chofer)
        respuesta = self.client.get(reverse("emergencias:mi_unidad"))
        self.assertContains(respuesta, "No tiene una unidad asignada")

    def test_un_despliegue_finalizado_desaparece_de_su_pantalla(self):
        despliegue = self.desplegar_con_chofer()
        DespliegueUnidad.objects.filter(pk=despliegue.pk).update(
            estado=DespliegueUnidad.Estado.FINALIZADA
        )
        self.client.force_login(self.chofer)
        respuesta = self.client.get(reverse("emergencias:mi_unidad"))
        self.assertContains(respuesta, "No tiene una unidad asignada")

    def test_quien_no_es_chofer_no_abre_esta_pantalla(self):
        self.client.force_login(self.jefe)
        self.assertEqual(self.client.get(reverse("emergencias:mi_unidad")).status_code, 403)

    def test_el_menu_lateral_solo_le_ofrece_su_unidad(self):
        self.desplegar_con_chofer()
        self.client.force_login(self.chofer)
        respuesta = self.client.get(reverse("emergencias:mi_unidad"))
        self.assertContains(respuesta, "Mi unidad")
        self.assertNotContains(respuesta, "Panel de control")
        self.assertNotContains(respuesta, "Capacidades operativas")

# ==========================================
# MÓDULO: TRANSMISIÓN DE UBICACIÓN
# ==========================================

class TransmisionDelChoferTests(BaseChoferTests):
    def test_abre_la_consola_de_su_propia_unidad(self):
        despliegue = self.desplegar_con_chofer()
        self.client.force_login(self.chofer)
        respuesta = self.client.get(reverse("emergencias:transmitir_gps", args=[despliegue.pk]))
        self.assertEqual(respuesta.status_code, 200)

    def test_no_abre_la_consola_de_otra_unidad(self):
        despliegue = self.desplegar_con_chofer(chofer=self.otro_chofer)
        self.client.force_login(self.chofer)
        respuesta = self.client.get(reverse("emergencias:transmitir_gps", args=[despliegue.pk]))
        self.assertIn(respuesta.status_code, (403, 404))

    def test_registra_la_posicion_de_su_unidad(self):
        despliegue = self.desplegar_con_chofer()
        self.client.force_login(self.chofer)
        respuesta = self.client.post(
            reverse("emergencias:registrar_posicion", args=[despliegue.pk]),
            data={"latitud": -0.9335, "longitud": -78.6165},
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(despliegue.posiciones.count(), 1)

    def test_no_registra_posiciones_en_la_unidad_de_otro(self):
        despliegue = self.desplegar_con_chofer(chofer=self.otro_chofer)
        self.client.force_login(self.chofer)
        respuesta = self.client.post(
            reverse("emergencias:registrar_posicion", args=[despliegue.pk]),
            data={"latitud": -0.9335, "longitud": -78.6165},
            content_type="application/json",
        )
        self.assertIn(respuesta.status_code, (400, 403, 404))
        self.assertEqual(despliegue.posiciones.count(), 0)
