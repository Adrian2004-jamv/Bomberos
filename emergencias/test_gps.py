import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso

from .models import DespliegueUnidad, Emergencia, PosicionUnidad
from .services import registrar_posicion_unidad


class PosicionesGPSTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="GPS-LAT")
        cls.cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos GPS", sigla="CB-GPS",
            ruc="0596000010001", direccion="Centro",
        )
        cls.cuerpo_ajeno = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Ajeno", sigla="CB-GPS-A",
            ruc="0596000010002", direccion="Sur",
        )
        cls.estacion = cls._estacion(cls.cuerpo, "GPS-01")
        cls.estacion_ajena = cls._estacion(cls.cuerpo_ajeno, "GPS-02")
        categoria = CategoriaRecurso.objects.create(nombre="Vehículos GPS", codigo="VEH-GPS")
        tipo = TipoRecurso.objects.create(
            categoria=categoria, nombre="Unidad GPS", codigo="UNI-GPS", es_unidad_desplegable=True,
        )
        cls.unidad = cls._unidad(cls.estacion, tipo, "U-GPS-01")
        cls.unidad_ajena = cls._unidad(cls.estacion_ajena, tipo, "U-GPS-02")
        cls.usuario = cls._usuario("gps-responsable", "0561000001", "Responsable de estación", cls.estacion)
        cls.consulta = cls._usuario("gps-consulta", "0561000002", "Operador de consulta", cls.estacion)
        cls.usuario_ajeno = cls._usuario("gps-ajeno", "0561000003", "Responsable de estación", cls.estacion_ajena)
        cls.emergencia = cls._emergencia("EM-GPS-01", cls.estacion, cls.usuario)
        cls.emergencia_ajena = cls._emergencia("EM-GPS-02", cls.estacion_ajena, cls.usuario_ajeno)
        cls.despliegue = cls._despliegue(cls.emergencia, cls.unidad, cls.usuario)
        cls.despliegue_ajeno = cls._despliegue(cls.emergencia_ajena, cls.unidad_ajena, cls.usuario_ajeno)

    @classmethod
    def _estacion(cls, cuerpo, codigo):
        return Estacion.objects.create(
            cuerpo_bomberos=cuerpo, nombre=f"Estación {codigo}", codigo=codigo,
            direccion="Centro", latitud="-0.933333", longitud="-78.616667",
        )

    @classmethod
    def _unidad(cls, estacion, tipo, codigo):
        return Recurso.objects.create(estacion=estacion, tipo=tipo, codigo_interno=codigo, nombre=codigo)

    @classmethod
    def _usuario(cls, username, cedula, grupo, estacion):
        usuario = get_user_model().objects.create_user(username=username, cedula=cedula, password="clave", estacion=estacion)
        usuario.groups.add(Group.objects.get(name=grupo))
        return usuario

    @classmethod
    def _emergencia(cls, codigo, estacion, usuario):
        return Emergencia.objects.create(
            codigo=codigo, tipo_emergencia="Incendio", direccion="Centro",
            estacion_responsable=estacion, registrado_por=usuario,
        )

    @classmethod
    def _despliegue(cls, emergencia, unidad, usuario, estado=DespliegueUnidad.Estado.EN_RUTA):
        return DespliegueUnidad.objects.create(
            emergencia=emergencia, unidad=unidad, estacion_procedencia=unidad.estacion,
            despachado_por=usuario, estado=estado,
        )

    def datos_validos(self, **cambios):
        datos = {"latitud": "-0.933333", "longitud": "-78.616667", "precision": "12.50", "velocidad": "4.250", "rumbo": "180.00", "altitud": "2750.00"}
        datos.update(cambios)
        return datos

    def crear_posicion(self, despliegue=None, usuario=None, **cambios):
        return registrar_posicion_unidad(despliegue or self.despliegue, usuario or self.usuario, **self.datos_validos(**cambios))

    def test_modelo_acepta_posicion_valida(self):
        posicion = PosicionUnidad(
            despliegue=self.despliegue, reportado_por=self.usuario,
            ubicacion=Point(-78.616667, -0.933333, srid=4326),
            precision="12.50", velocidad="4.250", rumbo="180.00", altitud="2750.00",
        )
        posicion.full_clean()
        self.assertEqual(posicion.ubicacion.srid, 4326)
        self.assertAlmostEqual(posicion.ubicacion.x, -78.616667)
        self.assertAlmostEqual(posicion.ubicacion.y, -0.933333)

    def test_modelo_rechaza_coordenadas_invalidas(self):
        for longitud, latitud in ((-78, 91), (-181, -1)):
            with self.subTest(longitud=longitud, latitud=latitud):
                posicion = PosicionUnidad(
                    despliegue=self.despliegue, reportado_por=self.usuario,
                    ubicacion=Point(longitud, latitud, srid=4326),
                )
                with self.assertRaises(ValidationError): posicion.full_clean()

    def test_modelo_rechaza_metadatos_invalidos(self):
        for campo, valor in (("precision", -1), ("velocidad", -1), ("rumbo", 361), ("rumbo", -1)):
            with self.subTest(campo=campo, valor=valor):
                metadatos = {"precision": "12.50", "velocidad": "4.250", "rumbo": "180.00"}
                metadatos[campo] = valor
                posicion = PosicionUnidad(
                    despliegue=self.despliegue, reportado_por=self.usuario,
                    ubicacion=Point(-78.616667, -0.933333, srid=4326), **metadatos,
                )
                with self.assertRaises(ValidationError): posicion.full_clean()

    def test_servicio_registra_y_conserva_historial(self):
        primera = self.crear_posicion()
        segunda = self.crear_posicion(latitud="-0.934000")
        self.assertEqual(self.despliegue.posiciones.count(), 2)
        self.assertEqual(primera.reportado_por, self.usuario)
        self.assertNotEqual(primera.pk, segunda.pk)
        self.assertEqual(primera.ubicacion.srid, 4326)
        self.assertAlmostEqual(primera.ubicacion.x, -78.616667)
        self.assertAlmostEqual(primera.ubicacion.y, -0.933333)

    def test_consulta_geografica_basica_con_postgis(self):
        posicion = self.crear_posicion()
        cercanas = PosicionUnidad.objects.filter(
            ubicacion__distance_lte=(Point(-78.6167, -0.9333, srid=4326), D(m=100))
        )
        self.assertIn(posicion, cercanas)

    def test_servicio_rechaza_fecha_exageradamente_adelantada(self):
        with self.assertRaises(ValidationError):
            self.crear_posicion(fecha_dispositivo=timezone.now() + timedelta(minutes=6))

    def test_servicio_rechaza_despliegue_finalizado(self):
        DespliegueUnidad.objects.filter(pk=self.despliegue.pk).update(estado=DespliegueUnidad.Estado.FINALIZADA)
        self.despliegue.refresh_from_db()
        with self.assertRaises(ValidationError): self.crear_posicion()

    def test_servicio_rechaza_emergencia_cerrada(self):
        Emergencia.objects.filter(pk=self.emergencia.pk).update(estado=Emergencia.Estado.CERRADA)
        self.emergencia.refresh_from_db()
        with self.assertRaises(ValidationError): self.crear_posicion()

    def test_servicio_rechaza_usuario_sin_autorizacion(self):
        with self.assertRaises(ValidationError): self.crear_posicion(usuario=self.consulta)
        with self.assertRaises(ValidationError): self.crear_posicion(usuario=self.usuario_ajeno)

    def post_url(self, despliegue=None):
        return reverse("emergencias:registrar_posicion", args=[(despliegue or self.despliegue).pk])

    def test_endpoint_exige_autenticacion(self):
        respuesta = self.client.post(self.post_url(), data=json.dumps(self.datos_validos()), content_type="application/json")
        self.assertEqual(respuesta.status_code, 401)

    def test_endpoint_rechaza_metodo_incorrecto(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(self.post_url()).status_code, 405)

    def test_endpoint_rechaza_contenido_no_json(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.post(self.post_url(), data={"latitud": 0})
        self.assertEqual(respuesta.status_code, 415)

    def test_endpoint_rechaza_usuario_sin_permiso_de_reporte(self):
        self.client.force_login(self.consulta)
        respuesta = self.client.post(self.post_url(), data=json.dumps(self.datos_validos()), content_type="application/json")
        self.assertEqual(respuesta.status_code, 403)

    def test_endpoint_rechaza_json_invalido(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.post(self.post_url(), data="{", content_type="application/json")
        self.assertEqual(respuesta.status_code, 400)

    def test_endpoint_tiene_proteccion_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        respuesta = cliente.post(self.post_url(), data=json.dumps(self.datos_validos()), content_type="application/json")
        self.assertEqual(respuesta.status_code, 403)

    def test_endpoint_registra_posicion(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.post(self.post_url(), data=json.dumps(self.datos_validos()), content_type="application/json")
        self.assertEqual(respuesta.status_code, 201)
        self.assertTrue(PosicionUnidad.objects.filter(pk=respuesta.json()["id"]).exists())

    def test_ultima_posicion_sin_datos(self):
        self.client.force_login(self.consulta)
        respuesta = self.client.get(reverse("emergencias:ultima_posicion", args=[self.despliegue.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.json()["disponible"])

    def test_ultima_posicion_selecciona_la_mas_reciente(self):
        primera = self.crear_posicion(latitud="-0.930000")
        segunda = self.crear_posicion(latitud="-0.940000")
        PosicionUnidad.objects.filter(pk=primera.pk).update(fecha_recepcion=timezone.now() + timedelta(seconds=1))
        self.client.force_login(self.consulta)
        respuesta = self.client.get(reverse("emergencias:ultima_posicion", args=[self.despliegue.pk]))
        self.assertAlmostEqual(respuesta.json()["latitud"], -0.93)
        self.assertAlmostEqual(respuesta.json()["longitud"], -78.616667)
        self.assertEqual(respuesta.json()["estado_despliegue"], DespliegueUnidad.Estado.EN_RUTA)
        self.assertNotEqual(primera.pk, segunda.pk)

    def test_no_consulta_despliegue_de_otra_institucion(self):
        self.client.force_login(self.consulta)
        url = reverse("emergencias:ultima_posicion", args=[self.despliegue_ajeno.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_pantalla_no_inicia_gps_automaticamente(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:transmitir_gps", args=[self.despliegue.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Iniciar transmisión")
        self.assertContains(respuesta, "Transmisión detenida")

    def test_pantalla_rechaza_operador_de_consulta(self):
        self.client.force_login(self.consulta)
        respuesta = self.client.get(reverse("emergencias:transmitir_gps", args=[self.despliegue.pk]))
        self.assertEqual(respuesta.status_code, 403)
