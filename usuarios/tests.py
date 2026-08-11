from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


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
            reverse("dashboard:principal"),
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
