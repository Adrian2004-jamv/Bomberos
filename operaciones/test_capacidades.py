from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from inventario.models import CategoriaRecurso, TipoRecurso

from .models import (
    CalificacionPersonal,
    EspecialidadOperativa,
    RequisitoPersonalCapacidad,
    RequisitoRecursoCapacidad,
    TipoCapacidadOperativa,
)


class RequisitosCapacidadOperativaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
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
        cls.capacidad_uno = TipoCapacidadOperativa.objects.create(
            nombre="Respuesta a incendio estructural",
            codigo="CAP-CIE",
        )
        cls.capacidad_dos = TipoCapacidadOperativa.objects.create(
            nombre="Respuesta ampliada a incendio estructural",
            codigo="CAP-CIE-AMP",
        )

    def test_creacion_valida_de_capacidad(self):
        capacidad = TipoCapacidadOperativa.objects.create(
            nombre="Rescate vehicular",
            codigo="CAP-RV",
            descripcion="Capacidad de respuesta a siniestros vehiculares.",
        )

        self.assertEqual(str(capacidad), "CAP-RV - Rescate vehicular")
        self.assertTrue(capacidad.activo)

    def test_requisito_valido_de_recurso(self):
        requisito = RequisitoRecursoCapacidad.objects.create(
            capacidad=self.capacidad_uno,
            tipo_recurso=self.tipo_recurso,
            cantidad_minima=1,
        )

        self.assertEqual(requisito.cantidad_minima, 1)
        self.assertEqual(self.capacidad_uno.requisitos_recursos.get(), requisito)

    def test_requisito_valido_de_personal(self):
        requisito = RequisitoPersonalCapacidad.objects.create(
            capacidad=self.capacidad_uno,
            especialidad=self.especialidad,
            nivel_minimo=CalificacionPersonal.Nivel.INTERMEDIO,
            cantidad_minima=2,
        )

        self.assertEqual(requisito.cantidad_minima, 2)
        self.assertEqual(self.capacidad_uno.requisitos_personal.get(), requisito)

    def test_rechaza_cantidad_cero(self):
        requisito = RequisitoRecursoCapacidad(
            capacidad=self.capacidad_uno,
            tipo_recurso=self.tipo_recurso,
            cantidad_minima=0,
        )

        with self.assertRaises(ValidationError):
            requisito.full_clean()

    def test_rechaza_cantidad_negativa(self):
        requisito = RequisitoPersonalCapacidad(
            capacidad=self.capacidad_uno,
            especialidad=self.especialidad,
            nivel_minimo=CalificacionPersonal.Nivel.BASICO,
            cantidad_minima=-1,
        )

        with self.assertRaises(ValidationError):
            requisito.full_clean()

    def test_rechaza_tipo_recurso_duplicado_en_capacidad(self):
        RequisitoRecursoCapacidad.objects.create(
            capacidad=self.capacidad_uno,
            tipo_recurso=self.tipo_recurso,
            cantidad_minima=1,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RequisitoRecursoCapacidad.objects.create(
                    capacidad=self.capacidad_uno,
                    tipo_recurso=self.tipo_recurso,
                    cantidad_minima=2,
                )

    def test_rechaza_especialidad_y_nivel_duplicados(self):
        datos = {
            "capacidad": self.capacidad_uno,
            "especialidad": self.especialidad,
            "nivel_minimo": CalificacionPersonal.Nivel.AVANZADO,
            "cantidad_minima": 1,
        }
        RequisitoPersonalCapacidad.objects.create(**datos)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RequisitoPersonalCapacidad.objects.create(**datos)

    def test_tipo_recurso_puede_reutilizarse_en_capacidades_diferentes(self):
        primero = RequisitoRecursoCapacidad.objects.create(
            capacidad=self.capacidad_uno,
            tipo_recurso=self.tipo_recurso,
            cantidad_minima=1,
        )
        segundo = RequisitoRecursoCapacidad.objects.create(
            capacidad=self.capacidad_dos,
            tipo_recurso=self.tipo_recurso,
            cantidad_minima=2,
        )

        self.assertEqual(primero.tipo_recurso, segundo.tipo_recurso)
        self.assertNotEqual(primero.capacidad, segundo.capacidad)

    def test_protege_catalogos_utilizados(self):
        RequisitoRecursoCapacidad.objects.create(
            capacidad=self.capacidad_uno,
            tipo_recurso=self.tipo_recurso,
            cantidad_minima=1,
        )
        RequisitoPersonalCapacidad.objects.create(
            capacidad=self.capacidad_uno,
            especialidad=self.especialidad,
            nivel_minimo=CalificacionPersonal.Nivel.BASICO,
            cantidad_minima=1,
        )

        with self.assertRaises(ProtectedError):
            self.tipo_recurso.delete()
        with self.assertRaises(ProtectedError):
            self.especialidad.delete()
        with self.assertRaises(ProtectedError):
            self.capacidad_uno.delete()
