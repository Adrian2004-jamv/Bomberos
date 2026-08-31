from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from instituciones.models import Canton, CuerpoBomberos, Estacion

class AutenticacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "clave-segura-prueba"
        cls.usuario = get_user_model().objects.create_user(
            username="operador",
            cedula="0500000102",
            password=cls.password,
        )

    def test_login_muestra_formulario_y_token_csrf(self):
        respuesta = self.client.get(reverse("usuarios:login"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "usuarios/login.html")
        self.assertContains(respuesta, "csrfmiddlewaretoken")

    def test_credenciales_incorrectas_muestran_error(self):
        respuesta = self.client.post(
            reverse("usuarios:login"),
            {"username": self.usuario.username, "password": "incorrecta"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "El usuario o la contraseña no son correctos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_correcto_redirige_al_inicio(self):
        respuesta = self.client.post(
            reverse("usuarios:login"),
            {"username": self.usuario.username, "password": self.password},
        )

        self.assertRedirects(
            respuesta,
            reverse("emergencias:lista"),
            fetch_redirect_response=False,
        )
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_mediante_post_cierra_sesion_y_redirige(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.post(reverse("usuarios:logout"))

        self.assertRedirects(respuesta, reverse("usuarios:login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_mediante_get_no_cierra_sesion(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse("usuarios:logout"))

        self.assertEqual(respuesta.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_post_sin_csrf_es_rechazado(self):
        cliente_csrf = Client(enforce_csrf_checks=True)
        cliente_csrf.force_login(self.usuario)

        respuesta = cliente_csrf.post(reverse("usuarios:logout"))

        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("_auth_user_id", cliente_csrf.session)

class GestionUsuariosInstitucionalesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="USR-LAT")
        cuerpo_uno = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Latacunga", sigla="USR-CBL",
            ruc="0598000000001", direccion="Centro",
        )
        cuerpo_dos = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Salcedo", sigla="USR-CBS",
            ruc="0598000000002", direccion="Salcedo",
        )
        cls.estacion_uno = Estacion.objects.create(
            cuerpo_bomberos=cuerpo_uno, nombre="Central", codigo="USR-E1",
            direccion="Centro", latitud="-0.930000", longitud="-78.610000",
        )
        cls.estacion_uno_b = Estacion.objects.create(
            cuerpo_bomberos=cuerpo_uno, nombre="Norte", codigo="USR-E2",
            direccion="Norte", latitud="-0.920000", longitud="-78.600000",
        )
        cls.estacion_dos = Estacion.objects.create(
            cuerpo_bomberos=cuerpo_dos, nombre="Principal", codigo="USR-E3",
            direccion="Salcedo", latitud="-1.040000", longitud="-78.590000",
        )
        cls.grupo_sistemas = Group.objects.get(name="Operador de sistemas institucional")
        cls.grupo_consulta = Group.objects.get(name="Operador de consulta")
        cls.operador = get_user_model().objects.create_user(
            username="sistemas.latacunga", cedula="0582000091",
            password="ClaveSistemas!2026", estacion=cls.estacion_uno,
        )
        cls.operador.groups.add(cls.grupo_sistemas)
        cls.usuario_local = get_user_model().objects.create_user(
            username="consulta.latacunga", cedula="0582000092",
            password="ClaveConsulta!2026", estacion=cls.estacion_uno_b,
        )
        cls.usuario_ajeno = get_user_model().objects.create_user(
            username="consulta.salcedo", cedula="0582000093",
            password="ClaveConsulta!2026", estacion=cls.estacion_dos,
        )

    def setUp(self):
        self.client.force_login(self.operador)

    def test_lista_muestra_solo_usuarios_de_su_institucion(self):
        respuesta = self.client.get(reverse("usuarios:lista"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.usuario_local.username)
        self.assertNotContains(respuesta, self.usuario_ajeno.username)
        self.assertContains(respuesta, "Usuarios")

    def test_operador_crea_cuenta_en_una_estacion_de_su_institucion(self):
        respuesta = self.client.post(reverse("usuarios:crear"), {
            "username": "nuevo.operador",
            "first_name": "Nuevo",
            "last_name": "Operador",
            "cedula": "0582000094",
            "email": "nuevo@example.com",
            "telefono": "0999999999",
            "cargo_institucional": "Operador de consulta",
            "estacion": self.estacion_uno_b.pk,
            "grupo": self.grupo_consulta.pk,
            "password1": "CuentaSegura!2026",
            "password2": "CuentaSegura!2026",
        })
        self.assertRedirects(respuesta, reverse("usuarios:lista"))
        creado = get_user_model().objects.get(username="nuevo.operador")
        self.assertEqual(creado.estacion, self.estacion_uno_b)
        self.assertTrue(creado.groups.filter(pk=self.grupo_consulta.pk).exists())

    def test_no_puede_asignar_una_estacion_de_otro_canton(self):
        respuesta = self.client.post(reverse("usuarios:crear"), {
            "username": "usuario.ajeno",
            "cedula": "0582000095",
            "estacion": self.estacion_dos.pk,
            "grupo": self.grupo_consulta.pk,
            "password1": "CuentaSegura!2026",
            "password2": "CuentaSegura!2026",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["formulario"].errors["estacion"])
        self.assertFalse(get_user_model().objects.filter(username="usuario.ajeno").exists())

    def test_usuario_sin_permiso_recibe_403(self):
        self.client.force_login(self.usuario_local)
        self.assertEqual(self.client.get(reverse("usuarios:lista")).status_code, 403)
        self.assertEqual(self.client.get(reverse("usuarios:crear")).status_code, 403)
