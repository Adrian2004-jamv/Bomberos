from unittest.mock import patch

from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.gis.geos import Point
from django.db import DatabaseError
from django.test import TestCase, TransactionTestCase

from emergencias.models import DespliegueUnidad, Emergencia, PosicionUnidad
from emergencias.services import registrar_posicion_unidad
from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso

from .consumers import MapaPosicionesConsumer, grupo_estacion

class ConsumidorMapaTests(TransactionTestCase):
    def setUp(self):
        canton = Canton.objects.create(nombre="Latacunga", codigo="WS-LAT")
        cuerpo_a = CuerpoBomberos.objects.create(canton=canton, nombre="WS A", sigla="CB-WS-A", ruc="0596000030001", direccion="A")
        cuerpo_b = CuerpoBomberos.objects.create(canton=canton, nombre="WS B", sigla="CB-WS-B", ruc="0596000030002", direccion="B")
        self.estacion_a1 = self._estacion(cuerpo_a, "WS-A1")
        self.estacion_a2 = self._estacion(cuerpo_a, "WS-A2")
        self.estacion_b = self._estacion(cuerpo_b, "WS-B1")
        self.institucional = self._usuario("ws-inst", "0563000001", "Responsable institucional", self.estacion_a1)
        self.estacion_user = self._usuario("ws-est", "0563000002", "Responsable de estación", self.estacion_a1)
        self.ajeno = self._usuario("ws-ajeno", "0563000003", "Responsable institucional", self.estacion_b)

    @staticmethod
    def _estacion(cuerpo, codigo):
        return Estacion.objects.create(cuerpo_bomberos=cuerpo, nombre=codigo, codigo=codigo, direccion="Centro", latitud="-0.93", longitud="-78.61")

    @staticmethod
    def _usuario(username, cedula, grupo, estacion):
        usuario = get_user_model().objects.create_user(username=username, cedula=cedula, password="clave", estacion=estacion)
        grupo_obj, _ = Group.objects.get_or_create(name=grupo)
        usuario.groups.add(grupo_obj)
        return usuario

    def comunicador(self, usuario):
        comunicador = WebsocketCommunicator(MapaPosicionesConsumer.as_asgi(), "/ws/mapa/posiciones/")
        comunicador.scope["user"] = usuario
        return comunicador

    async def test_rechaza_usuario_anonimo(self):
        comunicador = self.comunicador(AnonymousUser())
        conectado, codigo = await comunicador.connect()
        self.assertFalse(conectado)
        self.assertEqual(codigo, 4403)

    async def test_usuario_autorizado_conecta_y_desconecta(self):
        comunicador = self.comunicador(self.estacion_user)
        conectado, _ = await comunicador.connect()
        self.assertTrue(conectado)
        await comunicador.disconnect()

    async def test_responsable_estacion_recibe_solo_su_grupo(self):
        comunicador = self.comunicador(self.estacion_user)
        self.assertTrue((await comunicador.connect())[0])
        capa = get_channel_layer()
        await capa.group_send(grupo_estacion(self.estacion_a1.pk), {"type": "gps.posicion", "posicion": {"despliegue_id": 1}})
        self.assertEqual((await comunicador.receive_json_from())["posicion"]["despliegue_id"], 1)
        await capa.group_send(grupo_estacion(self.estacion_a2.pk), {"type": "gps.posicion", "posicion": {"despliegue_id": 2}})
        self.assertTrue(await comunicador.receive_nothing(timeout=0.1))
        await comunicador.disconnect()

    async def test_responsable_institucional_recibe_sus_estaciones_no_otra_institucion(self):
        comunicador = self.comunicador(self.institucional)
        self.assertTrue((await comunicador.connect())[0])
        capa = get_channel_layer()
        for estacion_id in (self.estacion_a1.pk, self.estacion_a2.pk):
            await capa.group_send(grupo_estacion(estacion_id), {"type": "gps.posicion", "posicion": {"despliegue_id": estacion_id}})
            self.assertEqual((await comunicador.receive_json_from())["tipo"], "posicion.actualizada")
        await capa.group_send(grupo_estacion(self.estacion_b.pk), {"type": "gps.posicion", "posicion": {"despliegue_id": 99}})
        self.assertTrue(await comunicador.receive_nothing(timeout=0.1))
        await comunicador.disconnect()

    async def test_mensajes_del_cliente_no_producen_comandos(self):
        comunicador = self.comunicador(self.estacion_user)
        self.assertTrue((await comunicador.connect())[0])
        await comunicador.send_json_to({"accion": "registrar_posicion", "latitud": 0})
        self.assertTrue(await comunicador.receive_nothing(timeout=0.1))
        await comunicador.disconnect()

class PublicacionPosicionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="PUB-LAT")
        cuerpo = CuerpoBomberos.objects.create(canton=canton, nombre="Publicación", sigla="CB-PUB", ruc="0596000031001", direccion="Centro")
        cls.estacion = Estacion.objects.create(cuerpo_bomberos=cuerpo, nombre="PUB-1", codigo="PUB-1", direccion="Centro", latitud="-0.93", longitud="-78.61")
        categoria = CategoriaRecurso.objects.create(nombre="Vehículo PUB", codigo="VEH-PUB")
        tipo = TipoRecurso.objects.create(categoria=categoria, nombre="Unidad PUB", codigo="UNI-PUB", es_unidad_desplegable=True)
        unidad = Recurso.objects.create(estacion=cls.estacion, tipo=tipo, codigo_interno="U-PUB", nombre="Unidad")
        cls.usuario = get_user_model().objects.create_user(username="pub-user", cedula="0563000100", password="clave", estacion=cls.estacion)
        cls.usuario.groups.add(Group.objects.get(name="Responsable de estación"))
        emergencia = Emergencia.objects.create(codigo="EM-PUB", tipo_emergencia="Incendio", direccion="Centro", estacion_responsable=cls.estacion, registrado_por=cls.usuario)
        cls.despliegue = DespliegueUnidad.objects.create(emergencia=emergencia, unidad=unidad, estacion_procedencia=cls.estacion, despachado_por=cls.usuario, estado=DespliegueUnidad.Estado.EN_RUTA)

    def registrar(self):
        return registrar_posicion_unidad(self.despliegue, self.usuario, latitud="-0.933", longitud="-78.616", precision="9.0", velocidad="2.5", rumbo="90")

    @patch("emergencias.realtime.publicar_posicion_gps")
    def test_publica_solo_despues_del_commit(self, publicar):
        with self.captureOnCommitCallbacks(execute=True):
            posicion = self.registrar()
            publicar.assert_not_called()
        publicar.assert_called_once_with(posicion)

    @patch("emergencias.realtime.publicar_posicion_gps")
    @patch.object(PosicionUnidad, "save", side_effect=DatabaseError("fallo simulado"))
    def test_no_publica_si_falla_la_transaccion(self, _guardar, publicar):
        with self.assertRaises(DatabaseError):
            self.registrar()
        publicar.assert_not_called()
        self.assertFalse(PosicionUnidad.objects.exists())

    def test_evento_publicado_tiene_estructura_minima(self):
        posicion = PosicionUnidad.objects.create(
            despliegue=self.despliegue, ubicacion=Point(-78.616, -0.933, srid=4326),
            precision="9", velocidad="2.5", rumbo="90", reportado_por=self.usuario,
        )
        with patch("emergencias.realtime.get_channel_layer") as obtener_capa, patch(
            "emergencias.realtime.async_to_sync"
        ) as convertir_async:
            capa = obtener_capa.return_value
            enviar = convertir_async.return_value
            from emergencias.realtime import publicar_posicion_gps
            publicar_posicion_gps(posicion)
            evento = enviar.call_args.args[1]["posicion"]
        self.assertEqual(set(evento), {
            "despliegue_id", "unidad", "emergencia_id", "emergencia", "longitud", "latitud",
            "precision", "velocidad", "rumbo", "estado", "fecha_recepcion",
        })
        self.assertEqual([evento["longitud"], evento["latitud"]], [-78.616, -0.933])
