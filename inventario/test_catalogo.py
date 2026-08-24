"""Catálogo provincial de categorías y tipos de recurso.

Hasta ahora solo se editaba desde Django Admin. Estas pruebas cubren quién
puede tocarlo, qué se conserva al desactivar y el efecto de marcar un tipo como
unidad desplegable.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from instituciones.models import Canton, CuerpoBomberos, Estacion

from .models import CategoriaRecurso, Recurso, TipoRecurso


class BaseCatalogoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="LAT-CT")
        cls.cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Catálogo", sigla="CBC-CT",
            ruc="0596000000601", direccion="Centro",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo, nombre="Central Catálogo", codigo="CC-CT",
            direccion="Centro", latitud="-0.930000", longitud="-78.610000",
        )
        cls.categoria = CategoriaRecurso.objects.create(
            nombre="Vehículos", codigo="VEH-CT"
        )
        cls.tipo = TipoRecurso.objects.create(
            categoria=cls.categoria, nombre="Autobomba", codigo="AUT-CT"
        )
        cls.provincial = cls.crear_usuario(
            "provincial-ct", "0620000001", "Responsable provincial", None
        )
        cls.institucional = cls.crear_usuario(
            "institucional-ct", "0620000002", "Responsable institucional", cls.estacion
        )
        cls.inventario = cls.crear_usuario(
            "inventario-ct", "0620000003", "Encargado de inventario", cls.estacion
        )

    @classmethod
    def crear_usuario(cls, username, cedula, grupo, estacion):
        usuario = get_user_model().objects.create_user(
            username=username, cedula=cedula, password="clave", estacion=estacion
        )
        usuario.groups.add(Group.objects.get(name=grupo))
        return usuario


class AccesoAlCatalogoTests(BaseCatalogoTests):
    def test_el_alcance_provincial_entra(self):
        self.client.force_login(self.provincial)
        respuesta = self.client.get(reverse("inventario:catalogo"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Vehículos")
        self.assertContains(respuesta, "Autobomba")

    def test_un_responsable_institucional_no_edita_el_catalogo(self):
        """Los tipos los comparten todas las instituciones: una estación que
        inventara los suyos alteraría la medición de las demás."""
        self.client.force_login(self.institucional)
        for nombre in ("inventario:catalogo", "inventario:catalogo_categoria_crear",
                       "inventario:catalogo_tipo_crear"):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)

    def test_un_encargado_de_inventario_tampoco(self):
        self.client.force_login(self.inventario)
        self.assertEqual(self.client.get(reverse("inventario:catalogo")).status_code, 403)

    def test_acceso_anonimo_va_al_inicio_de_sesion(self):
        respuesta = self.client.get(reverse("inventario:catalogo"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("usuarios:login"), respuesta.headers["Location"])

    def test_el_menu_ofrece_los_catalogos_solo_al_alcance_provincial(self):
        self.client.force_login(self.provincial)
        self.assertContains(
            self.client.get(reverse("inventario:lista")), reverse("inventario:catalogo")
        )
        self.client.force_login(self.inventario)
        self.assertNotContains(
            self.client.get(reverse("inventario:lista")), reverse("inventario:catalogo")
        )


class CategoriasTests(BaseCatalogoTests):
    def test_crea_una_categoria_y_normaliza_su_codigo(self):
        self.client.force_login(self.provincial)
        respuesta = self.client.post(reverse("inventario:catalogo_categoria_crear"), {
            "nombre": "Herramientas", "codigo": " her ",
            "descripcion": "Herramienta manual y mecánica", "activo": "on",
        })
        self.assertRedirects(respuesta, reverse("inventario:catalogo"))
        categoria = CategoriaRecurso.objects.get(nombre="Herramientas")
        self.assertEqual(categoria.codigo, "HER")
        self.assertTrue(categoria.activo)

    def test_no_admite_un_codigo_repetido(self):
        self.client.force_login(self.provincial)
        respuesta = self.client.post(reverse("inventario:catalogo_categoria_crear"), {
            "nombre": "Otra", "codigo": "VEH-CT", "activo": "on",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(CategoriaRecurso.objects.filter(codigo="VEH-CT").count(), 1)

    def test_desactivar_conserva_los_tipos_que_dependen_de_ella(self):
        self.client.force_login(self.provincial)
        self.client.post(
            reverse("inventario:catalogo_categoria_editar", args=[self.categoria.pk]),
            {"nombre": self.categoria.nombre, "codigo": self.categoria.codigo},
        )
        self.categoria.refresh_from_db()
        self.tipo.refresh_from_db()
        self.assertFalse(self.categoria.activo)
        self.assertEqual(self.tipo.categoria, self.categoria)

    def test_el_catalogo_cuenta_los_recursos_de_cada_tipo(self):
        Recurso.objects.create(
            estacion=self.estacion, tipo=self.tipo,
            codigo_interno="AB-CT-01", nombre="Autobomba 1",
        )
        self.client.force_login(self.provincial)
        respuesta = self.client.get(reverse("inventario:catalogo"))
        categoria = respuesta.context["categorias"][0]
        self.assertEqual(categoria.tipos_recurso.all()[0].cantidad_recursos, 1)


class TiposDeRecursoTests(BaseCatalogoTests):
    def test_crea_un_tipo_marcado_como_unidad_desplegable(self):
        self.client.force_login(self.provincial)
        respuesta = self.client.post(reverse("inventario:catalogo_tipo_crear"), {
            "categoria": self.categoria.pk, "nombre": "Ambulancia",
            "codigo": "amb", "es_unidad_desplegable": "on", "activo": "on",
        })
        self.assertRedirects(respuesta, reverse("inventario:catalogo"))
        tipo = TipoRecurso.objects.get(nombre="Ambulancia")
        self.assertEqual(tipo.codigo, "AMB")
        self.assertTrue(tipo.es_unidad_desplegable)

    def test_solo_ofrece_categorias_activas_al_crear(self):
        inactiva = CategoriaRecurso.objects.create(
            nombre="Retirada", codigo="RET-CT", activo=False
        )
        self.client.force_login(self.provincial)
        respuesta = self.client.get(reverse("inventario:catalogo_tipo_crear"))
        opciones = respuesta.context["formulario"].fields["categoria"].queryset
        self.assertIn(self.categoria, opciones)
        self.assertNotIn(inactiva, opciones)

    def test_al_editar_conserva_su_categoria_aunque_este_inactiva(self):
        """Editar el nombre de un tipo no puede moverlo de categoría."""
        CategoriaRecurso.objects.filter(pk=self.categoria.pk).update(activo=False)
        self.client.force_login(self.provincial)
        respuesta = self.client.get(
            reverse("inventario:catalogo_tipo_editar", args=[self.tipo.pk])
        )
        self.assertIn(
            self.categoria, respuesta.context["formulario"].fields["categoria"].queryset
        )

    def test_marcar_desplegable_habilita_el_despacho(self):
        """Es el efecto real de la casilla: sin ella el recurso no se despacha."""
        self.client.force_login(self.provincial)
        self.client.post(
            reverse("inventario:catalogo_tipo_editar", args=[self.tipo.pk]),
            {"categoria": self.categoria.pk, "nombre": self.tipo.nombre,
             "codigo": self.tipo.codigo, "es_unidad_desplegable": "on", "activo": "on"},
        )
        self.tipo.refresh_from_db()
        self.assertTrue(self.tipo.es_unidad_desplegable)

    def test_no_admite_dos_codigos_iguales_en_la_misma_categoria(self):
        self.client.force_login(self.provincial)
        respuesta = self.client.post(reverse("inventario:catalogo_tipo_crear"), {
            "categoria": self.categoria.pk, "nombre": "Duplicado",
            "codigo": self.tipo.codigo, "activo": "on",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            TipoRecurso.objects.filter(
                categoria=self.categoria, codigo=self.tipo.codigo
            ).count(),
            1,
        )
