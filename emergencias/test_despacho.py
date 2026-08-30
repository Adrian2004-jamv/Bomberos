"""Despacho de unidades y ciclo de estado del incidente desde la interfaz.

Los servicios ya estaban probados en ``tests.py``; aquí se comprueba que la
aplicación web los usa, que respeta el ámbito del usuario y que la interfaz
solo ofrece las transiciones que el servicio aceptaría.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, HistorialEstadoRecurso, Recurso, TipoRecurso

from .models import DespliegueUnidad, Emergencia
from .services import (cambiar_estado_emergencia, desplegar_unidad,
                       unidades_desplegables)


class BaseDespachoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="LAT-DP")
        cls.cuerpo = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Bomberos Despacho",
            sigla="CBD-DP",
            ruc="0596000000101",
            direccion="Centro",
        )
        cls.cuerpo_ajeno = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Bomberos Ajenos",
            sigla="CBA-DP",
            ruc="0596000000102",
            direccion="Sur",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo,
            nombre="Central Despacho",
            codigo="CD-DP",
            direccion="Centro",
            latitud="-0.930000",
            longitud="-78.610000",
        )
        cls.estacion_ajena = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo_ajeno,
            nombre="Central Ajena",
            codigo="CA-DP",
            direccion="Sur",
            latitud="-1.010000",
            longitud="-78.660000",
        )
        categoria = CategoriaRecurso.objects.create(nombre="Vehículos", codigo="VEH-DP")
        cls.tipo_unidad = TipoRecurso.objects.create(
            categoria=categoria,
            nombre="Autobomba",
            codigo="AUT-DP",
            es_unidad_desplegable=True,
        )
        cls.tipo_equipo = TipoRecurso.objects.create(
            categoria=categoria,
            nombre="Generador",
            codigo="GEN-DP",
            es_unidad_desplegable=False,
        )
        cls.responsable = cls.crear_usuario(
            "responsable-dp", "0570000001", "Responsable institucional", cls.estacion
        )
        cls.consulta = cls.crear_usuario(
            "consulta-dp", "0570000002", "Operador de consulta", cls.estacion
        )
        cls.ajeno = cls.crear_usuario(
            "ajeno-dp", "0570000003", "Responsable institucional", cls.estacion_ajena
        )

    @classmethod
    def crear_usuario(cls, username, cedula, grupo, estacion):
        usuario = get_user_model().objects.create_user(
            username=username, cedula=cedula, password="clave", estacion=estacion
        )
        usuario.groups.add(Group.objects.get(name=grupo))
        return usuario

    def crear_emergencia(self, codigo="EM-DP-001", estado=Emergencia.Estado.REPORTADA,
                         estacion=None):
        return Emergencia.objects.create(
            codigo=codigo,
            tipo_emergencia="Incendio estructural",
            descripcion="Incendio en edificación",
            prioridad=Emergencia.Prioridad.ALTA,
            estado=estado,
            direccion="Centro de Latacunga",
            latitud="-0.933333",
            longitud="-78.616667",
            estacion_responsable=estacion or self.estacion,
            registrado_por=self.responsable,
        )

    def crear_unidad(self, codigo="AB-DP-01", estacion=None, tipo=None,
                     estado=Recurso.EstadoOperativo.OPERATIVO,
                     disponibilidad=Recurso.Disponibilidad.DISPONIBLE, activo=True):
        return Recurso.objects.create(
            estacion=estacion or self.estacion,
            tipo=tipo or self.tipo_unidad,
            codigo_interno=codigo,
            nombre=f"Unidad {codigo}",
            estado_operativo=estado,
            disponibilidad=disponibilidad,
            activo=activo,
        )


class EstadoEmergenciaTests(BaseDespachoTests):
    def test_transicion_valida_avanza_el_incidente(self):
        emergencia = self.crear_emergencia()
        actualizada = cambiar_estado_emergencia(
            emergencia, Emergencia.Estado.EN_ATENCION, self.responsable
        )
        self.assertEqual(actualizada.estado, Emergencia.Estado.EN_ATENCION)
        self.assertIsNone(actualizada.fecha_cierre)

    def test_no_permite_saltar_de_reportada_a_cerrada(self):
        emergencia = self.crear_emergencia()
        with self.assertRaises(ValidationError):
            cambiar_estado_emergencia(
                emergencia, Emergencia.Estado.CERRADA, self.responsable
            )
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.REPORTADA)

    def test_cierre_sella_la_fecha_y_termina_el_incidente(self):
        emergencia = self.crear_emergencia(estado=Emergencia.Estado.EN_ATENCION)
        actualizada = cambiar_estado_emergencia(
            emergencia, Emergencia.Estado.CERRADA, self.responsable
        )
        self.assertTrue(actualizada.esta_terminada)
        self.assertIsNotNone(actualizada.fecha_cierre)
        self.assertGreaterEqual(actualizada.fecha_cierre, actualizada.fecha_reporte)
        self.assertFalse(actualizada.admite_despliegues)

    def test_no_cierra_con_unidades_todavia_en_el_incidente(self):
        emergencia = self.crear_emergencia(estado=Emergencia.Estado.EN_ATENCION)
        desplegar_unidad(emergencia, self.crear_unidad(), self.responsable)
        with self.assertRaises(ValidationError) as contexto:
            cambiar_estado_emergencia(
                emergencia, Emergencia.Estado.CERRADA, self.responsable
            )
        self.assertIn("AB-DP-01", " ".join(contexto.exception.messages))
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.EN_ATENCION)
        self.assertIsNone(emergencia.fecha_cierre)

    def test_cierra_cuando_los_despliegues_terminaron(self):
        emergencia = self.crear_emergencia(estado=Emergencia.Estado.EN_ATENCION)
        despliegue = desplegar_unidad(emergencia, self.crear_unidad(), self.responsable)
        DespliegueUnidad.objects.filter(pk=despliegue.pk).update(
            estado=DespliegueUnidad.Estado.FINALIZADA
        )
        actualizada = cambiar_estado_emergencia(
            emergencia, Emergencia.Estado.CERRADA, self.responsable
        )
        self.assertEqual(actualizada.estado, Emergencia.Estado.CERRADA)

    def test_un_incidente_terminado_no_admite_mas_transiciones(self):
        emergencia = self.crear_emergencia(estado=Emergencia.Estado.CERRADA)
        with self.assertRaises(ValidationError):
            cambiar_estado_emergencia(
                emergencia, Emergencia.Estado.EN_ATENCION, self.responsable
            )

    def test_rechaza_estado_inexistente(self):
        with self.assertRaises(ValidationError):
            cambiar_estado_emergencia(self.crear_emergencia(), "archivada", self.responsable)

    def test_rechaza_usuario_fuera_del_ambito(self):
        emergencia = self.crear_emergencia()
        with self.assertRaises(ValidationError):
            cambiar_estado_emergencia(
                emergencia, Emergencia.Estado.EN_ATENCION, self.ajeno
            )

    def test_rechaza_perfil_de_consulta(self):
        emergencia = self.crear_emergencia()
        with self.assertRaises(ValidationError):
            cambiar_estado_emergencia(
                emergencia, Emergencia.Estado.EN_ATENCION, self.consulta
            )


class UnidadesDesplegablesTests(BaseDespachoTests):
    def test_solo_ofrece_unidades_operativas_disponibles_y_del_ambito(self):
        emergencia = self.crear_emergencia()
        libre = self.crear_unidad()
        self.crear_unidad(codigo="GEN-01", tipo=self.tipo_equipo)
        self.crear_unidad(codigo="AB-02", estado=Recurso.EstadoOperativo.FUERA_SERVICIO)
        self.crear_unidad(codigo="AB-03", disponibilidad=Recurso.Disponibilidad.NO_DISPONIBLE)
        self.crear_unidad(codigo="AB-04", activo=False)
        self.crear_unidad(codigo="AB-05", estacion=self.estacion_ajena)
        self.assertEqual(
            list(unidades_desplegables(emergencia, self.responsable)), [libre]
        )

    def test_una_unidad_en_otro_incidente_deja_de_ofrecerse(self):
        emergencia = self.crear_emergencia()
        unidad = self.crear_unidad()
        desplegar_unidad(emergencia, unidad, self.responsable)
        otra = self.crear_emergencia(codigo="EM-DP-002")
        self.assertNotIn(unidad, unidades_desplegables(otra, self.responsable))


class DespachoWebTests(BaseDespachoTests):
    def test_responsable_despacha_una_unidad_desde_la_interfaz(self):
        emergencia = self.crear_emergencia()
        unidad = self.crear_unidad()
        self.client.force_login(self.responsable)
        respuesta = self.client.post(
            reverse("emergencias:despachar", args=[emergencia.pk]),
            {"unidad": unidad.pk, "observaciones": "Salida inmediata"},
        )
        self.assertRedirects(respuesta, reverse("emergencias:detalle", args=[emergencia.pk]))
        despliegue = DespliegueUnidad.objects.get(emergencia=emergencia)
        unidad.refresh_from_db()
        self.assertEqual(despliegue.unidad, unidad)
        self.assertEqual(despliegue.despachado_por, self.responsable)
        self.assertEqual(despliegue.estado, DespliegueUnidad.Estado.ASIGNADA)
        self.assertEqual(despliegue.observaciones, "Salida inmediata")
        self.assertEqual(unidad.disponibilidad, Recurso.Disponibilidad.ASIGNADO)
        self.assertTrue(HistorialEstadoRecurso.objects.filter(recurso=unidad).exists())

    def test_formulario_lista_las_unidades_disponibles(self):
        emergencia = self.crear_emergencia()
        self.crear_unidad()
        self.client.force_login(self.responsable)
        respuesta = self.client.get(reverse("emergencias:despachar", args=[emergencia.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "AB-DP-01")
        self.assertContains(respuesta, "Despachar unidad")

    def test_avisa_cuando_no_queda_ninguna_unidad_disponible(self):
        emergencia = self.crear_emergencia()
        self.client.force_login(self.responsable)
        respuesta = self.client.get(reverse("emergencias:despachar", args=[emergencia.pk]))
        self.assertContains(respuesta, "No hay unidades disponibles para despachar.")
        self.assertNotContains(respuesta, "Observaciones")

    def test_unidad_ajena_no_se_acepta_aunque_se_envie_su_identificador(self):
        emergencia = self.crear_emergencia()
        ajena = self.crear_unidad(codigo="AB-AJ-01", estacion=self.estacion_ajena)
        self.client.force_login(self.responsable)
        respuesta = self.client.post(
            reverse("emergencias:despachar", args=[emergencia.pk]), {"unidad": ajena.pk}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(DespliegueUnidad.objects.exists())

    def test_perfil_de_consulta_no_puede_despachar(self):
        emergencia = self.crear_emergencia()
        self.client.force_login(self.consulta)
        self.assertEqual(
            self.client.get(reverse("emergencias:despachar", args=[emergencia.pk])).status_code,
            403,
        )

    def test_una_emergencia_cerrada_no_admite_despacho(self):
        emergencia = self.crear_emergencia(estado=Emergencia.Estado.CERRADA)
        self.client.force_login(self.responsable)
        respuesta = self.client.get(reverse("emergencias:despachar", args=[emergencia.pk]))
        self.assertRedirects(respuesta, reverse("emergencias:detalle", args=[emergencia.pk]))

    def test_acceso_anonimo_va_al_inicio_de_sesion(self):
        emergencia = self.crear_emergencia()
        respuesta = self.client.get(reverse("emergencias:despachar", args=[emergencia.pk]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("usuarios:login"), respuesta.headers["Location"])


class TransicionesWebTests(BaseDespachoTests):
    def test_el_detalle_ya_no_muestra_el_ciclo_operativo(self):
        """El panel se retiró de la pantalla; la ruta de estado sigue viva."""
        emergencia = self.crear_emergencia()
        self.client.force_login(self.responsable)
        respuesta = self.client.get(reverse("emergencias:detalle", args=[emergencia.pk]))
        self.assertNotContains(respuesta, "Ciclo operativo")
        self.assertNotContains(respuesta, "incident-state-panel")

    def test_la_ruta_de_estado_sigue_atendiendo(self):
        """Sin el panel, cambiar de estado exige llamar la ruta directamente."""
        emergencia = self.crear_emergencia()
        self.client.force_login(self.responsable)
        respuesta = self.client.post(
            reverse("emergencias:cambiar_estado", args=[emergencia.pk]),
            {"estado": Emergencia.Estado.EN_ATENCION},
        )
        self.assertEqual(respuesta.status_code, 302)
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.EN_ATENCION)

    def test_detalle_no_ofrece_transiciones_a_un_perfil_de_consulta(self):
        emergencia = self.crear_emergencia()
        self.client.force_login(self.consulta)
        respuesta = self.client.get(reverse("emergencias:detalle", args=[emergencia.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'name="estado"')
        self.assertNotContains(respuesta, "Registrar unidad en el SCI-211")

    def test_cambio_de_estado_desde_la_interfaz(self):
        emergencia = self.crear_emergencia()
        self.client.force_login(self.responsable)
        respuesta = self.client.post(
            reverse("emergencias:cambiar_estado", args=[emergencia.pk]),
            {"estado": Emergencia.Estado.EN_ATENCION},
            follow=True,
        )
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.EN_ATENCION)
        self.assertContains(respuesta, "La emergencia pasó a en atención.")

    def test_cierre_bloqueado_se_explica_en_la_interfaz(self):
        emergencia = self.crear_emergencia(estado=Emergencia.Estado.EN_ATENCION)
        desplegar_unidad(emergencia, self.crear_unidad(), self.responsable)
        self.client.force_login(self.responsable)
        respuesta = self.client.post(
            reverse("emergencias:cambiar_estado", args=[emergencia.pk]),
            {"estado": Emergencia.Estado.CERRADA},
            follow=True,
        )
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.EN_ATENCION)
        self.assertContains(respuesta, "Todavía hay unidades en la emergencia")

    def test_el_cambio_de_estado_solo_acepta_post(self):
        emergencia = self.crear_emergencia()
        self.client.force_login(self.responsable)
        self.assertEqual(
            self.client.get(
                reverse("emergencias:cambiar_estado", args=[emergencia.pk])
            ).status_code,
            405,
        )

    def test_despliegue_avanza_y_libera_la_unidad_al_finalizar(self):
        emergencia = self.crear_emergencia(estado=Emergencia.Estado.EN_ATENCION)
        despliegue = desplegar_unidad(emergencia, self.crear_unidad(), self.responsable)
        self.client.force_login(self.responsable)
        url = reverse("emergencias:despliegue_estado", args=[despliegue.pk])
        for estado in (
            DespliegueUnidad.Estado.EN_RUTA,
            DespliegueUnidad.Estado.EN_SITIO,
            DespliegueUnidad.Estado.FINALIZADA,
        ):
            respuesta = self.client.post(url, {"estado": estado})
            self.assertRedirects(
                respuesta, reverse("emergencias:detalle", args=[emergencia.pk])
            )
        despliegue.refresh_from_db()
        despliegue.unidad.refresh_from_db()
        self.assertEqual(despliegue.estado, DespliegueUnidad.Estado.FINALIZADA)
        self.assertIsNotNone(despliegue.fecha_salida)
        self.assertIsNotNone(despliegue.fecha_llegada)
        self.assertIsNotNone(despliegue.fecha_retorno)
        self.assertEqual(despliegue.unidad.disponibilidad, Recurso.Disponibilidad.DISPONIBLE)

    def test_transicion_invalida_de_despliegue_no_altera_el_registro(self):
        emergencia = self.crear_emergencia()
        despliegue = desplegar_unidad(emergencia, self.crear_unidad(), self.responsable)
        self.client.force_login(self.responsable)
        respuesta = self.client.post(
            reverse("emergencias:despliegue_estado", args=[despliegue.pk]),
            {"estado": DespliegueUnidad.Estado.FINALIZADA},
            follow=True,
        )
        despliegue.refresh_from_db()
        self.assertEqual(despliegue.estado, DespliegueUnidad.Estado.ASIGNADA)
        self.assertContains(respuesta, "No se puede cambiar de")

    def test_despliegue_de_otra_institucion_no_es_alcanzable(self):
        emergencia = self.crear_emergencia(codigo="EM-DP-AJ", estacion=self.estacion_ajena)
        despliegue = desplegar_unidad(
            emergencia, self.crear_unidad(codigo="AB-AJ-02", estacion=self.estacion_ajena),
            self.ajeno,
        )
        self.client.force_login(self.responsable)
        respuesta = self.client.post(
            reverse("emergencias:despliegue_estado", args=[despliegue.pk]),
            {"estado": DespliegueUnidad.Estado.EN_RUTA},
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_detalle_muestra_las_acciones_del_despliegue(self):
        emergencia = self.crear_emergencia(estado=Emergencia.Estado.EN_ATENCION)
        despliegue = desplegar_unidad(emergencia, self.crear_unidad(), self.responsable)
        self.client.force_login(self.responsable)
        respuesta = self.client.get(reverse("emergencias:detalle", args=[emergencia.pk]))
        self.assertContains(
            respuesta, reverse("emergencias:despliegue_estado", args=[despliegue.pk])
        )
        self.assertContains(respuesta, 'value="en_ruta"', html=False)
        self.assertContains(respuesta, "Registrar unidad en el SCI-211")


class EdicionEmergenciaTests(BaseDespachoTests):
    def test_responsable_corrige_la_situacion_del_incidente(self):
        emergencia = self.crear_emergencia()
        self.client.force_login(self.responsable)
        respuesta = self.client.post(
            reverse("emergencias:editar", args=[emergencia.pk]),
            {
                "tipo_emergencia": "Incendio forestal",
                "descripcion": "Se extiende al cerro",
                "prioridad": Emergencia.Prioridad.CRITICA,
                "direccion": "Vía a Pujilí km 3",
                "latitud": "-0.940000",
                "longitud": "-78.620000",
            },
        )
        self.assertRedirects(respuesta, reverse("emergencias:detalle", args=[emergencia.pk]))
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.tipo_emergencia, "Incendio forestal")
        self.assertEqual(emergencia.prioridad, Emergencia.Prioridad.CRITICA)
        self.assertEqual(emergencia.direccion, "Vía a Pujilí km 3")

    def test_la_edicion_no_expone_codigo_ni_estacion_ni_estado(self):
        emergencia = self.crear_emergencia()
        self.client.force_login(self.responsable)
        respuesta = self.client.get(reverse("emergencias:editar", args=[emergencia.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'name="codigo"')
        self.assertNotContains(respuesta, 'name="estacion_responsable"')
        self.assertNotContains(respuesta, 'name="fecha_reporte"')

    def test_una_emergencia_terminada_no_se_edita(self):
        emergencia = self.crear_emergencia(estado=Emergencia.Estado.CERRADA)
        self.client.force_login(self.responsable)
        respuesta = self.client.get(reverse("emergencias:editar", args=[emergencia.pk]))
        self.assertRedirects(respuesta, reverse("emergencias:detalle", args=[emergencia.pk]))

    def test_perfil_de_consulta_no_puede_editar(self):
        emergencia = self.crear_emergencia()
        self.client.force_login(self.consulta)
        self.assertEqual(
            self.client.get(reverse("emergencias:editar", args=[emergencia.pk])).status_code,
            403,
        )

    def test_el_registro_rechaza_una_fecha_de_reporte_futura(self):
        self.client.force_login(self.responsable)
        futuro = (timezone.localtime() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        respuesta = self.client.post(reverse("emergencias:crear"), {
            "tipo_emergencia": "Rescate",
            "descripcion": "Prueba",
            "prioridad": Emergencia.Prioridad.MEDIA,
            "fecha_reporte": futuro,
            "direccion": "Latacunga",
            "latitud": "-0.933333",
            "longitud": "-78.616667",
            "estacion_responsable": self.estacion.pk,
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "La fecha del reporte no puede estar en el futuro.")
        self.assertFalse(Emergencia.objects.filter(descripcion="Prueba").exists())
