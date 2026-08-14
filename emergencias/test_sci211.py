from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
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
        cls.otro_cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Otra Institución", sigla="SCI-O",
            ruc="0599999999002", direccion="Otra dirección",
        )
        cls.estacion_otra_institucion = Estacion.objects.create(
            cuerpo_bomberos=cls.otro_cuerpo, nombre="Estación Externa", codigo="EX-SCI",
            direccion="Exterior", latitud="-0.920000", longitud="-78.620000",
        )
        cls.usuario = cls._usuario("responsable-sci", "0571000001", "Responsable de estación", cls.estacion)
        cls.consulta = cls._usuario("consulta-sci", "0571000002", "Operador de consulta", cls.estacion)
        cls.otro = cls._usuario("otro-sci", "0571000003", "Responsable de estación", cls.otra_estacion)
        cls.otra_institucion = cls._usuario(
            "externo-sci", "0571000004", "Responsable institucional", cls.estacion_otra_institucion
        )
        cls.superusuario = get_user_model().objects.create_superuser(
            username="super-sci", cedula="0571000005", password="clave", estacion=None,
        )

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
            registrador_1="Usuario de Prueba", creado_por=self.usuario, modificado_por=self.usuario,
        )
        if completo:
            RegistroRecursoSCI211.objects.create(
                formulario=f, solicitado_por="CI Prueba", fecha_hora_solicitud=self.emergencia.fecha_reporte,
                clase_recurso="Vehículos", tipo_recurso="Autobomba", institucion_procedencia="Bomberos Prueba",
                matricula_identificacion="TEST-001", numero_personas=4, estado_recurso="disponible",
                asignado_a="Área de Espera", observaciones="Contenido <script>alert('x')</script> y ñ.",
            )
        return f

    def test_creacion_autorizada_y_borrador(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.post(reverse("emergencias:sci211_crear", args=[self.emergencia.pk]))
        self.assertEqual(respuesta.status_code, 302)
        formulario = FormularioSCI211.objects.get(emergencia=self.emergencia)
        self.assertEqual(formulario.estado, FormularioSCI211.Estado.BORRADOR)
        self.assertEqual(formulario.registrador_1, self.usuario.username)

        formulario.punto_registro = "Área de Espera editada"
        formulario.save(update_fields=("punto_registro",))
        segunda = self.client.post(reverse("emergencias:sci211_crear", args=[self.emergencia.pk]))
        self.assertEqual(segunda.status_code, 302)
        self.assertEqual(FormularioSCI211.objects.filter(emergencia=self.emergencia).count(), 1)
        formulario.refresh_from_db()
        self.assertEqual(formulario.punto_registro, "Área de Espera editada")

    def test_restriccion_unica_impide_duplicado(self):
        self.crear_formulario()
        with self.assertRaises(IntegrityError), transaction.atomic():
            FormularioSCI211.objects.create(
                emergencia=self.emergencia, codigo="SCI-211-DUPLICADO",
                punto_registro="Base", registrador_1="Prueba",
                creado_por=self.usuario, modificado_por=self.usuario,
            )

    def test_finalizacion_congela_datos_e_impide_edicion(self):
        formulario = finalizar_sci211(self.crear_formulario(), self.usuario)
        self.assertEqual(formulario.estado, FormularioSCI211.Estado.FINALIZADO)
        self.assertEqual(formulario.institucion_emitida, self.cuerpo.nombre)
        self.assertEqual(formulario.incidente_nombre_emitido, self.emergencia.tipo_emergencia)
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse("emergencias:sci211_editar", args=[formulario.pk])).status_code, 302)
        respuesta = self.client.post(reverse("emergencias:sci211_editar", args=[formulario.pk]), {"punto_registro": "ALTERADO"})
        self.assertEqual(respuesta.status_code, 302)
        formulario.refresh_from_db()
        self.assertEqual(formulario.punto_registro, "Puesto de Comando")
        self.assertNotContains(self.client.get(reverse("emergencias:sci211_detalle", args=[formulario.pk])), "Eliminar")

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
        self.assertEqual(self.client.get(reverse("emergencias:sci211_pdf", args=[formulario.pk])).status_code, 200)
        self.client.force_login(self.otra_institucion)
        self.assertEqual(self.client.get(reverse("emergencias:sci211_detalle", args=[formulario.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("emergencias:sci211_crear", args=[self.emergencia.pk])).status_code, 404)

    def test_acceso_anonimo_requiere_autenticacion(self):
        formulario = self.crear_formulario()
        for nombre, args in (
            ("sci211_lista", []), ("sci211_detalle", [formulario.pk]),
            ("sci211_editar", [formulario.pk]), ("sci211_finalizar", [formulario.pk]),
            ("sci211_pdf", [formulario.pk]), ("sci211_imprimir", [formulario.pk]),
        ):
            self.assertEqual(self.client.get(reverse(f"emergencias:{nombre}", args=args)).status_code, 302)

    def test_integracion_detalle_muestra_accion_estado_y_actualizacion(self):
        formulario = self.crear_formulario()
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:detalle", args=[self.emergencia.pk]))
        self.assertContains(respuesta, "SCI-211 - Registro y Control de Recursos")
        self.assertContains(respuesta, "Borrador")
        self.assertContains(respuesta, "Actualizado:")
        self.assertContains(respuesta, "Continuar SCI-211")
        finalizar_sci211(formulario, self.usuario)
        respuesta = self.client.get(reverse("emergencias:detalle", args=[self.emergencia.pk]))
        self.assertContains(respuesta, "Consultar SCI-211")
        self.assertContains(respuesta, "Descargar PDF")

    def test_menu_incluye_formularios_sci_y_marca_opcion_activa(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:lista"))
        self.assertContains(respuesta, "Formularios SCI")
        self.assertContains(respuesta, reverse("emergencias:sci211_lista"))
        respuesta = self.client.get(reverse("emergencias:sci211_lista"))
        self.assertContains(
            respuesta,
            f'href="{reverse("emergencias:sci211_lista")}" aria-current="page"',
            html=False,
        )

    def test_superusuario_sin_estacion_ve_boton_y_centro_de_formularios(self):
        formulario = self.crear_formulario()
        self.client.force_login(self.superusuario)
        respuesta = self.client.get(reverse("emergencias:lista"))
        self.assertContains(respuesta, "Formularios SCI")
        respuesta = self.client.get(reverse("emergencias:sci211_lista"))
        self.assertContains(respuesta, "Centro documental operativo")
        self.assertContains(respuesta, formulario.codigo)
        self.assertContains(respuesta, "Continuar edición")
        self.assertContains(respuesta, "Vista imprimible")
        self.assertContains(respuesta, "Descargar PDF")

    def test_catalogo_muestra_los_doce_formularios_y_sus_fichas(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:sci211_lista"))
        for codigo in ("201", "202", "203", "204", "205", "206", "207", "211", "214", "215", "221", "222"):
            self.assertContains(respuesta, f"SCI-{codigo}")
        self.assertContains(respuesta, "Vista informativa", count=11)
        self.assertContains(respuesta, "Operativo", count=1)

        ficha = self.client.get(reverse("emergencias:sci_catalogo_detalle", args=["205"]))
        self.assertEqual(ficha.status_code, 200)
        self.assertContains(ficha, "Plan de Comunicaciones")
        self.assertContains(ficha, "digitalización pendiente")

        inexistente = self.client.get(reverse("emergencias:sci_catalogo_detalle", args=["999"]))
        self.assertEqual(inexistente.status_code, 404)

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
        formulario = self.crear_formulario()
        html = render_to_string("emergencias/sci211/pdf.html", {"formulario": formulario})
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("Matrícula", html)
        pdf = generar_pdf_sci211(formulario)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 1000)
