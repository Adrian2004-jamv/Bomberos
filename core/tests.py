from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class InicioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="usuario.core",
            cedula="0500000101",
            password="clave-segura-prueba",
        )

    def test_usuario_no_autenticado_es_redirigido_al_login(self):
        respuesta = self.client.get(reverse("core:inicio"))

        self.assertRedirects(
            respuesta,
            f'{reverse("usuarios:login")}?next={reverse("core:inicio")}',
        )

    def test_usuario_autenticado_accede_al_inicio(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse("core:inicio"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "core/inicio.html")
        self.assertContains(respuesta, self.usuario.username)
        self.assertContains(respuesta, "Centro de gestión provincial")
