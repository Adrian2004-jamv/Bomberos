from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, HistorialEstadoRecurso, Recurso, TipoRecurso

from .models import DespliegueUnidad, Emergencia
from .services import (
    cambiar_estado_despliegue,
    cancelar_despliegue,
    desplegar_unidad,
    finalizar_despliegue,
)


class EmergenciasYDesplieguesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="LAT-EM")
        cls.cuerpo_uno = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Bomberos Uno",
            sigla="CBU-EM",
            ruc="0596000000001",
            direccion="Centro",
        )
        cls.cuerpo_dos = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Bomberos Dos",
            sigla="CBD-EM",
            ruc="0596000000002",
            direccion="Sur",
        )
        cls.estacion_uno = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo_uno,
            nombre="Central Uno",
            codigo="C1-EM",
            direccion="Centro",
            latitud="-0.900000",
            longitud="-78.600000",
        )
        cls.estacion_uno_b = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo_uno,
            nombre="Norte Uno",
            codigo="N1-EM",
            direccion="Norte",
            latitud="-0.910000",
            longitud="-78.610000",
        )
        cls.estacion_dos = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo_dos,
            nombre="Central Dos",
            codigo="C2-EM",
            direccion="Sur",
            latitud="-1.000000",
            longitud="-78.650000",
        )
        categoria = CategoriaRecurso.objects.create(nombre="Vehículos", codigo="VEH-EM")
        cls.tipo_unidad = TipoRecurso.objects.create(
            categoria=categoria,
            nombre="Autobomba",
            codigo="AUT-EM",
            es_unidad_desplegable=True,
        )
        cls.tipo_no_unidad = TipoRecurso.objects.create(
            categoria=categoria,
            nombre="Generador",
            codigo="GEN-EM",
            es_unidad_desplegable=False,
        )
        cls.usuario_institucional = cls.crear_usuario(
            "institucional-em",
            "0560000001",
            "Responsable institucional",
            cls.estacion_uno,
        )
        cls.usuario_estacion = cls.crear_usuario(
            "estacion-em",
            "0560000002",
            "Responsable de estación",
            cls.estacion_uno,
        )
        cls.usuario_consulta = cls.crear_usuario(
            "consulta-em",
            "0560000003",
            "Operador de consulta",
            cls.estacion_uno,
        )

    @classmethod
    def crear_usuario(cls, username, cedula, grupo, estacion):
        usuario = get_user_model().objects.create_user(
            username=username, cedula=cedula, password="clave", estacion=estacion
        )
        usuario.groups.add(Group.objects.get(name=grupo))
        return usuario

    def crear_emergencia(self, codigo="EM-2026-001", estado=Emergencia.Estado.REPORTADA):
        return Emergencia.objects.create(
            codigo=codigo,
            tipo_emergencia="Incendio estructural",
            descripcion="Incendio en edificación",
            prioridad=Emergencia.Prioridad.ALTA,
            estado=estado,
            direccion="Centro de Latacunga",
            latitud="-0.933333",
            longitud="-78.616667",
            estacion_responsable=self.estacion_uno,
            registrado_por=self.usuario_institucional,
        )

    def crear_unidad(
        self,
        codigo="U-001",
        estacion=None,
        tipo=None,
        estado=Recurso.EstadoOperativo.OPERATIVO,
        disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
        activo=True,
    ):
        return Recurso.objects.create(
            estacion=estacion or self.estacion_uno,
            tipo=tipo or self.tipo_unidad,
            codigo_interno=codigo,
            nombre=f"Unidad {codigo}",
            estado_operativo=estado,
            disponibilidad=disponibilidad,
            activo=activo,
        )

    def test_registro_valido_de_emergencia(self):
        emergencia = self.crear_emergencia()
        emergencia.full_clean()
        self.assertEqual(emergencia.estado, Emergencia.Estado.REPORTADA)
        self.assertTrue(emergencia.admite_despliegues)

    def test_validacion_de_coordenadas(self):
        emergencia = self.crear_emergencia()
        emergencia.latitud = 91
        emergencia.longitud = -181
        with self.assertRaises(ValidationError) as contexto:
            emergencia.full_clean()
        self.assertIn("latitud", contexto.exception.message_dict)
        self.assertIn("longitud", contexto.exception.message_dict)

    def test_fecha_cierre_no_puede_ser_anterior_al_reporte(self):
        emergencia = self.crear_emergencia()
        emergencia.fecha_cierre = emergencia.fecha_reporte - timedelta(minutes=1)
        with self.assertRaises(ValidationError):
            emergencia.full_clean()

    def test_despliegue_correcto_asigna_unidad_y_crea_historial(self):
        emergencia = self.crear_emergencia()
        unidad = self.crear_unidad()
        despliegue = desplegar_unidad(
            emergencia, unidad, self.usuario_institucional, "Salida inicial"
        )
        unidad.refresh_from_db()
        self.assertEqual(despliegue.estado, DespliegueUnidad.Estado.ASIGNADA)
        self.assertEqual(despliegue.estacion_procedencia, self.estacion_uno)
        self.assertEqual(unidad.disponibilidad, Recurso.Disponibilidad.ASIGNADO)
        historial = HistorialEstadoRecurso.objects.get(recurso=unidad)
        self.assertEqual(historial.disponibilidad_nueva, Recurso.Disponibilidad.ASIGNADO)

    def test_rechaza_recurso_que_no_es_unidad_movil(self):
        with self.assertRaises(ValidationError):
            desplegar_unidad(
                self.crear_emergencia(),
                self.crear_unidad(tipo=self.tipo_no_unidad),
                self.usuario_institucional,
            )

    def test_rechaza_unidad_fuera_de_servicio(self):
        unidad = self.crear_unidad(estado=Recurso.EstadoOperativo.FUERA_SERVICIO)
        with self.assertRaises(ValidationError):
            desplegar_unidad(self.crear_emergencia(), unidad, self.usuario_institucional)

    def test_rechaza_unidad_no_disponible(self):
        unidad = self.crear_unidad(disponibilidad=Recurso.Disponibilidad.RESERVADO)
        with self.assertRaises(ValidationError):
            desplegar_unidad(self.crear_emergencia(), unidad, self.usuario_institucional)

    def test_rechaza_unidad_de_otra_institucion(self):
        unidad = self.crear_unidad(estacion=self.estacion_dos)
        with self.assertRaises(ValidationError):
            desplegar_unidad(self.crear_emergencia(), unidad, self.usuario_institucional)

    def test_responsable_estacion_no_usa_unidad_de_otra_estacion(self):
        unidad = self.crear_unidad(estacion=self.estacion_uno_b)
        with self.assertRaises(ValidationError):
            desplegar_unidad(self.crear_emergencia(), unidad, self.usuario_estacion)

    def test_operador_consulta_no_puede_despachar(self):
        with self.assertRaises(ValidationError):
            desplegar_unidad(
                self.crear_emergencia(), self.crear_unidad(), self.usuario_consulta
            )

    def test_unidad_no_puede_tener_dos_despliegues_activos(self):
        unidad = self.crear_unidad()
        primero = desplegar_unidad(
            self.crear_emergencia(), unidad, self.usuario_institucional
        )
        unidad.disponibilidad = Recurso.Disponibilidad.DISPONIBLE
        unidad.save(update_fields=("disponibilidad",))
        with self.assertRaises(ValidationError):
            desplegar_unidad(
                self.crear_emergencia("EM-2026-002"),
                unidad,
                self.usuario_institucional,
            )
        self.assertTrue(DespliegueUnidad.objects.filter(pk=primero.pk).exists())

    def test_restriccion_base_impide_doble_despliegue_activo(self):
        emergencia = self.crear_emergencia()
        unidad = self.crear_unidad()
        datos = {
            "emergencia": emergencia,
            "unidad": unidad,
            "estacion_procedencia": unidad.estacion,
            "despachado_por": self.usuario_institucional,
        }
        DespliegueUnidad.objects.create(**datos)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DespliegueUnidad.objects.create(**datos)

    def test_emergencia_cerrada_o_cancelada_no_admite_unidades(self):
        for indice, estado in enumerate(
            (Emergencia.Estado.CERRADA, Emergencia.Estado.CANCELADA), start=1
        ):
            with self.subTest(estado=estado), self.assertRaises(ValidationError):
                desplegar_unidad(
                    self.crear_emergencia(f"EM-CERRADA-{indice}", estado),
                    self.crear_unidad(f"U-CERRADA-{indice}"),
                    self.usuario_institucional,
                )

    def test_transiciones_validas_registran_fechas_y_conservan_historial(self):
        despliegue = desplegar_unidad(
            self.crear_emergencia(), self.crear_unidad(), self.usuario_institucional
        )
        despliegue = cambiar_estado_despliegue(
            despliegue, DespliegueUnidad.Estado.EN_RUTA, self.usuario_institucional
        )
        self.assertIsNotNone(despliegue.fecha_salida)
        despliegue = cambiar_estado_despliegue(
            despliegue, DespliegueUnidad.Estado.EN_SITIO, self.usuario_institucional
        )
        self.assertIsNotNone(despliegue.fecha_llegada)
        fecha_asignacion = despliegue.fecha_asignacion
        despliegue = cambiar_estado_despliegue(
            despliegue, DespliegueUnidad.Estado.RETORNANDO, self.usuario_institucional
        )
        despliegue = finalizar_despliegue(
            despliegue, self.usuario_institucional, "Retorno completado"
        )
        self.assertEqual(despliegue.estado, DespliegueUnidad.Estado.FINALIZADA)
        self.assertEqual(despliegue.fecha_asignacion, fecha_asignacion)
        self.assertIsNotNone(despliegue.fecha_retorno)
        self.assertTrue(DespliegueUnidad.objects.filter(pk=despliegue.pk).exists())
        despliegue.unidad.refresh_from_db()
        self.assertEqual(
            despliegue.unidad.disponibilidad, Recurso.Disponibilidad.DISPONIBLE
        )
        self.assertEqual(despliegue.unidad.historial_estados.count(), 2)

    def test_rechaza_transicion_invalida(self):
        despliegue = desplegar_unidad(
            self.crear_emergencia(), self.crear_unidad(), self.usuario_institucional
        )
        with self.assertRaises(ValidationError):
            cambiar_estado_despliegue(
                despliegue,
                DespliegueUnidad.Estado.EN_SITIO,
                self.usuario_institucional,
            )
        despliegue.refresh_from_db()
        self.assertEqual(despliegue.estado, DespliegueUnidad.Estado.ASIGNADA)

    def test_cancelacion_libera_unidad(self):
        despliegue = desplegar_unidad(
            self.crear_emergencia(), self.crear_unidad(), self.usuario_institucional
        )
        despliegue = cancelar_despliegue(despliegue, self.usuario_institucional)
        despliegue.unidad.refresh_from_db()
        self.assertEqual(despliegue.estado, DespliegueUnidad.Estado.CANCELADA)
        self.assertEqual(
            despliegue.unidad.disponibilidad, Recurso.Disponibilidad.DISPONIBLE
        )

    def test_unidad_no_operativa_no_se_libera_como_disponible(self):
        despliegue = desplegar_unidad(
            self.crear_emergencia(), self.crear_unidad(), self.usuario_institucional
        )
        Recurso.objects.filter(pk=despliegue.unidad_id).update(
            estado_operativo=Recurso.EstadoOperativo.FUERA_SERVICIO
        )
        despliegue = cancelar_despliegue(despliegue, self.usuario_institucional)
        despliegue.unidad.refresh_from_db()
        self.assertEqual(
            despliegue.unidad.disponibilidad, Recurso.Disponibilidad.NO_DISPONIBLE
        )

    def test_fallo_al_crear_despliegue_revierte_disponibilidad(self):
        unidad = self.crear_unidad()
        with patch(
            "emergencias.services.DespliegueUnidad.objects.create",
            side_effect=DatabaseError("Fallo simulado"),
        ):
            with self.assertRaises(DatabaseError):
                desplegar_unidad(
                    self.crear_emergencia(), unidad, self.usuario_institucional
                )
        unidad.refresh_from_db()
        self.assertEqual(unidad.disponibilidad, Recurso.Disponibilidad.DISPONIBLE)
        self.assertFalse(unidad.historial_estados.exists())
        self.assertFalse(DespliegueUnidad.objects.exists())

    def test_listado_web_muestra_emergencias_del_ambito(self):
        emergencia = self.crear_emergencia()
        self.client.force_login(self.usuario_consulta)
        respuesta = self.client.get("/emergencias/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, emergencia.codigo)

    def test_detalle_web_no_expone_emergencias_de_otra_institucion(self):
        emergencia = Emergencia.objects.create(
            codigo="EM-AJENA-001",
            tipo_emergencia="Emergencia ajena",
            direccion="Otra institución",
            estacion_responsable=self.estacion_dos,
            registrado_por=self.usuario_institucional,
        )
        self.client.force_login(self.usuario_consulta)
        respuesta = self.client.get(f"/emergencias/{emergencia.pk}/")
        self.assertEqual(respuesta.status_code, 404)
