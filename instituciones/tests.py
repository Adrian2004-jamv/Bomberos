from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .forms import CuerpoBomberosForm, EstacionForm
from .models import Canton, CuerpoBomberos, Estacion

class InterfazInstitucionesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.canton_uno = Canton.objects.create(nombre="Latacunga", codigo="LAT")
        cls.canton_dos = Canton.objects.create(nombre="Salcedo", codigo="SAL")
        cls.cuerpo_uno = CuerpoBomberos.objects.create(
            canton=cls.canton_uno,
            nombre="Cuerpo de Bomberos Latacunga",
            sigla="CBL",
            ruc="0590000000001",
            direccion="Av. Principal 100",
            telefono="032800000",
            correo="contacto@cbl.example",
            sitio_web="https://cbl.example",
        )
        cls.cuerpo_dos = CuerpoBomberos.objects.create(
            canton=cls.canton_dos,
            nombre="Cuerpo de Bomberos Salcedo",
            sigla="CBS",
            ruc="0590000000002",
            direccion="Calle Central 200",
        )
        cls.estacion_uno = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo_uno,
            nombre="Estación Central",
            codigo="E01",
            direccion="Av. Principal 100",
            latitud="-0.935000",
            longitud="-78.615000",
        )
        cls.estacion_dos = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo_dos,
            nombre="Estación Salcedo",
            codigo="E01",
            direccion="Calle Central 200",
            latitud="-1.043000",
            longitud="-78.590000",
        )
        usuario_model = get_user_model()
        cls.superusuario = usuario_model.objects.create_superuser(
            username="admin", cedula="0500000001", password="clave-segura"
        )
        cls.responsable = usuario_model.objects.create_user(
            username="provincial", cedula="0500000002", password="clave-segura"
        )
        grupo, _ = Group.objects.get_or_create(name="Responsable provincial")
        cls.responsable.groups.add(grupo)
        cls.usuario_normal = usuario_model.objects.create_user(
            username="estacion", cedula="0500000003", password="clave-segura",
            estacion=cls.estacion_uno,
        )
        cls.usuario_sin_estacion = usuario_model.objects.create_user(
            username="sin_estacion", cedula="0500000004", password="clave-segura"
        )

    @staticmethod
    def datos_cuerpo(**cambios):
        datos = {
            "canton": InterfazInstitucionesTests.canton_uno.pk,
            "nombre": "Cuerpo de Bomberos de Prueba",
            "sigla": "CBP",
            "ruc": "0590000000003",
            "direccion": "Dirección de prueba",
            "telefono": "032811111",
            "correo": "prueba@bomberos.example",
            "sitio_web": "https://bomberos.example",
            "activo": "on",
        }
        datos.update(cambios)
        return datos

    @staticmethod
    def datos_estacion(**cambios):
        datos = {
            "nombre": "Estación Norte",
            "codigo": "EN1",
            "direccion": "Sector norte",
            "telefono": "032822222",
            "latitud": "-0.900000",
            "longitud": "-78.600000",
            "activo": "on",
        }
        datos.update(cambios)
        return datos

    def test_usuario_no_autenticado_es_redirigido(self):
        respuesta = self.client.get(reverse("instituciones:lista"))
        self.assertRedirects(
            respuesta,
            f'{reverse("usuarios:login")}?next={reverse("instituciones:lista")}',
            fetch_redirect_response=False,
        )

    def test_superusuario_visualiza_todas_las_instituciones(self):
        self.client.force_login(self.superusuario)
        respuesta = self.client.get(reverse("instituciones:lista"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.cuerpo_uno.nombre)
        self.assertContains(respuesta, self.cuerpo_dos.nombre)

    def test_responsable_provincial_puede_crear_y_editar(self):
        self.client.force_login(self.responsable)
        respuesta = self.client.post(
            reverse("instituciones:crear_cuerpo"), self.datos_cuerpo()
        )
        creado = CuerpoBomberos.objects.get(sigla="CBP")
        self.assertRedirects(respuesta, reverse("instituciones:detalle", args=[creado.pk]))

        datos = self.datos_cuerpo(nombre="Institución actualizada")
        respuesta = self.client.post(
            reverse("instituciones:editar_cuerpo", args=[creado.pk]), datos
        )
        creado.refresh_from_db()
        self.assertEqual(creado.nombre, "Institución actualizada")
        self.assertRedirects(respuesta, reverse("instituciones:detalle", args=[creado.pk]))

    def test_usuario_normal_solo_consulta_su_institucion_y_estacion(self):
        self.client.force_login(self.usuario_normal)
        listado = self.client.get(reverse("instituciones:lista"))
        self.assertContains(listado, self.cuerpo_uno.nombre)
        self.assertNotContains(listado, self.cuerpo_dos.nombre)

        detalle = self.client.get(reverse("instituciones:detalle", args=[self.cuerpo_uno.pk]))
        self.assertContains(detalle, self.estacion_uno.nombre)
        self.assertNotContains(detalle, "Nueva estación")

    def test_usuario_normal_no_abre_otra_institucion_por_url(self):
        self.client.force_login(self.usuario_normal)
        respuesta = self.client.get(
            reverse("instituciones:detalle", args=[self.cuerpo_dos.pk])
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_usuario_normal_no_puede_crear(self):
        self.client.force_login(self.usuario_normal)
        respuesta = self.client.post(
            reverse("instituciones:crear_cuerpo"), self.datos_cuerpo()
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(CuerpoBomberos.objects.filter(sigla="CBP").exists())

    def test_usuario_sin_estacion_no_obtiene_acceso_indebido(self):
        self.client.force_login(self.usuario_sin_estacion)
        listado = self.client.get(reverse("instituciones:lista"))
        self.assertEqual(listado.status_code, 200)
        self.assertNotContains(listado, self.cuerpo_uno.nombre)
        detalle = self.client.get(reverse("instituciones:detalle", args=[self.cuerpo_uno.pk]))
        self.assertEqual(detalle.status_code, 404)

    def test_estacion_se_asocia_al_cuerpo_indicado_en_la_url(self):
        self.client.force_login(self.responsable)
        respuesta = self.client.post(
            reverse("instituciones:crear_estacion", args=[self.cuerpo_uno.pk]),
            self.datos_estacion(),
        )
        estacion = Estacion.objects.get(codigo="EN1")
        self.assertEqual(estacion.cuerpo_bomberos, self.cuerpo_uno)
        self.assertRedirects(
            respuesta, reverse("instituciones:detalle", args=[self.cuerpo_uno.pk])
        )

    def test_manipulacion_de_relacion_institucional_es_rechazada(self):
        self.client.force_login(self.responsable)
        respuesta = self.client.post(
            reverse("instituciones:crear_estacion", args=[self.cuerpo_uno.pk]),
            self.datos_estacion(cuerpo_bomberos=self.cuerpo_dos.pk),
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(Estacion.objects.filter(codigo="EN1").exists())

    def test_formularios_no_exponen_relacion_de_estacion(self):
        self.assertNotIn("cuerpo_bomberos", EstacionForm().fields)
        self.assertIn("canton", CuerpoBomberosForm().fields)

    def test_formularios_invalidos_muestran_errores(self):
        self.client.force_login(self.responsable)
        respuesta = self.client.post(
            reverse("instituciones:crear_estacion", args=[self.cuerpo_uno.pk]),
            self.datos_estacion(latitud="91", longitud="-181"),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Asegúrese de que este valor es menor o igual a 90")
        self.assertFalse(Estacion.objects.filter(codigo="EN1").exists())

    def test_rutas_de_consulta_y_formularios_responden(self):
        self.client.force_login(self.superusuario)
        rutas = (
            reverse("instituciones:lista"),
            reverse("instituciones:detalle", args=[self.cuerpo_uno.pk]),
            reverse("instituciones:crear_cuerpo"),
            reverse("instituciones:editar_cuerpo", args=[self.cuerpo_uno.pk]),
            reverse("instituciones:crear_estacion", args=[self.cuerpo_uno.pk]),
            reverse("instituciones:editar_estacion", args=[self.estacion_uno.pk]),
        )
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 200)
