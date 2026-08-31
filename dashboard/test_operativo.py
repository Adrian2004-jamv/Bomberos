"""El dashboard como tablero de la operación, no solo del inventario.

Comprueba los indicadores de incidentes y unidades, el tablero de incidentes
en curso y que todo respete el ámbito autorizado del usuario.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from emergencias.models import DespliegueUnidad, Emergencia
from emergencias.services import desplegar_unidad
from emergencias.services_sci import crear_sci211_desde_emergencia
from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso

class BaseOperativoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="LAT-OP")
        cls.cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Operativo", sigla="CBO-OP",
            ruc="0596000000301", direccion="Centro",
        )
        cls.cuerpo_ajeno = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Ajeno Op", sigla="CBAO-OP",
            ruc="0596000000302", direccion="Sur",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo, nombre="Central Operativa", codigo="CO-OP",
            direccion="Centro", latitud="-0.930000", longitud="-78.610000",
        )
        cls.estacion_ajena = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo_ajeno, nombre="Central Ajena Op", codigo="CAO-OP",
            direccion="Sur", latitud="-1.010000", longitud="-78.660000",
        )
        categoria = CategoriaRecurso.objects.create(nombre="Vehículos", codigo="VEH-OP")
        cls.tipo_unidad = TipoRecurso.objects.create(
            categoria=categoria, nombre="Autobomba", codigo="AUT-OP",
            es_unidad_desplegable=True,
        )
        cls.responsable = cls.crear_usuario(
            "responsable-op", "0590000001", "Responsable institucional", cls.estacion
        )
        cls.consulta = cls.crear_usuario(
            "consulta-op", "0590000002", "Operador de consulta", cls.estacion
        )
        cls.ajeno = cls.crear_usuario(
            "ajeno-op", "0590000003", "Responsable institucional", cls.estacion_ajena
        )

    @classmethod
    def crear_usuario(cls, username, cedula, grupo, estacion):
        usuario = get_user_model().objects.create_user(
            username=username, cedula=cedula, password="clave", estacion=estacion
        )
        usuario.groups.add(Group.objects.get(name=grupo))
        return usuario

    def crear_emergencia(self, codigo, estado=Emergencia.Estado.EN_ATENCION, estacion=None):
        return Emergencia.objects.create(
            codigo=codigo, tipo_emergencia="Incendio estructural",
            prioridad=Emergencia.Prioridad.ALTA, estado=estado,
            direccion="Centro de Latacunga", latitud="-0.933333", longitud="-78.616667",
            estacion_responsable=estacion or self.estacion,
            registrado_por=self.responsable,
        )

    def crear_unidad(self, codigo, estacion=None):
        return Recurso.objects.create(
            estacion=estacion or self.estacion, tipo=self.tipo_unidad,
            codigo_interno=codigo, nombre=f"Unidad {codigo}",
        )

    def abrir(self, usuario):
        self.client.force_login(usuario)
        return self.client.get(reverse("dashboard:principal"))

class IndicadoresOperativosTests(BaseOperativoTests):
    def test_cuenta_incidentes_en_curso_y_terminados(self):
        self.crear_emergencia("OP-001")
        self.crear_emergencia("OP-002", estado=Emergencia.Estado.REPORTADA)
        self.crear_emergencia("OP-003", estado=Emergencia.Estado.CERRADA)
        self.crear_emergencia("OP-004", estado=Emergencia.Estado.CANCELADA)
        operativo = self.abrir(self.responsable).context["operativo"]
        self.assertEqual(operativo["incidentes_en_curso"], 2)
        self.assertEqual(operativo["incidentes_atendidos"], 2)

    def test_cuenta_solo_las_unidades_que_siguen_en_el_incidente(self):
        emergencia = self.crear_emergencia("OP-010")
        desplegar_unidad(emergencia, self.crear_unidad("AB-OP-1"), self.responsable)
        terminado = desplegar_unidad(
            emergencia, self.crear_unidad("AB-OP-2"), self.responsable
        )
        DespliegueUnidad.objects.filter(pk=terminado.pk).update(
            estado=DespliegueUnidad.Estado.FINALIZADA
        )
        operativo = self.abrir(self.responsable).context["operativo"]
        self.assertEqual(operativo["unidades_desplegadas"], 1)

    def test_marca_los_incidentes_en_curso_sin_sci211(self):
        documentado = self.crear_emergencia("OP-020")
        self.crear_emergencia("OP-021")
        crear_sci211_desde_emergencia(documentado, self.responsable)
        operativo = self.abrir(self.responsable).context["operativo"]
        self.assertEqual(operativo["sin_documentar"], 1)

    def test_un_incidente_cerrado_sin_sci211_no_cuenta_como_pendiente(self):
        self.crear_emergencia("OP-030", estado=Emergencia.Estado.CERRADA)
        operativo = self.abrir(self.responsable).context["operativo"]
        self.assertEqual(operativo["sin_documentar"], 0)

    def test_los_indicadores_respetan_el_ambito(self):
        self.crear_emergencia("OP-040")
        self.crear_emergencia("OP-041", estacion=self.estacion_ajena)
        propio = self.abrir(self.responsable).context["operativo"]
        self.assertEqual(propio["incidentes_en_curso"], 1)
        ajeno = self.abrir(self.ajeno).context["operativo"]
        self.assertEqual(ajeno["incidentes_en_curso"], 1)

    def test_el_tablero_funciona_sin_ningun_incidente(self):
        respuesta = self.abrir(self.responsable)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["operativo"]["incidentes_en_curso"], 0)
        self.assertContains(respuesta, "No hay emergencias en curso en su ámbito.")

class TableroDeIncidentesTests(BaseOperativoTests):
    def test_muestra_el_incidente_con_sus_unidades_y_su_documentacion(self):
        emergencia = self.crear_emergencia("OP-100")
        desplegar_unidad(emergencia, self.crear_unidad("AB-OP-10"), self.responsable)
        respuesta = self.abrir(self.responsable)
        self.assertContains(respuesta, "OP-100")
        self.assertContains(respuesta, reverse("emergencias:detalle", args=[emergencia.pk]))
        self.assertContains(respuesta, "1 unidad")
        self.assertContains(respuesta, "Sin SCI-211")
        incidente = respuesta.context["incidentes_en_curso"][0]
        self.assertEqual(incidente.unidades_activas, 1)
        self.assertFalse(incidente.tiene_sci211)

    def test_un_incidente_documentado_no_se_marca_como_pendiente(self):
        emergencia = self.crear_emergencia("OP-110")
        crear_sci211_desde_emergencia(emergencia, self.responsable)
        respuesta = self.abrir(self.responsable)
        self.assertTrue(respuesta.context["incidentes_en_curso"][0].tiene_sci211)
        self.assertNotContains(respuesta, "Sin SCI-211")

    def test_no_incluye_incidentes_terminados(self):
        self.crear_emergencia("OP-120", estado=Emergencia.Estado.CERRADA)
        respuesta = self.abrir(self.responsable)
        self.assertEqual(list(respuesta.context["incidentes_en_curso"]), [])

    def test_el_tablero_esta_acotado_en_numero(self):
        for indice in range(9):
            self.crear_emergencia(f"OP-13{indice}")
        respuesta = self.abrir(self.responsable)
        self.assertEqual(len(respuesta.context["incidentes_en_curso"]), 6)

    def test_no_expone_incidentes_de_otra_institucion(self):
        self.crear_emergencia("OP-AJENO", estacion=self.estacion_ajena)
        respuesta = self.abrir(self.responsable)
        self.assertNotContains(respuesta, "OP-AJENO")

class ActividadYAccesosTests(BaseOperativoTests):
    def test_la_actividad_reciente_incluye_incidentes_y_despliegues(self):
        emergencia = self.crear_emergencia("OP-200")
        desplegar_unidad(emergencia, self.crear_unidad("AB-OP-20"), self.responsable)
        actividad = self.abrir(self.responsable).context["actividad_reciente"]
        tipos = {item["tipo"] for item in actividad}
        self.assertIn("Incidente", tipos)
        self.assertIn("Despliegue", tipos)

    def test_la_actividad_conserva_su_limite(self):
        for indice in range(12):
            self.crear_emergencia(f"OP-21{indice}")
        actividad = self.abrir(self.responsable).context["actividad_reciente"]
        self.assertEqual(len(actividad), 8)

    def test_los_accesos_rapidos_respetan_el_permiso_de_gestion(self):
        respuesta = self.abrir(self.responsable)
        self.assertContains(respuesta, "Registrar emergencia")
        self.assertContains(respuesta, "Mapa operativo")

        respuesta_consulta = self.abrir(self.consulta)
        self.assertNotContains(respuesta_consulta, "Registrar emergencia")
        self.assertContains(respuesta_consulta, "Mapa operativo")

    def test_una_cuenta_sin_ambito_no_ve_la_seccion_operativa(self):
        sin_ambito = get_user_model().objects.create_user(
            username="sin-ambito-op", cedula="0590000009", password="clave"
        )
        respuesta = self.abrir(sin_ambito)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context["puede_consultar_emergencias"])
        self.assertNotContains(respuesta, "Incidentes en curso")
