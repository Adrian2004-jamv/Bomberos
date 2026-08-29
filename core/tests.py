from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import Recurso


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
            reverse("dashboard:principal"),
            fetch_redirect_response=False,
        )

    def test_usuario_autenticado_accede_al_inicio(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse("core:inicio"))

        self.assertRedirects(respuesta, reverse("dashboard:principal"))


class DatosCotopaxiTests(TestCase):
    def test_la_carga_es_repetible(self):
        call_command("cargar_datos_cotopaxi", verbosity=0)
        call_command("cargar_datos_cotopaxi", verbosity=0)

        self.assertEqual(Canton.objects.count(), 7)
        self.assertEqual(CuerpoBomberos.objects.count(), 1)

    def test_los_siete_cantones_quedan_disponibles(self):
        """La provincia entera es el ámbito, aunque solo opere Latacunga."""
        call_command("cargar_datos_cotopaxi", verbosity=0)
        self.assertEqual(Canton.objects.count(), 7)
        self.assertIn("Sigchos", Canton.objects.values_list("nombre", flat=True))

    def test_solo_se_precarga_el_cuerpo_de_bomberos_de_latacunga(self):
        call_command("cargar_datos_cotopaxi", verbosity=0)
        cuerpos = CuerpoBomberos.objects.all()
        self.assertEqual(cuerpos.count(), 1)
        self.assertEqual(cuerpos.get().nombre, "Cuerpo de Bomberos de Latacunga")
        self.assertEqual(cuerpos.get().canton.nombre, "Latacunga")

    def test_latacunga_tiene_sus_tres_estaciones(self):
        call_command("cargar_datos_cotopaxi", verbosity=0)
        estaciones = Estacion.objects.filter(
            cuerpo_bomberos__canton__codigo="LATACUNGA", activo=True
        )
        self.assertEqual(estaciones.count(), 3)
        self.assertEqual(len(set(estaciones.values_list("codigo", flat=True))), 3)

    def test_cada_estacion_recibe_sus_recursos_iniciales(self):
        call_command("cargar_datos_cotopaxi", verbosity=0)
        for estacion in Estacion.objects.all():
            self.assertEqual(estacion.recursos.count(), 3)


class PwaTests(TestCase):
    def test_manifiesto_publico_tiene_mime_y_contenido_requerido(self):
        respuesta = self.client.get(reverse("core:manifest"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/manifest+json")
        contenido = respuesta.json()
        for campo in ("id", "name", "short_name", "description", "start_url", "scope", "display", "background_color", "theme_color", "lang", "orientation", "icons"):
            self.assertIn(campo, contenido)
        self.assertEqual(contenido["start_url"], "/")
        self.assertEqual(contenido["scope"], "/")

    def test_iconos_declarados_existen_en_archivos_estaticos(self):
        for icono in self.client.get(reverse("core:manifest")).json()["icons"]:
            ruta = icono["src"].removeprefix("/static/")
            self.assertIsNotNone(finders.find(ruta), ruta)

    def test_service_worker_publico_tiene_mime_alcance_y_sin_cache_http(self):
        respuesta = self.client.get(reverse("core:service_worker"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta["Content-Type"].startswith("application/javascript"))
        self.assertEqual(respuesta["Service-Worker-Allowed"], "/")
        self.assertIn("no-cache", respuesta["Cache-Control"])

    def test_pagina_offline_es_publica_y_no_contiene_datos_privados(self):
        respuesta = self.client.get(reverse("core:sin_conexion"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Sin conexión con el servidor")
        self.assertContains(respuesta, "no deben considerarse guardadas")
        self.assertNotContains(respuesta, "csrfmiddlewaretoken")

    def test_base_incluye_manifiesto_tema_y_controles_pwa(self):
        fuente = (Path(settings.BASE_DIR) / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn('rel="manifest"', fuente)
        self.assertIn('name="theme-color"', fuente)
        self.assertIn('componentes/pwa_controles.html', fuente)

    def test_service_worker_excluye_endpoints_sensibles_y_html_privado(self):
        contenido = self.client.get(reverse("core:service_worker")).content.decode()
        for ruta in ("/emergencias/api/", "/mapa/datos/", "/mapa/recorridos/", "/ws/"):
            self.assertIn(ruta, contenido)
        self.assertIn('request.mode === "navigate"', contenido)
        self.assertIn("fetch(request).catch(() => caches.match(OFFLINE_URL))", contenido)
        self.assertNotIn("cache.put(request, response", contenido)

    def test_archivos_pwa_no_contienen_credenciales(self):
        archivos = (
            Path(settings.BASE_DIR) / "static" / "pwa" / "service-worker.js",
            Path(settings.BASE_DIR) / "static" / "js" / "app.js",
        )
        for archivo in archivos:
            contenido = archivo.read_text(encoding="utf-8").lower()
            for prohibido in ("postgres_password", "dj_database_url", "private key", "bearer "):
                self.assertNotIn(prohibido, contenido)
