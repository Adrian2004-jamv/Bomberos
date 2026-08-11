from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.test import TestCase

from instituciones.models import Canton, CuerpoBomberos, Estacion

from .models import CategoriaRecurso, HistorialEstadoRecurso, Recurso, TipoRecurso
from .services import actualizar_estado_recurso


class ActualizarEstadoRecursoTests(TestCase):
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
        estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo,
            nombre="Estación Central",
            codigo="EC-01",
            direccion="Latacunga",
            latitud="-0.933333",
            longitud="-78.616667",
        )
        categoria = CategoriaRecurso.objects.create(nombre="Vehículo", codigo="VEH")
        tipo = TipoRecurso.objects.create(
            categoria=categoria,
            nombre="Autobomba",
            codigo="AUT",
        )
        cls.recurso = Recurso.objects.create(
            estacion=estacion,
            tipo=tipo,
            codigo_interno="R-001",
            nombre="Autobomba de prueba",
        )
        cls.usuario = get_user_model().objects.create_user(
            username="responsable",
            cedula="0500000001",
            password="clave-segura-prueba",
            estacion=estacion,
        )

    def test_cambio_valido_actualiza_recurso_y_crea_historial(self):
        recurso, historial = actualizar_estado_recurso(
            recurso=self.recurso,
            nuevo_estado_operativo=Recurso.EstadoOperativo.MANTENIMIENTO,
            nueva_disponibilidad=Recurso.Disponibilidad.NO_DISPONIBLE,
            usuario_responsable=self.usuario,
            motivo="Revisión preventiva",
            observaciones="Ingreso al taller",
        )

        recurso.refresh_from_db()
        self.assertEqual(recurso.estado_operativo, Recurso.EstadoOperativo.MANTENIMIENTO)
        self.assertEqual(recurso.disponibilidad, Recurso.Disponibilidad.NO_DISPONIBLE)
        self.assertEqual(HistorialEstadoRecurso.objects.count(), 1)
        self.assertEqual(historial.estado_anterior, Recurso.EstadoOperativo.OPERATIVO)
        self.assertEqual(historial.disponibilidad_anterior, Recurso.Disponibilidad.DISPONIBLE)
        self.assertEqual(historial.registrado_por, self.usuario)

    def test_sin_cambios_no_crea_historial(self):
        recurso, historial = actualizar_estado_recurso(
            recurso=self.recurso,
            nuevo_estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
            nueva_disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
            usuario_responsable=self.usuario,
            motivo="Verificación sin novedades",
        )

        self.assertEqual(recurso.pk, self.recurso.pk)
        self.assertIsNone(historial)
        self.assertFalse(HistorialEstadoRecurso.objects.exists())

    def test_opcion_invalida_produce_error(self):
        with self.assertRaises(ValidationError):
            actualizar_estado_recurso(
                recurso=self.recurso,
                nuevo_estado_operativo="estado_inexistente",
                nueva_disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
                usuario_responsable=self.usuario,
                motivo="Prueba de validación",
            )

        self.recurso.refresh_from_db()
        self.assertEqual(self.recurso.estado_operativo, Recurso.EstadoOperativo.OPERATIVO)
        self.assertFalse(HistorialEstadoRecurso.objects.exists())

    def test_fallo_del_historial_revierte_actualizacion(self):
        with patch(
            "inventario.services.HistorialEstadoRecurso.objects.create",
            side_effect=DatabaseError("Fallo simulado al crear el historial"),
        ):
            with self.assertRaises(DatabaseError):
                actualizar_estado_recurso(
                    recurso=self.recurso,
                    nuevo_estado_operativo=Recurso.EstadoOperativo.FUERA_SERVICIO,
                    nueva_disponibilidad=Recurso.Disponibilidad.NO_DISPONIBLE,
                    usuario_responsable=self.usuario,
                    motivo="Fallo de auditoría simulado",
                )

        self.recurso.refresh_from_db()
        self.assertEqual(self.recurso.estado_operativo, Recurso.EstadoOperativo.OPERATIVO)
        self.assertEqual(self.recurso.disponibilidad, Recurso.Disponibilidad.DISPONIBLE)
        self.assertFalse(HistorialEstadoRecurso.objects.exists())
