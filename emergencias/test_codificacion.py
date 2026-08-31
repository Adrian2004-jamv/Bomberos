"""Comprueba la codificación oficial de incidentes: II-DDMMAAAA-NNN."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion

from .codigos import (PATRON_CODIGO, codigo_fijo, generar_codigo_emergencia,
                      iniciales_tipo_emergencia)
from .models import Emergencia

class InicialesTests(TestCase):
    def test_toma_la_inicial_de_las_dos_primeras_palabras(self):
        self.assertEqual(iniciales_tipo_emergencia("Incendio estructural"), "IE")
        self.assertEqual(iniciales_tipo_emergencia("Incendio forestal"), "IF")

    def test_una_sola_palabra_usa_sus_dos_primeras_letras(self):
        self.assertEqual(iniciales_tipo_emergencia("Rescate"), "RE")

    def test_ignora_tildes_y_signos(self):
        self.assertEqual(iniciales_tipo_emergencia("Émergencia médica"), "EM")
        self.assertEqual(iniciales_tipo_emergencia("Rescate (vehicular)"), "RV")

    def test_palabra_de_una_letra_se_rellena(self):
        self.assertEqual(iniciales_tipo_emergencia("A"), "AX")

    def test_texto_vacio_cae_en_el_valor_neutro(self):
        self.assertEqual(iniciales_tipo_emergencia(""), "EM")
        self.assertEqual(iniciales_tipo_emergencia(None), "EM")

class CodigoEmergenciaTests(TestCase):
    def setUp(self):
        canton = Canton.objects.create(nombre="Latacunga", codigo="COD-T")
        cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Codificación", sigla="COD-T",
            ruc="0599999999009", direccion="Dirección institucional",
        )
        self.estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo, nombre="Estación Central", codigo="CEN-COD",
            direccion="Centro", latitud="-0.930000", longitud="-78.610000",
        )
        self.usuario = get_user_model().objects.create_user(
            username="registrador", password="clave-de-prueba", cedula="0500000001",
        )

    def _crear(self, tipo, fecha):
        return Emergencia.objects.create(
            codigo=generar_codigo_emergencia(tipo, fecha),
            tipo_emergencia=tipo,
            fecha_reporte=fecha,
            direccion="Dirección de prueba",
            estacion_responsable=self.estacion,
            registrado_por=self.usuario,
        )

    def test_el_primer_incidente_del_dia_arranca_en_001(self):
        fecha = timezone.now()
        emergencia = self._crear("Incendio estructural", fecha)
        esperado = f"IE-{timezone.localtime(fecha):%d%m%Y}-001"
        self.assertEqual(emergencia.codigo, esperado)
        self.assertRegex(emergencia.codigo, PATRON_CODIGO)

    def test_el_consecutivo_avanza_dentro_del_mismo_tipo_y_dia(self):
        fecha = timezone.now()
        codigos = [self._crear("Incendio estructural", fecha).codigo for _ in range(3)]
        self.assertEqual([codigo[-3:] for codigo in codigos], ["001", "002", "003"])

    def test_cada_tipo_lleva_su_propio_consecutivo(self):
        fecha = timezone.now()
        estructural = self._crear("Incendio estructural", fecha)
        forestal = self._crear("Incendio forestal", fecha)
        self.assertTrue(estructural.codigo.startswith("IE-"))
        self.assertTrue(forestal.codigo.startswith("IF-"))
        self.assertEqual(forestal.codigo[-3:], "001")

    def test_cada_dia_reinicia_el_consecutivo(self):
        hoy = timezone.now()
        self._crear("Incendio estructural", hoy)
        manana = self._crear("Incendio estructural", hoy + timedelta(days=1))
        self.assertEqual(manana.codigo[-3:], "001")

    def test_el_registro_por_la_vista_produce_un_codigo_valido(self):
        self.usuario.estacion = self.estacion
        self.usuario.save(update_fields=["estacion"])
        emergencia = self._crear("Rescate vehicular", timezone.now())
        self.assertRegex(emergencia.codigo, PATRON_CODIGO)

class CodigoFijoTests(TestCase):
    def test_es_reproducible_para_los_mismos_argumentos(self):
        fecha = timezone.now()
        self.assertEqual(
            codigo_fijo("Incendio estructural", fecha),
            codigo_fijo("Incendio estructural", fecha),
        )

    def test_cumple_el_patron_oficial(self):
        self.assertRegex(codigo_fijo("Incendio forestal", timezone.now()), PATRON_CODIGO)

    def test_no_consulta_la_base(self):
        fecha = timezone.now()
        with self.assertNumQueries(0):
            codigo_fijo("Incendio estructural", fecha)
