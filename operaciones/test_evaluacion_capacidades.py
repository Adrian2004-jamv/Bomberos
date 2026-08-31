from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso

from .models import EvaluacionCapacidadEstacion, RequisitoRecursoCapacidad, TipoCapacidadOperativa
from .services import evaluar_capacidad_estacion

class EvaluarCapacidadSoloRecursosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="LAT-ECR")
        cuerpo = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Cuerpo de Bomberos Latacunga",
            sigla="CBL-ECR",
            ruc="0593000000001",
            direccion="Latacunga",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo,
            nombre="Central",
            codigo="EC-ECR",
            direccion="Centro",
            latitud="-0.933333",
            longitud="-78.616667",
        )
        cls.otra_estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo,
            nombre="Norte",
            codigo="EN-ECR",
            direccion="Norte",
            latitud="-0.900000",
            longitud="-78.600000",
        )
        categoria = CategoriaRecurso.objects.create(nombre="Vehículos", codigo="VEH-ECR")
        cls.tipo = TipoRecurso.objects.create(categoria=categoria, nombre="Autobomba", codigo="AUT-ECR")
        cls.usuario = get_user_model().objects.create_user(
            username="evaluador-recursos", cedula="0530000001", password="clave"
        )

    def crear_capacidad(self, cantidad=2, obligatorio=True):
        capacidad = TipoCapacidadOperativa.objects.create(
            nombre=f"Capacidad {TipoCapacidadOperativa.objects.count() + 1}",
            codigo=f"CAP-ECR-{TipoCapacidadOperativa.objects.count() + 1}",
        )
        RequisitoRecursoCapacidad.objects.create(
            capacidad=capacidad,
            tipo_recurso=self.tipo,
            cantidad_minima=cantidad,
            obligatorio=obligatorio,
        )
        return capacidad

    def crear_recurso(
        self,
        codigo,
        estacion=None,
        estado=Recurso.EstadoOperativo.OPERATIVO,
        disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
        activo=True,
    ):
        return Recurso.objects.create(
            estacion=estacion or self.estacion,
            tipo=self.tipo,
            codigo_interno=codigo,
            nombre=f"Recurso {codigo}",
            estado_operativo=estado,
            disponibilidad=disponibilidad,
            activo=activo,
        )

    def test_capacidad_cumple_con_recursos_suficientes(self):
        capacidad = self.crear_capacidad(cantidad=2)
        self.crear_recurso("R-1")
        self.crear_recurso("R-2")
        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad, self.usuario)
        self.assertEqual(evaluacion.estado, EvaluacionCapacidadEstacion.Estado.CUMPLE)
        self.assertEqual(evaluacion.porcentaje_cumplimiento, Decimal("100.00"))

    def test_capacidad_no_cumple_cuando_faltan_recursos(self):
        capacidad = self.crear_capacidad(cantidad=2)
        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad, self.usuario)
        self.assertEqual(evaluacion.estado, EvaluacionCapacidadEstacion.Estado.NO_CUMPLE)
        self.assertEqual(evaluacion.detalle_recursos[0]["faltante"], 2)

    def test_recursos_de_otra_estacion_no_se_contabilizan(self):
        capacidad = self.crear_capacidad(cantidad=1)
        self.crear_recurso("R-OTRA", estacion=self.otra_estacion)
        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad, self.usuario)
        self.assertEqual(evaluacion.estado, EvaluacionCapacidadEstacion.Estado.NO_CUMPLE)
        self.assertEqual(evaluacion.detalle_recursos[0]["cantidad_encontrada"], 0)

    def test_recursos_fuera_de_servicio_no_se_contabilizan(self):
        capacidad = self.crear_capacidad(cantidad=1)
        self.crear_recurso("R-FS", estado=Recurso.EstadoOperativo.FUERA_SERVICIO)
        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad, self.usuario)
        self.assertEqual(evaluacion.detalle_recursos[0]["cantidad_encontrada"], 0)

    def test_recursos_no_disponibles_no_se_contabilizan(self):
        capacidad = self.crear_capacidad(cantidad=1)
        self.crear_recurso("R-ND", disponibilidad=Recurso.Disponibilidad.NO_DISPONIBLE)
        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad, self.usuario)
        self.assertEqual(evaluacion.detalle_recursos[0]["cantidad_encontrada"], 0)

    def test_recursos_inactivos_no_se_contabilizan(self):
        capacidad = self.crear_capacidad(cantidad=1)
        self.crear_recurso("R-INACTIVO", activo=False)
        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad, self.usuario)
        self.assertEqual(evaluacion.detalle_recursos[0]["cantidad_encontrada"], 0)

    def test_evaluacion_guarda_fotografia_historica_de_recursos(self):
        capacidad = self.crear_capacidad(cantidad=2)
        self.crear_recurso("R-HIST")
        evaluacion = evaluar_capacidad_estacion(
            self.estacion, capacidad, self.usuario, "Evaluación inicial"
        )
        detalle_original = evaluacion.detalle_recursos.copy()
        self.crear_recurso("R-POSTERIOR")
        evaluacion.refresh_from_db()
        self.assertEqual(evaluacion.detalle_recursos, detalle_original)
        self.assertEqual(detalle_original[0]["cantidad_requerida"], 2)
        self.assertEqual(detalle_original[0]["cantidad_encontrada"], 1)
        self.assertEqual(detalle_original[0]["faltante"], 1)
        self.assertEqual(evaluacion.evaluado_por, self.usuario)
        self.assertIsNotNone(evaluacion.fecha_evaluacion)

    def test_capacidad_sin_requisitos_genera_error(self):
        capacidad = TipoCapacidadOperativa.objects.create(nombre="Vacía", codigo="VAC-ECR")
        with self.assertRaises(ValidationError):
            evaluar_capacidad_estacion(self.estacion, capacidad, self.usuario)

    def test_se_conservan_multiples_evaluaciones_historicas(self):
        capacidad = self.crear_capacidad(cantidad=1)
        primera = evaluar_capacidad_estacion(self.estacion, capacidad, self.usuario)
        self.crear_recurso("R-CAMBIO")
        segunda = evaluar_capacidad_estacion(self.estacion, capacidad, self.usuario)
        self.assertEqual(EvaluacionCapacidadEstacion.objects.count(), 2)
        self.assertEqual(primera.estado, EvaluacionCapacidadEstacion.Estado.NO_CUMPLE)
        self.assertEqual(segunda.estado, EvaluacionCapacidadEstacion.Estado.CUMPLE)
