from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from emergencias.models import DespliegueUnidad, Emergencia, PosicionUnidad
from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso

from .services import clasificar_antiguedad

class MapaOperativoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="MAP-LAT")
        cls.cuerpo_a = cls._cuerpo(canton, "Mapa A", "CB-MA", "0596000020001")
        cls.cuerpo_b = cls._cuerpo(canton, "Mapa B", "CB-MB", "0596000020002")
        cls.estacion_a1 = cls._estacion(cls.cuerpo_a, "MA-1")
        cls.estacion_a2 = cls._estacion(cls.cuerpo_a, "MA-2")
        cls.estacion_b = cls._estacion(cls.cuerpo_b, "MB-1")
        categoria = CategoriaRecurso.objects.create(nombre="Vehículos mapa", codigo="VEH-MAP")
        tipo = TipoRecurso.objects.create(categoria=categoria, nombre="Autobomba mapa", codigo="AUT-MAP", es_unidad_desplegable=True)
        cls.unidad_a1 = cls._unidad(cls.estacion_a1, tipo, "MAP-A1")
        cls.unidad_a2 = cls._unidad(cls.estacion_a2, tipo, "MAP-A2")
        cls.unidad_b = cls._unidad(cls.estacion_b, tipo, "MAP-B1")
        cls.usuario_institucional = cls._usuario("map-inst", "0562000001", "Responsable institucional", cls.estacion_a1)
        cls.usuario_estacion = cls._usuario("map-est", "0562000002", "Responsable de estación", cls.estacion_a1)
        cls.usuario_consulta = cls._usuario("map-cons", "0562000003", "Operador de consulta", cls.estacion_a1)
        cls.usuario_b = cls._usuario("map-b", "0562000004", "Responsable institucional", cls.estacion_b)
        cls.emergencia_a1 = cls._emergencia("MAP-EM-A1", cls.estacion_a1, cls.usuario_institucional, "-0.933333", "-78.616667")
        cls.emergencia_a2 = cls._emergencia("MAP-EM-A2", cls.estacion_a2, cls.usuario_institucional)
        cls.emergencia_b = cls._emergencia("MAP-EM-B", cls.estacion_b, cls.usuario_b, "-1.000000", "-78.650000")
        cls.despliegue_a1 = cls._despliegue(cls.emergencia_a1, cls.unidad_a1, cls.usuario_institucional)
        cls.despliegue_a2 = cls._despliegue(cls.emergencia_a2, cls.unidad_a2, cls.usuario_institucional)
        cls.despliegue_b = cls._despliegue(cls.emergencia_b, cls.unidad_b, cls.usuario_b)

    @staticmethod
    def _cuerpo(canton, nombre, sigla, ruc):
        return CuerpoBomberos.objects.create(canton=canton, nombre=nombre, sigla=sigla, ruc=ruc, direccion="Centro")

    @staticmethod
    def _estacion(cuerpo, codigo):
        return Estacion.objects.create(cuerpo_bomberos=cuerpo, nombre=f"Estación {codigo}", codigo=codigo, direccion="Centro", latitud="-0.93", longitud="-78.61")

    @staticmethod
    def _unidad(estacion, tipo, codigo):
        return Recurso.objects.create(estacion=estacion, tipo=tipo, codigo_interno=codigo, nombre=f"Unidad {codigo}")

    @staticmethod
    def _usuario(username, cedula, grupo, estacion):
        usuario = get_user_model().objects.create_user(username=username, cedula=cedula, password="clave", estacion=estacion)
        usuario.groups.add(Group.objects.get(name=grupo))
        return usuario

    @staticmethod
    def _emergencia(codigo, estacion, usuario, latitud=None, longitud=None, estado=Emergencia.Estado.EN_ATENCION):
        return Emergencia.objects.create(codigo=codigo, tipo_emergencia="Incendio", prioridad=Emergencia.Prioridad.ALTA, estado=estado, direccion="Centro", latitud=latitud, longitud=longitud, estacion_responsable=estacion, registrado_por=usuario)

    @staticmethod
    def _despliegue(emergencia, unidad, usuario, estado=DespliegueUnidad.Estado.EN_RUTA):
        return DespliegueUnidad.objects.create(emergencia=emergencia, unidad=unidad, estacion_procedencia=unidad.estacion, despachado_por=usuario, estado=estado)

    @staticmethod
    def _posicion(despliegue, usuario, longitud, latitud, segundos=0):
        posicion = PosicionUnidad.objects.create(despliegue=despliegue, ubicacion=Point(longitud, latitud, srid=4326), precision="8.00", velocidad="3.500", reportado_por=usuario)
        if segundos:
            PosicionUnidad.objects.filter(pk=posicion.pk).update(fecha_recepcion=timezone.now() + timedelta(seconds=segundos))
            posicion.refresh_from_db()
        return posicion

    def datos(self, usuario=None, parametros=""):
        self.client.force_login(usuario or self.usuario_institucional)
        return self.client.get(f"{reverse('mapas:datos')}{parametros}")

    def features(self, respuesta, clase):
        return [item for item in respuesta.json()["features"] if item["properties"]["clase"] == clase]

    def test_mapa_exige_autenticacion_y_carga_para_usuario_autorizado(self):
        self.assertEqual(self.client.get(reverse("mapas:operativo")).status_code, 302)
        self.client.force_login(self.usuario_consulta)
        respuesta = self.client.get(reverse("mapas:operativo"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Mapa operativo")

    def test_endpoint_geojson_exige_autenticacion(self):
        self.assertEqual(self.client.get(reverse("mapas:datos")).status_code, 401)

    def test_restriccion_institucional(self):
        respuesta = self.datos()
        codigos = {item["properties"].get("emergencia", item["properties"].get("codigo")) for item in respuesta.json()["features"]}
        self.assertIn(self.emergencia_a1.codigo, codigos)
        self.assertNotIn(self.emergencia_b.codigo, codigos)

    def test_restriccion_por_estacion(self):
        respuesta = self.datos(self.usuario_estacion)
        unidades = {item["properties"]["unidad"] for item in self.features(respuesta, "unidad")}
        self.assertEqual(unidades, {self.unidad_a1.codigo_interno})

    def test_excluye_emergencia_cerrada(self):
        Emergencia.objects.filter(pk=self.emergencia_a1.pk).update(estado=Emergencia.Estado.CERRADA)
        respuesta = self.datos()
        self.assertNotIn(self.emergencia_a1.codigo, {item["properties"]["codigo"] for item in self.features(respuesta, "emergencia")})

    def test_excluye_despliegue_finalizado(self):
        DespliegueUnidad.objects.filter(pk=self.despliegue_a1.pk).update(estado=DespliegueUnidad.Estado.FINALIZADA)
        respuesta = self.datos()
        self.assertNotIn(self.unidad_a1.codigo_interno, {item["properties"]["unidad"] for item in self.features(respuesta, "unidad")})

    def test_emergencia_activa_con_coordenadas_respeta_orden_geojson(self):
        feature = next(item for item in self.features(self.datos(), "emergencia") if item["properties"]["codigo"] == self.emergencia_a1.codigo)
        self.assertEqual(feature["geometry"]["coordinates"], [-78.616667, -0.933333])

    def test_unidad_utiliza_ultima_posicion(self):
        self._posicion(self.despliegue_a1, self.usuario_institucional, -78.61, -0.93, -20)
        self._posicion(self.despliegue_a1, self.usuario_institucional, -78.62, -0.94)
        feature = next(item for item in self.features(self.datos(), "unidad") if item["properties"]["unidad"] == self.unidad_a1.codigo_interno)
        self.assertEqual(feature["geometry"]["coordinates"], [-78.62, -0.94])

    def test_unidad_sin_posicion_permanece_en_lista_geojson(self):
        feature = next(item for item in self.features(self.datos(), "unidad") if item["properties"]["unidad"] == self.unidad_a2.codigo_interno)
        self.assertIsNone(feature["geometry"])
        self.assertEqual(feature["properties"]["antiguedad"]["codigo"], "sin_posicion")

    def test_clasificacion_antiguedad(self):
        ahora = timezone.now()
        self.assertEqual(clasificar_antiguedad(ahora - timedelta(seconds=30), ahora)["codigo"], "reciente")
        self.assertEqual(clasificar_antiguedad(ahora - timedelta(seconds=120), ahora)["codigo"], "retraso")
        self.assertEqual(clasificar_antiguedad(ahora - timedelta(seconds=600), ahora)["codigo"], "desactualizada")

    def test_recorrido_ordenado_y_limitado_al_despliegue(self):
        primera = self._posicion(self.despliegue_a1, self.usuario_institucional, -78.61, -0.93, -20)
        segunda = self._posicion(self.despliegue_a1, self.usuario_institucional, -78.62, -0.94)
        self._posicion(self.despliegue_a2, self.usuario_institucional, -78.70, -0.80)
        self.client.force_login(self.usuario_institucional)
        respuesta = self.client.get(reverse("mapas:recorrido", args=[self.despliegue_a1.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["geometry"]["coordinates"], [[primera.ubicacion.x, primera.ubicacion.y], [segunda.ubicacion.x, segunda.ubicacion.y]])
        self.assertEqual(respuesta.json()["properties"]["cantidad_puntos"], 2)

    def test_recorrido_cero_y_una_posicion(self):
        self.client.force_login(self.usuario_institucional)
        sin_datos = self.client.get(reverse("mapas:recorrido", args=[self.despliegue_a1.pk])).json()
        self.assertIsNone(sin_datos["geometry"])
        self._posicion(self.despliegue_a1, self.usuario_institucional, -78.61, -0.93)
        un_dato = self.client.get(reverse("mapas:recorrido", args=[self.despliegue_a1.pk])).json()
        self.assertEqual(un_dato["geometry"]["type"], "Point")

    def test_rechaza_recorrido_de_otra_institucion(self):
        self.client.force_login(self.usuario_institucional)
        self.assertEqual(self.client.get(reverse("mapas:recorrido", args=[self.despliegue_b.pk])).status_code, 404)

    def test_filtro_manipulado_no_amplia_permisos(self):
        respuesta = self.datos(parametros=f"?cuerpo={self.cuerpo_b.pk}&estacion={self.estacion_b.pk}&emergencia={self.emergencia_b.pk}")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["features"], [])

    def test_filtro_invalido_devuelve_400(self):
        self.assertEqual(self.datos(parametros="?estado=inventado").status_code, 400)
        self.assertEqual(self.datos(parametros="?estacion=no-numero").status_code, 400)

    def test_funciona_sin_emergencias_activas(self):
        Emergencia.objects.all().update(estado=Emergencia.Estado.CERRADA)
        self.assertEqual(self.datos().json()["features"], [])
