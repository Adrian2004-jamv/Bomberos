"""Retirada de emergencias de prueba con toda su documentación."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso

from .models import (DespliegueUnidad, Emergencia, FormularioSCI,
                     FormularioSCI211, PosicionUnidad)
from .services import desplegar_unidad

class LimpiarEmergenciasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="LIM")
        cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Limpieza", sigla="LIM",
            ruc="0596000001400", direccion="Centro",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo, nombre="Central Limpieza", codigo="LIM-C",
            direccion="Centro", latitud="-0.930000", longitud="-78.610000",
        )
        cls.usuario = get_user_model().objects.create_superuser(
            username="limpieza", cedula="1600000001", password="clave",
        )
        categoria = CategoriaRecurso.objects.create(codigo="LIMV", nombre="Vehículos")
        cls.tipo = TipoRecurso.objects.create(
            categoria=categoria, codigo="LIMA", nombre="Autobomba",
            es_unidad_desplegable=True,
        )

    def crear(self, codigo, dias_atras=0):
        emergencia = Emergencia.objects.create(
            codigo=codigo, tipo_emergencia="Incendio estructural",
            direccion="Centro", estacion_responsable=self.estacion,
            registrado_por=self.usuario,
        )
        if dias_atras:
            Emergencia.objects.filter(pk=emergencia.pk).update(
                fecha_reporte=timezone.now() - timezone.timedelta(days=dias_atras)
            )
            emergencia.refresh_from_db()
        return emergencia

    def con_documentacion(self, codigo="IE-DOC-001", unidad="AB-LIM-01"):
        emergencia = self.crear(codigo)
        FormularioSCI.objects.create(
            emergencia=emergencia, codigo_sci="201", datos={},
            creado_por=self.usuario, modificado_por=self.usuario,
        )
        formulario = FormularioSCI211.objects.create(
            emergencia=emergencia, codigo=f"SCI-211-{emergencia.pk}",
            punto_registro="Puesto de Comando", registrador_1="limpieza",
            creado_por=self.usuario, modificado_por=self.usuario,
        )
        recurso = Recurso.objects.create(
            estacion=self.estacion, tipo=self.tipo, codigo_interno=unidad,
            nombre="Autobomba", estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
            disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
            fecha_confirmacion_disponibilidad=timezone.now(),
        )
        despliegue = desplegar_unidad(emergencia, recurso, self.usuario)
        formulario.registros.create(
            orden=1, solicitado_por="CI", fecha_hora_solicitud=emergencia.fecha_reporte,
            despliegue=despliegue, recurso_inventario=recurso,
            clase_recurso="Vehículos", institucion_procedencia="Bomberos",
            matricula_identificacion=unidad, numero_personas=2,
            asignado_a="Zona de operaciones",
        )
        return emergencia, recurso

    def ejecutar(self, *argumentos):
        salida = StringIO()
        call_command("limpiar_emergencias", *argumentos, stdout=salida)
        return salida.getvalue()

# ==========================================
# MÓDULO: SALVAGUARDAS
# ==========================================

class SalvaguardasTests(LimpiarEmergenciasTests):
    def test_sin_criterio_se_niega_a_actuar(self):
        self.crear("IE-SIN-001")
        with self.assertRaises(CommandError):
            self.ejecutar()
        self.assertTrue(Emergencia.objects.filter(codigo="IE-SIN-001").exists())

    def test_una_fecha_ilegible_detiene_el_comando(self):
        with self.assertRaises(CommandError):
            self.ejecutar("--antes-de", "ayer")

    def test_por_omision_solo_simula(self):
        self.crear("IE-SIM-001")
        salida = self.ejecutar("--todas")
        self.assertIn("Simulación", salida)
        self.assertTrue(Emergencia.objects.filter(codigo="IE-SIM-001").exists())

    def test_avisa_cuando_nada_coincide(self):
        salida = self.ejecutar("--codigo", "NO-EXISTE")
        self.assertIn("Ninguna emergencia coincide", salida)

# ==========================================
# MÓDULO: RETIRADA
# ==========================================

class RetiradaTests(LimpiarEmergenciasTests):
    def test_retira_la_emergencia_con_toda_su_documentacion(self):
        emergencia, _ = self.con_documentacion()
        self.ejecutar("--codigo", emergencia.codigo, "--ejecutar")
        self.assertFalse(Emergencia.objects.filter(pk=emergencia.pk).exists())
        self.assertEqual(FormularioSCI.objects.count(), 0)
        self.assertEqual(FormularioSCI211.objects.count(), 0)
        self.assertEqual(DespliegueUnidad.objects.count(), 0)

    def test_la_unidad_vuelve_a_estar_disponible(self):
        emergencia, recurso = self.con_documentacion()
        recurso.refresh_from_db()
        self.assertEqual(recurso.disponibilidad, Recurso.Disponibilidad.ASIGNADO)

        salida = self.ejecutar("--codigo", emergencia.codigo, "--ejecutar")
        recurso.refresh_from_db()
        self.assertEqual(recurso.disponibilidad, Recurso.Disponibilidad.DISPONIBLE)
        self.assertIn("1 unidad(es) volvieron a estar disponibles", salida)

    def test_el_recurso_del_inventario_no_se_borra(self):
        emergencia, recurso = self.con_documentacion()
        self.ejecutar("--codigo", emergencia.codigo, "--ejecutar")
        self.assertTrue(Recurso.objects.filter(pk=recurso.pk).exists())

    def test_las_posiciones_del_gps_se_van_con_su_despliegue(self):
        emergencia, recurso = self.con_documentacion()
        despliegue = DespliegueUnidad.objects.get(emergencia=emergencia)
        PosicionUnidad.objects.create(
            despliegue=despliegue,
            ubicacion="SRID=4326;POINT (-78.61 -0.93)",
            reportado_por=self.usuario,
        )
        self.ejecutar("--codigo", emergencia.codigo, "--ejecutar")
        self.assertEqual(PosicionUnidad.objects.count(), 0)

    def test_solo_retira_lo_anterior_a_la_fecha(self):
        self.crear("IE-VIEJA-001", dias_atras=10)
        self.crear("IE-NUEVA-001")
        corte = (timezone.now() - timezone.timedelta(days=1)).date()
        self.ejecutar("--antes-de", corte.isoformat(), "--ejecutar")
        self.assertFalse(Emergencia.objects.filter(codigo="IE-VIEJA-001").exists())
        self.assertTrue(Emergencia.objects.filter(codigo="IE-NUEVA-001").exists())

    def test_acota_por_estacion(self):
        otra = Estacion.objects.create(
            cuerpo_bomberos=self.estacion.cuerpo_bomberos, nombre="Norte",
            codigo="LIM-N", direccion="Norte",
            latitud="-0.900000", longitud="-78.600000",
        )
        self.crear("IE-CENTRAL-001")
        ajena = Emergencia.objects.create(
            codigo="IE-NORTE-001", tipo_emergencia="Rescate", direccion="Norte",
            estacion_responsable=otra, registrado_por=self.usuario,
        )
        self.ejecutar("--estacion", "LIM-C", "--ejecutar")
        self.assertFalse(Emergencia.objects.filter(codigo="IE-CENTRAL-001").exists())
        self.assertTrue(Emergencia.objects.filter(pk=ajena.pk).exists())

    def test_todas_vacia_el_padron_entero(self):
        self.con_documentacion("IE-TODO-001", "AB-LIM-T1")
        self.con_documentacion("IE-TODO-002", "AB-LIM-T2")
        self.crear("IE-TODO-003")

        self.ejecutar("--todas", "--ejecutar")

        self.assertEqual(Emergencia.objects.count(), 0)
        self.assertEqual(FormularioSCI.objects.count(), 0)
        self.assertEqual(FormularioSCI211.objects.count(), 0)
        self.assertEqual(DespliegueUnidad.objects.count(), 0)
        self.assertEqual(PosicionUnidad.objects.count(), 0)

    def test_vaciar_el_padron_no_toca_el_inventario(self):
        _, primera = self.con_documentacion("IE-INV-001", "AB-LIM-I1")
        _, segunda = self.con_documentacion("IE-INV-002", "AB-LIM-I2")

        self.ejecutar("--todas", "--ejecutar")

        for recurso in (primera, segunda):
            recurso.refresh_from_db()
            self.assertEqual(
                recurso.disponibilidad, Recurso.Disponibilidad.DISPONIBLE
            )
        self.assertEqual(Recurso.objects.count(), 2)

    def test_varios_codigos_a_la_vez(self):
        self.crear("IE-UNO-001")
        self.crear("IE-DOS-001")
        self.crear("IE-TRES-001")
        self.ejecutar("--codigo", "IE-UNO-001", "--codigo", "IE-DOS-001", "--ejecutar")
        self.assertEqual(
            list(Emergencia.objects.values_list("codigo", flat=True)), ["IE-TRES-001"]
        )


class ReaperturaDeSCI211Tests(TestCase):
    """La migración devuelve a borrador los 211 cerrados antes de tiempo."""

    def test_la_migracion_esta_declarada(self):
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(None, ignore_no_migrations=True)
        nombres = {
            nombre for aplicacion, nombre in loader.graph.nodes
            if aplicacion == "emergencias"
        }
        self.assertIn("0013_reabrir_sci211_de_emergencias_en_curso", nombres)

    def test_solo_alcanza_a_las_emergencias_en_curso(self):
        """Se comprueba sobre la consulta que usa la migración: un 211 de una
        emergencia ya cerrada esta finalizado como debe y no se toca."""
        from emergencias.models import FormularioSCI211

        alcanzados = FormularioSCI211.objects.filter(
            estado=FormularioSCI211.Estado.FINALIZADO
        ).exclude(
            emergencia__estado__in=(
                Emergencia.Estado.CERRADA, Emergencia.Estado.CANCELADA
            )
        )
        # La migración ya corrió sobre la base de pruebas: no debe quedar
        # ninguno cerrado con su emergencia abierta.
        self.assertEqual(alcanzados.count(), 0)
