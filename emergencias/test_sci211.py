from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from instituciones.models import Canton, CuerpoBomberos, Estacion

from .models import Emergencia, FormularioSCI211, RegistroRecursoSCI211
from .services_sci import finalizar_sci211, generar_pdf_sci211


class SCI211Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Prueba", codigo="SCI-T")
        cls.cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Prueba", sigla="SCI-T", ruc="0599999999001",
            direccion="Dirección institucional",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo, nombre="Estación Norte", codigo="EN-SCI",
            direccion="Norte", latitud="-0.900000", longitud="-78.600000",
        )
        cls.otra_estacion = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo, nombre="Estación Sur", codigo="ES-SCI",
            direccion="Sur", latitud="-0.910000", longitud="-78.610000",
        )
        cls.usuario = cls._usuario("responsable-sci", "0571000001", "Responsable de estación", cls.estacion)
        cls.consulta = cls._usuario("consulta-sci", "0571000002", "Operador de consulta", cls.estacion)
        cls.otro = cls._usuario("otro-sci", "0571000003", "Responsable de estación", cls.otra_estacion)

    @classmethod
    def _usuario(cls, nombre, cedula, grupo, estacion):
        usuario = get_user_model().objects.create_user(username=nombre, cedula=cedula, password="clave", estacion=estacion)
        usuario.groups.add(Group.objects.get(name=grupo))
        return usuario

    def setUp(self):
        self.emergencia = Emergencia.objects.create(
            codigo="EM-SCI-001", tipo_emergencia="Incendio de prueba", direccion="Calle Ficticia 123",
            latitud="-0.933333", longitud="-78.616667", estacion_responsable=self.estacion,
            registrado_por=self.usuario,
        )

    def crear_formulario(self, completo=True):
        f = FormularioSCI211.objects.create(
            emergencia=self.emergencia, codigo="SCI-211-EM-SCI-001", punto_registro="Puesto de Comando",
            preparado_por_nombre="Usuario de Prueba", creado_por=self.usuario, modificado_por=self.usuario,
        )
        if completo:
            RegistroRecursoSCI211.objects.create(
                formulario=f, solicitado_por="CI Prueba", fecha_hora_solicitud=self.emergencia.fecha_reporte,
                clase_recurso="Vehículos", tipo_recurso="Autobomba", institucion_procedencia="Bomberos Prueba",
                matricula_identificacion="TEST-001", numero_personas=4, estado_recurso="disponible",
                ubicacion_recurso="Área de Espera", observaciones="Contenido <script>alert('x')</script> y ñ.",
            )
        return f

    def test_creacion_autorizada_y_borrador(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.post(reverse("emergencias:sci211_crear", args=[self.emergencia.pk]))
        self.assertEqual(respuesta.status_code, 302)
        formulario = FormularioSCI211.objects.get(emergencia=self.emergencia)
        self.assertEqual(formulario.estado, FormularioSCI211.Estado.BORRADOR)
        self.assertEqual(formulario.preparado_por_nombre, self.usuario.username)

    def test_finalizacion_congela_datos_e_impide_edicion(self):
        formulario = finalizar_sci211(self.crear_formulario(), self.usuario)
        self.assertEqual(formulario.estado, FormularioSCI211.Estado.FINALIZADO)
        self.assertEqual(formulario.institucion_emitida, self.cuerpo.nombre)
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse("emergencias:sci211_editar", args=[formulario.pk])).status_code, 302)

    def test_no_finaliza_incompleto(self):
        formulario = self.crear_formulario(completo=False)
        self.client.force_login(self.usuario)
        respuesta = self.client.post(reverse("emergencias:sci211_finalizar", args=[formulario.pk]))
        formulario.refresh_from_db()
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(formulario.estado, FormularioSCI211.Estado.BORRADOR)

    def test_restriccion_estacion_y_solo_lectura(self):
        formulario = self.crear_formulario()
        self.client.force_login(self.otro)
        self.assertEqual(self.client.get(reverse("emergencias:sci211_detalle", args=[formulario.pk])).status_code, 404)
        self.client.force_login(self.consulta)
        self.assertEqual(self.client.get(reverse("emergencias:sci211_detalle", args=[formulario.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("emergencias:sci211_editar", args=[formulario.pk])).status_code, 403)

    def test_pdf_protegido_no_vacio_y_original_intacto(self):
        formulario = self.crear_formulario()
        original = Path("Total de Formularios SCI/SCI - 211 formulario.xlsx")
        antes = original.read_bytes()
        self.assertEqual(self.client.get(reverse("emergencias:sci211_pdf", args=[formulario.pk])).status_code, 302)
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:sci211_pdf", args=[formulario.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        self.assertIn("SCI_211_EM-SCI-001.pdf", respuesta["Content-Disposition"])
        self.assertGreater(len(respuesta.content), 1000)
        self.assertEqual(original.read_bytes(), antes)

    def test_pdf_escapa_html_y_representa_espanol(self):
        pdf = generar_pdf_sci211(self.crear_formulario())
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 1000)
