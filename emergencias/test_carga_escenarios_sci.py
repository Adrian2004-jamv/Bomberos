from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase

from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import Recurso

from emergencias.codigos import PATRON_CODIGO
from emergencias.models import DespliegueUnidad, Emergencia, FormularioSCI, FormularioSCI211
from emergencias.views import CATALOGO_FORMULARIOS_SCI, emergencias_permitidas, preparar_avance_documental

class CargaEscenariosSCITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="SCI-ESC")
        cuerpo = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Cuerpo de Bomberos de Latacunga",
            sigla="CBL-ESC",
            ruc="0595000000001",
            direccion="Latacunga",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo,
            nombre="Estación Central",
            codigo="SCI-EST",
            direccion="Latacunga",
            latitud="-0.935000",
            longitud="-78.615000",
        )
        cls.usuario = get_user_model().objects.create_user(
            username="comandante.latacunga",
            cedula="0581000099",
            password="ClaveSegura!2026",
            estacion=cls.estacion,
        )
        cls.usuario.groups.add(Group.objects.get(name="Responsable provincial"))

    DIRECCION_COMPLETA = "Sector El Salto, zona urbana de Latacunga"
    DIRECCION_INCOMPLETA = "Sector Loma Grande, parroquia Aláquez, Latacunga"

    def ejecutar_carga(self):
        call_command("cargar_inventario_bomberil", stdout=StringIO())
        call_command("cargar_escenarios_sci", stdout=StringIO())

    def test_crea_un_incidente_completo_y_otro_parcial(self):
        self.ejecutar_carga()
        completa = Emergencia.objects.get(direccion=self.DIRECCION_COMPLETA)
        incompleta = Emergencia.objects.get(direccion=self.DIRECCION_INCOMPLETA)

        self.assertRegex(completa.codigo, PATRON_CODIGO)
        self.assertRegex(incompleta.codigo, PATRON_CODIGO)
        self.assertTrue(completa.codigo.startswith("IE-"))
        self.assertTrue(incompleta.codigo.startswith("IF-"))

        self.assertEqual(completa.estado, Emergencia.Estado.CERRADA)
        self.assertEqual(FormularioSCI.objects.filter(emergencia=completa).count(), 11)
        self.assertTrue(all(
            valor.strip()
            for formulario in FormularioSCI.objects.filter(emergencia=completa)
            for valor in formulario.datos.values()
        ))
        self.assertEqual(completa.formulario_sci_211.estado, FormularioSCI211.Estado.FINALIZADO)
        self.assertEqual(completa.formulario_sci_211.registros.count(), 2)

        self.assertEqual(incompleta.estado, Emergencia.Estado.EN_ATENCION)
        self.assertEqual(FormularioSCI.objects.filter(emergencia=incompleta).count(), 3)
        self.assertEqual(incompleta.formulario_sci_211.estado, FormularioSCI211.Estado.BORRADOR)
        self.assertEqual(incompleta.formulario_sci_211.registros.count(), 1)
        self.assertTrue(incompleta.despliegues.filter(estado=DespliegueUnidad.Estado.EN_SITIO).exists())
        self.assertEqual(Recurso.objects.get(codigo_interno="AB-01").disponibilidad, Recurso.Disponibilidad.ASIGNADO)

    def test_el_avance_visible_es_100_y_33_por_ciento(self):
        self.ejecutar_carga()
        emergencias = preparar_avance_documental(list(emergencias_permitidas(self.usuario)))
        por_direccion = {emergencia.direccion: emergencia for emergencia in emergencias}

        self.assertEqual(len(CATALOGO_FORMULARIOS_SCI), 12)
        self.assertEqual(por_direccion[self.DIRECCION_COMPLETA].formularios_completados, 12)
        self.assertEqual(por_direccion[self.DIRECCION_COMPLETA].porcentaje_formularios, 100)
        self.assertEqual(por_direccion[self.DIRECCION_INCOMPLETA].formularios_completados, 4)
        self.assertEqual(por_direccion[self.DIRECCION_INCOMPLETA].porcentaje_formularios, 33)

    def test_carga_es_idempotente(self):
        self.ejecutar_carga()
        call_command("cargar_escenarios_sci", stdout=StringIO())

        direcciones = (self.DIRECCION_COMPLETA, self.DIRECCION_INCOMPLETA)
        self.assertEqual(Emergencia.objects.filter(direccion__in=direcciones).count(), 2)
        self.assertEqual(
            FormularioSCI.objects.filter(emergencia__direccion=self.DIRECCION_COMPLETA).count(), 11
        )
        self.assertEqual(
            FormularioSCI.objects.filter(emergencia__direccion=self.DIRECCION_INCOMPLETA).count(), 3
        )
        self.assertEqual(
            DespliegueUnidad.objects.filter(emergencia__direccion=self.DIRECCION_INCOMPLETA).count(), 1
        )
