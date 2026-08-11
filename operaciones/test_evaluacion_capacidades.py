from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso

from .models import (
    CalificacionPersonal,
    EspecialidadOperativa,
    EvaluacionCapacidadEstacion,
    PersonalOperativo,
    RequisitoPersonalCapacidad,
    RequisitoRecursoCapacidad,
    TipoCapacidadOperativa,
)
from .services import evaluar_capacidad_estacion


class EvaluarCapacidadEstacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Pujilí", codigo="PUJ")
        cuerpo = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Cuerpo de Bomberos de Pujilí",
            sigla="CBP",
            ruc="0590000000003",
            direccion="Pujilí",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo,
            nombre="Estación Central de Pujilí",
            codigo="ECP-01",
            direccion="Pujilí",
            latitud="-0.957590",
            longitud="-78.696360",
        )
        categoria = CategoriaRecurso.objects.create(nombre="Vehículos", codigo="VEH")
        cls.tipo_recurso = TipoRecurso.objects.create(
            categoria=categoria,
            nombre="Autobomba",
            codigo="AUT",
        )
        cls.especialidad = EspecialidadOperativa.objects.create(
            nombre="Combate de incendios estructurales",
            codigo="CIE",
        )
        cls.especialidad_adicional = EspecialidadOperativa.objects.create(
            nombre="Rescate vehicular",
            codigo="RV",
        )

    def crear_capacidad(self, codigo="CAP-TEST"):
        return TipoCapacidadOperativa.objects.create(
            nombre=f"Capacidad {codigo}",
            codigo=codigo,
        )

    def agregar_requisito_recurso(self, capacidad, cantidad=1, obligatorio=True):
        return RequisitoRecursoCapacidad.objects.create(
            capacidad=capacidad,
            tipo_recurso=self.tipo_recurso,
            cantidad_minima=cantidad,
            obligatorio=obligatorio,
        )

    def agregar_requisito_personal(
        self,
        capacidad,
        nivel=CalificacionPersonal.Nivel.BASICO,
        cantidad=1,
        obligatorio=True,
    ):
        return RequisitoPersonalCapacidad.objects.create(
            capacidad=capacidad,
            especialidad=self.especialidad,
            nivel_minimo=nivel,
            cantidad_minima=cantidad,
            obligatorio=obligatorio,
        )

    def crear_recurso(self, **cambios):
        numero = Recurso.objects.count() + 1
        datos = {
            "estacion": self.estacion,
            "tipo": self.tipo_recurso,
            "codigo_interno": f"REC-{numero:03d}",
            "nombre": f"Autobomba {numero}",
        }
        datos.update(cambios)
        return Recurso.objects.create(**datos)

    def crear_personal(self, disponibilidad=PersonalOperativo.Disponibilidad.DISPONIBLE):
        numero = PersonalOperativo.objects.count() + 1
        return PersonalOperativo.objects.create(
            estacion=self.estacion,
            codigo_institucional=f"PER-{numero:03d}",
            nombres=f"Persona {numero}",
            apellidos="Operativa",
            fecha_ingreso=timezone.localdate(),
            disponibilidad=disponibilidad,
        )

    def calificar(
        self,
        personal,
        especialidad=None,
        nivel=CalificacionPersonal.Nivel.BASICO,
        fecha_vencimiento=None,
    ):
        return CalificacionPersonal.objects.create(
            personal=personal,
            especialidad=especialidad or self.especialidad,
            nivel=nivel,
            fecha_emision=timezone.localdate() - timedelta(days=365),
            fecha_vencimiento=fecha_vencimiento,
        )

    def test_estacion_cumple_todos_los_requisitos(self):
        capacidad = self.crear_capacidad()
        self.agregar_requisito_recurso(capacidad)
        self.agregar_requisito_personal(capacidad)
        self.crear_recurso()
        self.calificar(self.crear_personal())

        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad)

        self.assertEqual(evaluacion.estado, EvaluacionCapacidadEstacion.Estado.CUMPLE)
        self.assertEqual(evaluacion.porcentaje_cumplimiento, Decimal("100.00"))

    def test_estacion_con_cumplimiento_parcial(self):
        capacidad = self.crear_capacidad()
        self.agregar_requisito_recurso(capacidad)
        self.agregar_requisito_personal(capacidad)
        self.crear_recurso()

        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad)

        self.assertEqual(evaluacion.estado, EvaluacionCapacidadEstacion.Estado.PARCIAL)
        self.assertEqual(evaluacion.porcentaje_cumplimiento, Decimal("50.00"))

    def test_estacion_no_cumple(self):
        capacidad = self.crear_capacidad()
        self.agregar_requisito_recurso(capacidad)
        self.agregar_requisito_personal(capacidad)

        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad)

        self.assertEqual(evaluacion.estado, EvaluacionCapacidadEstacion.Estado.NO_CUMPLE)
        self.assertEqual(evaluacion.porcentaje_cumplimiento, Decimal("0.00"))

    def test_recurso_en_mantenimiento_no_se_contabiliza(self):
        capacidad = self.crear_capacidad()
        self.agregar_requisito_recurso(capacidad)
        self.crear_recurso(estado_operativo=Recurso.EstadoOperativo.MANTENIMIENTO)

        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad)

        self.assertEqual(evaluacion.detalle_recursos[0]["cantidad_disponible"], 0)
        self.assertEqual(evaluacion.estado, EvaluacionCapacidadEstacion.Estado.NO_CUMPLE)

    def test_recurso_asignado_no_se_contabiliza(self):
        capacidad = self.crear_capacidad()
        self.agregar_requisito_recurso(capacidad)
        self.crear_recurso(disponibilidad=Recurso.Disponibilidad.ASIGNADO)

        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad)

        self.assertEqual(evaluacion.detalle_recursos[0]["cantidad_disponible"], 0)

    def test_personal_no_disponible_no_se_contabiliza(self):
        capacidad = self.crear_capacidad()
        self.agregar_requisito_personal(capacidad)
        personal = self.crear_personal(PersonalOperativo.Disponibilidad.DESCANSO)
        self.calificar(personal)

        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad)

        self.assertEqual(evaluacion.detalle_personal[0]["cantidad_disponible"], 0)

    def test_certificacion_vencida_no_se_contabiliza(self):
        capacidad = self.crear_capacidad()
        self.agregar_requisito_personal(capacidad)
        personal = self.crear_personal()
        self.calificar(
            personal,
            fecha_vencimiento=timezone.localdate() - timedelta(days=1),
        )

        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad)

        self.assertEqual(evaluacion.detalle_personal[0]["cantidad_disponible"], 0)

    def test_nivel_superior_es_aceptado(self):
        capacidad = self.crear_capacidad()
        self.agregar_requisito_personal(capacidad, nivel=CalificacionPersonal.Nivel.BASICO)
        personal = self.crear_personal()
        self.calificar(personal, nivel=CalificacionPersonal.Nivel.AVANZADO)

        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad)

        self.assertEqual(evaluacion.detalle_personal[0]["cantidad_disponible"], 1)
        self.assertEqual(evaluacion.estado, EvaluacionCapacidadEstacion.Estado.CUMPLE)

    def test_nivel_inferior_es_rechazado(self):
        capacidad = self.crear_capacidad()
        self.agregar_requisito_personal(capacidad, nivel=CalificacionPersonal.Nivel.AVANZADO)
        personal = self.crear_personal()
        self.calificar(personal, nivel=CalificacionPersonal.Nivel.BASICO)

        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad)

        self.assertEqual(evaluacion.detalle_personal[0]["cantidad_disponible"], 0)
        self.assertEqual(evaluacion.estado, EvaluacionCapacidadEstacion.Estado.NO_CUMPLE)

    def test_requisito_opcional_no_bloquea_estado_cumple(self):
        capacidad = self.crear_capacidad()
        self.agregar_requisito_recurso(capacidad, obligatorio=True)
        self.agregar_requisito_personal(capacidad, obligatorio=False)
        self.crear_recurso()

        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad)

        self.assertEqual(evaluacion.estado, EvaluacionCapacidadEstacion.Estado.CUMPLE)
        self.assertEqual(evaluacion.porcentaje_cumplimiento, Decimal("50.00"))

    def test_capacidad_sin_requisitos_genera_error(self):
        capacidad = self.crear_capacidad()

        with self.assertRaises(ValidationError):
            evaluar_capacidad_estacion(self.estacion, capacidad)

        self.assertFalse(EvaluacionCapacidadEstacion.objects.exists())

    def test_se_crean_varias_evaluaciones_historicas(self):
        capacidad = self.crear_capacidad()
        self.agregar_requisito_recurso(capacidad)

        primera = evaluar_capacidad_estacion(self.estacion, capacidad)
        segunda = evaluar_capacidad_estacion(self.estacion, capacidad)

        self.assertNotEqual(primera.pk, segunda.pk)
        self.assertEqual(EvaluacionCapacidadEstacion.objects.count(), 2)

    def test_persona_no_se_cuenta_dos_veces_en_un_requisito(self):
        capacidad = self.crear_capacidad()
        self.agregar_requisito_personal(capacidad, cantidad=2)
        personal = self.crear_personal()
        self.calificar(personal, especialidad=self.especialidad)
        self.calificar(personal, especialidad=self.especialidad_adicional)

        evaluacion = evaluar_capacidad_estacion(self.estacion, capacidad)

        self.assertEqual(evaluacion.detalle_personal[0]["cantidad_disponible"], 1)
        self.assertEqual(evaluacion.detalle_personal[0]["faltante"], 1)
