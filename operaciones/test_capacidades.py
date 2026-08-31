from django.db import IntegrityError, transaction
from django.test import TestCase

from inventario.models import CategoriaRecurso, TipoRecurso

from .models import RequisitoRecursoCapacidad, TipoCapacidadOperativa

class RequisitosCapacidadOperativaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = CategoriaRecurso.objects.create(nombre="Vehículos", codigo="VEH-CAP")
        cls.tipo_autobomba = TipoRecurso.objects.create(
            categoria=categoria, nombre="Autobomba", codigo="AUT-CAP"
        )
        cls.capacidad_uno = TipoCapacidadOperativa.objects.create(
            nombre="Combate estructural", codigo="CE-CAP"
        )
        cls.capacidad_dos = TipoCapacidadOperativa.objects.create(
            nombre="Apoyo hídrico", codigo="AH-CAP"
        )

    def test_creacion_valida_de_capacidad(self):
        self.assertEqual(str(self.capacidad_uno), "CE-CAP - Combate estructural")

    def test_requisito_valido_de_recurso(self):
        requisito = RequisitoRecursoCapacidad.objects.create(
            capacidad=self.capacidad_uno,
            tipo_recurso=self.tipo_autobomba,
            cantidad_minima=2,
        )
        requisito.full_clean()
        self.assertEqual(self.capacidad_uno.requisitos_recursos.get(), requisito)

    def test_rechaza_cantidad_cero_y_negativa(self):
        for cantidad in (0, -1):
            requisito = RequisitoRecursoCapacidad(
                capacidad=self.capacidad_uno,
                tipo_recurso=self.tipo_autobomba,
                cantidad_minima=cantidad,
            )
            with self.subTest(cantidad=cantidad), self.assertRaises(Exception):
                requisito.full_clean()

    def test_rechaza_tipo_recurso_duplicado_en_capacidad(self):
        RequisitoRecursoCapacidad.objects.create(
            capacidad=self.capacidad_uno,
            tipo_recurso=self.tipo_autobomba,
            cantidad_minima=1,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RequisitoRecursoCapacidad.objects.create(
                    capacidad=self.capacidad_uno,
                    tipo_recurso=self.tipo_autobomba,
                    cantidad_minima=2,
                )

    def test_tipo_recurso_puede_reutilizarse_en_capacidades_diferentes(self):
        primero = RequisitoRecursoCapacidad.objects.create(
            capacidad=self.capacidad_uno,
            tipo_recurso=self.tipo_autobomba,
            cantidad_minima=1,
        )
        segundo = RequisitoRecursoCapacidad.objects.create(
            capacidad=self.capacidad_dos,
            tipo_recurso=self.tipo_autobomba,
            cantidad_minima=1,
        )
        self.assertNotEqual(primero.capacidad, segundo.capacidad)

    def test_catalogo_utilizado_esta_protegido(self):
        RequisitoRecursoCapacidad.objects.create(
            capacidad=self.capacidad_uno,
            tipo_recurso=self.tipo_autobomba,
            cantidad_minima=1,
        )
        with self.assertRaises(Exception):
            self.tipo_autobomba.delete()
