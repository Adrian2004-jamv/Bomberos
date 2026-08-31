from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

class CrearSuperusuarioInicialTests(TestCase):
    """El arranque en Render depende de este comando: no hay consola."""

    ENTORNO = {
        "DJANGO_SUPERUSER_USERNAME": "admin-inicial",
        "DJANGO_SUPERUSER_PASSWORD": "clave-inicial-larga",
        "DJANGO_SUPERUSER_EMAIL": "admin@example.org",
        "DJANGO_SUPERUSER_CEDULA": "0599999999",
    }

    def ejecutar(self, **entorno):
        salida = StringIO()
        with self.settings():
            import os

            previos = {clave: os.environ.get(clave) for clave in self.ENTORNO}
            os.environ.update({k: v for k, v in entorno.items() if v is not None})
            for clave in self.ENTORNO:
                if clave not in entorno:
                    os.environ.pop(clave, None)
            try:
                call_command("crear_superusuario_inicial", stdout=salida)
            finally:
                for clave, valor in previos.items():
                    if valor is None:
                        os.environ.pop(clave, None)
                    else:
                        os.environ[clave] = valor
        return salida.getvalue()

    def test_crea_el_superusuario_con_los_datos_del_entorno(self):
        salida = self.ejecutar(**self.ENTORNO)
        usuario = get_user_model().objects.get(username="admin-inicial")
        self.assertTrue(usuario.is_superuser)
        self.assertTrue(usuario.is_staff)
        self.assertTrue(usuario.check_password("clave-inicial-larga"))
        self.assertEqual(usuario.cedula, "0599999999")
        self.assertIn("creado", salida)

    def test_no_crea_un_segundo_superusuario(self):
        self.ejecutar(**self.ENTORNO)
        otro = dict(self.ENTORNO, DJANGO_SUPERUSER_USERNAME="admin-duplicado",
                    DJANGO_SUPERUSER_CEDULA="0588888888")
        salida = self.ejecutar(**otro)
        self.assertFalse(get_user_model().objects.filter(username="admin-duplicado").exists())
        self.assertEqual(get_user_model().objects.filter(is_superuser=True).count(), 1)
        self.assertIn("Ya existe", salida)

    def test_sin_variables_no_crea_nada_y_no_falla(self):
        salida = self.ejecutar()
        self.assertFalse(get_user_model().objects.filter(is_superuser=True).exists())
        self.assertIn("no se crea", salida)

    def test_no_toca_la_clave_del_usuario_existente_sin_pedirlo(self):
        self.ejecutar(**self.ENTORNO)
        otra = dict(self.ENTORNO, DJANGO_SUPERUSER_PASSWORD="clave-distinta-nueva")
        salida = self.ejecutar(**otra)
        usuario = get_user_model().objects.get(username="admin-inicial")
        self.assertTrue(usuario.check_password("clave-inicial-larga"))
        self.assertIn("ya existe", salida.lower())

    def test_reinicia_la_clave_cuando_se_pide(self):
        """Unica via de recuperar el acceso en un entorno sin consola."""
        self.ejecutar(**self.ENTORNO)
        otra = dict(self.ENTORNO,
                    DJANGO_SUPERUSER_PASSWORD="clave-de-recuperacion",
                    DJANGO_SUPERUSER_REINICIAR_CLAVE="1")
        salida = self.ejecutar(**otra)
        usuario = get_user_model().objects.get(username="admin-inicial")
        self.assertTrue(usuario.check_password("clave-de-recuperacion"))
        self.assertTrue(usuario.is_superuser)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertIn("actualizada", salida)

    def test_reactiva_y_repromueve_al_reiniciar(self):
        self.ejecutar(**self.ENTORNO)
        get_user_model().objects.filter(username="admin-inicial").update(
            is_active=False, is_superuser=False, is_staff=False
        )
        otra = dict(self.ENTORNO, DJANGO_SUPERUSER_REINICIAR_CLAVE="1")
        self.ejecutar(**otra)
        usuario = get_user_model().objects.get(username="admin-inicial")
        self.assertTrue(usuario.is_active)
        self.assertTrue(usuario.is_superuser)
        self.assertTrue(usuario.is_staff)
