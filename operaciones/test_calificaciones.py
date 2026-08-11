from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion

from .models import CalificacionPersonal, EspecialidadOperativa, PersonalOperativo


class CalificacionPersonalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Salcedo", codigo="SAL")
        cuerpo = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Cuerpo de Bomberos de Salcedo",
            sigla="CBS",
            ruc="0590000000002",
            direccion="Salcedo",
        )
        estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo,
            nombre="Estación Central de Salcedo",
            codigo="ECS-01",
            direccion="Salcedo",
            latitud="-1.045278",
            longitud="-78.590833",
        )
        cls.personal_uno = PersonalOperativo.objects.create(
            estacion=estacion,
            codigo_institucional="S-001",
            nombres="María",
            apellidos="Gómez",
            fecha_ingreso=timezone.localdate(),
        )
        cls.personal_dos = PersonalOperativo.objects.create(
            estacion=estacion,
            codigo_institucional="S-002",
            nombres="Juan",
            apellidos="Vega",
            fecha_ingreso=timezone.localdate(),
        )
        cls.especialidad = EspecialidadOperativa.objects.create(
            nombre="Rescate vehicular",
            codigo="RES-VEH",
        )

    def crear_calificacion(self, **cambios):
        datos = {
            "personal": self.personal_uno,
            "especialidad": self.especialidad,
            "nivel": CalificacionPersonal.Nivel.BASICO,
            "fecha_emision": timezone.localdate(),
        }
        datos.update(cambios)
        return CalificacionPersonal.objects.create(**datos)

    def test_calificacion_activa_sin_vencimiento_esta_vigente(self):
        calificacion = self.crear_calificacion(fecha_vencimiento=None)
        self.assertTrue(calificacion.vigente)

    def test_calificacion_con_fecha_futura_esta_vigente(self):
        calificacion = self.crear_calificacion(
            fecha_vencimiento=timezone.localdate() + timedelta(days=30)
        )
        self.assertTrue(calificacion.vigente)

    def test_calificacion_vencida_no_esta_vigente(self):
        calificacion = self.crear_calificacion(
            fecha_emision=timezone.localdate() - timedelta(days=365),
            fecha_vencimiento=timezone.localdate() - timedelta(days=1),
        )
        self.assertFalse(calificacion.vigente)

    def test_calificacion_inactiva_no_esta_vigente(self):
        calificacion = self.crear_calificacion(activo=False, fecha_vencimiento=None)
        self.assertFalse(calificacion.vigente)

    def test_rechaza_vencimiento_anterior_a_emision(self):
        calificacion = CalificacionPersonal(
            personal=self.personal_uno,
            especialidad=self.especialidad,
            nivel=CalificacionPersonal.Nivel.INTERMEDIO,
            fecha_emision=timezone.localdate(),
            fecha_vencimiento=timezone.localdate() - timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            calificacion.full_clean()

    def test_no_permite_especialidad_duplicada_para_misma_persona(self):
        self.crear_calificacion()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.crear_calificacion()

    def test_misma_especialidad_puede_asignarse_a_personas_diferentes(self):
        primera = self.crear_calificacion()
        segunda = self.crear_calificacion(personal=self.personal_dos)
        self.assertEqual(primera.especialidad, segunda.especialidad)
        self.assertNotEqual(primera.personal, segunda.personal)
