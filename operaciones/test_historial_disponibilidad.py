from decimal import Decimal
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion

from .admin import HistorialDisponibilidadPersonalAdmin
from .models import (
    EvaluacionCapacidadEstacion,
    HistorialDisponibilidadPersonal,
    PersonalOperativo,
    TipoCapacidadOperativa,
)
from .services import actualizar_disponibilidad_personal


class ActualizarDisponibilidadPersonalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="LAT-HD")
        cuerpo = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Cuerpo de Bomberos Latacunga",
            sigla="CBL-HD",
            ruc="0592000000001",
            direccion="Latacunga",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo,
            nombre="Estación Central",
            codigo="EC-HD",
            direccion="Latacunga",
            latitud="-0.933333",
            longitud="-78.616667",
        )
        cls.personal = PersonalOperativo.objects.create(
            estacion=cls.estacion,
            codigo_institucional="P-HD-001",
            nombres="Ana",
            apellidos="López",
            fecha_ingreso=timezone.localdate(),
        )
        cls.usuario = get_user_model().objects.create_user(
            username="auditor-personal",
            cedula="0520000001",
            password="clave-segura-prueba",
            estacion=cls.estacion,
        )
        cls.usuario_inactivo = get_user_model().objects.create_user(
            username="inactivo-personal",
            cedula="0520000002",
            password="clave-segura-prueba",
            is_active=False,
        )

    def test_cambio_valido_actualiza_y_crea_historial_correcto(self):
        personal, historial = actualizar_disponibilidad_personal(
            personal=self.personal,
            nueva_disponibilidad=PersonalOperativo.Disponibilidad.ASIGNADO,
            usuario_responsable=self.usuario,
            motivo="Asignación a operativo",
            observaciones="Salida coordinada",
        )
        personal.refresh_from_db()
        self.assertEqual(personal.disponibilidad, PersonalOperativo.Disponibilidad.ASIGNADO)
        self.assertEqual(historial.disponibilidad_anterior, PersonalOperativo.Disponibilidad.DISPONIBLE)
        self.assertEqual(historial.disponibilidad_nueva, PersonalOperativo.Disponibilidad.ASIGNADO)
        self.assertEqual(historial.registrado_por, self.usuario)
        self.assertEqual(HistorialDisponibilidadPersonal.objects.count(), 1)

    def test_motivo_obligatorio(self):
        with self.assertRaises(ValidationError):
            actualizar_disponibilidad_personal(
                self.personal,
                PersonalOperativo.Disponibilidad.DESCANSO,
                self.usuario,
                "   ",
            )
        self.assertFalse(HistorialDisponibilidadPersonal.objects.exists())

    def test_disponibilidad_invalida_es_rechazada(self):
        with self.assertRaises(ValidationError):
            actualizar_disponibilidad_personal(
                self.personal, "valor_invalido", self.usuario, "Prueba"
            )
        self.personal.refresh_from_db()
        self.assertEqual(self.personal.disponibilidad, PersonalOperativo.Disponibilidad.DISPONIBLE)

    def test_mismo_valor_no_crea_historial(self):
        personal, historial = actualizar_disponibilidad_personal(
            self.personal,
            PersonalOperativo.Disponibilidad.DISPONIBLE,
            self.usuario,
            "Verificación sin novedades",
        )
        self.assertEqual(personal.pk, self.personal.pk)
        self.assertIsNone(historial)
        self.assertFalse(HistorialDisponibilidadPersonal.objects.exists())

    def test_usuario_inactivo_es_rechazado(self):
        with self.assertRaises(ValidationError):
            actualizar_disponibilidad_personal(
                self.personal,
                PersonalOperativo.Disponibilidad.LICENCIA,
                self.usuario_inactivo,
                "Licencia autorizada",
            )
        self.assertFalse(HistorialDisponibilidadPersonal.objects.exists())

    def test_fallo_del_historial_revierte_la_actualizacion(self):
        with patch(
            "operaciones.services.HistorialDisponibilidadPersonal.objects.create",
            side_effect=DatabaseError("Fallo simulado"),
        ):
            with self.assertRaises(DatabaseError):
                actualizar_disponibilidad_personal(
                    self.personal,
                    PersonalOperativo.Disponibilidad.NO_DISPONIBLE,
                    self.usuario,
                    "Novedad operativa",
                )
        self.personal.refresh_from_db()
        self.assertEqual(self.personal.disponibilidad, PersonalOperativo.Disponibilidad.DISPONIBLE)
        self.assertFalse(HistorialDisponibilidadPersonal.objects.exists())

    def test_conserva_multiples_cambios_y_ordena_el_mas_reciente_primero(self):
        _, primero = actualizar_disponibilidad_personal(
            self.personal,
            PersonalOperativo.Disponibilidad.ASIGNADO,
            self.usuario,
            "Primer cambio",
        )
        _, segundo = actualizar_disponibilidad_personal(
            self.personal,
            PersonalOperativo.Disponibilidad.DESCANSO,
            self.usuario,
            "Segundo cambio",
        )
        historiales = list(self.personal.historial_disponibilidad.all())
        self.assertEqual(historiales, [segundo, primero])
        self.assertEqual(historiales[1].disponibilidad_nueva, PersonalOperativo.Disponibilidad.ASIGNADO)
        self.assertEqual(historiales[0].disponibilidad_anterior, PersonalOperativo.Disponibilidad.ASIGNADO)

    def test_admin_no_permite_crear_editar_ni_eliminar(self):
        request = RequestFactory().get("/admin/operaciones/historialdisponibilidadpersonal/")
        request.user = self.usuario
        administracion = HistorialDisponibilidadPersonalAdmin(
            HistorialDisponibilidadPersonal, admin.site
        )
        self.assertFalse(administracion.has_add_permission(request))
        self.assertFalse(administracion.has_change_permission(request))
        self.assertFalse(administracion.has_delete_permission(request))
        self.assertEqual(
            set(administracion.readonly_fields),
            {
                "personal",
                "disponibilidad_anterior",
                "disponibilidad_nueva",
                "motivo",
                "observaciones",
                "registrado_por",
                "fecha_registro",
            },
        )

    def test_evaluacion_historica_no_cambia(self):
        capacidad = TipoCapacidadOperativa.objects.create(
            nombre="Rescate", codigo="RES-HD"
        )
        evaluacion = EvaluacionCapacidadEstacion.objects.create(
            estacion=self.estacion,
            capacidad=capacidad,
            estado=EvaluacionCapacidadEstacion.Estado.CUMPLE,
            porcentaje_cumplimiento=Decimal("100.00"),
            detalle_recursos=[],
            detalle_personal=[{"personal_id": self.personal.pk, "disponible": True}],
            evaluado_por=self.usuario,
        )
        datos_originales = (
            evaluacion.estado,
            evaluacion.porcentaje_cumplimiento,
            evaluacion.detalle_personal.copy(),
            evaluacion.fecha_evaluacion,
        )
        actualizar_disponibilidad_personal(
            self.personal,
            PersonalOperativo.Disponibilidad.NO_DISPONIBLE,
            self.usuario,
            "Cambio posterior a la evaluación",
        )
        evaluacion.refresh_from_db()
        self.assertEqual(
            (
                evaluacion.estado,
                evaluacion.porcentaje_cumplimiento,
                evaluacion.detalle_personal,
                evaluacion.fecha_evaluacion,
            ),
            datos_originales,
        )
