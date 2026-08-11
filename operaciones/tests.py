from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion

from .models import CalificacionPersonal, EspecialidadOperativa, PersonalOperativo


class PersonalOperativoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="LAT")
        cuerpo = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Cuerpo de Bomberos de Latacunga",
            sigla="CBL",
            ruc="0590000000001",
            direccion="Latacunga",
        )
        cls.estacion_central = Estacion.objects.create(
            cuerpo_bomberos=cuerpo,
            nombre="Estación Central",
            codigo="EC-01",
            direccion="Latacunga",
            latitud="-0.933333",
            longitud="-78.616667",
        )
        cls.estacion_norte = Estacion.objects.create(
            cuerpo_bomberos=cuerpo,
            nombre="Estación Norte",
            codigo="EN-01",
            direccion="Latacunga",
            latitud="-0.900000",
            longitud="-78.600000",
        )
        cls.usuario = get_user_model().objects.create_user(
            username="bombero.usuario",
            cedula="0500000001",
            password="clave-segura-prueba",
            estacion=cls.estacion_central,
        )

    def crear_personal(self, **cambios):
        datos = {
            "estacion": self.estacion_central,
            "codigo_institucional": "P-001",
            "cedula": "0500000002",
            "nombres": "Ana María",
            "apellidos": "López Pérez",
            "fecha_ingreso": timezone.localdate(),
        }
        datos.update(cambios)
        return PersonalOperativo.objects.create(**datos)

    def test_creacion_valida_sin_cuenta_de_usuario(self):
        personal = self.crear_personal()

        self.assertIsNone(personal.usuario)
        self.assertEqual(personal.estacion, self.estacion_central)
        self.assertEqual(personal.institucion, self.estacion_central.cuerpo_bomberos)

    def test_creacion_valida_con_cuenta_de_usuario(self):
        personal = self.crear_personal(usuario=self.usuario)

        self.assertEqual(personal.usuario, self.usuario)
        self.assertEqual(self.usuario.personal_operativo, personal)

    def test_codigo_institucional_no_se_repite_en_misma_estacion(self):
        self.crear_personal(cedula=None)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.crear_personal(cedula=None)

    def test_codigo_institucional_puede_repetirse_en_estaciones_diferentes(self):
        primero = self.crear_personal(cedula=None)
        segundo = self.crear_personal(estacion=self.estacion_norte, cedula=None)

        self.assertEqual(primero.codigo_institucional, segundo.codigo_institucional)
        self.assertNotEqual(primero.estacion, segundo.estacion)

    def test_rechaza_fecha_de_ingreso_futura(self):
        personal = PersonalOperativo(
            estacion=self.estacion_central,
            codigo_institucional="P-002",
            nombres="Carlos",
            apellidos="Pérez",
            fecha_ingreso=timezone.localdate() + timedelta(days=1),
        )

        with self.assertRaises(ValidationError):
            personal.full_clean()

    def test_nombre_completo(self):
        personal = self.crear_personal()

        self.assertEqual(personal.nombre_completo, "Ana María López Pérez")
