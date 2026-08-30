"""Indicadores propios de una emergencia."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso

from .indicadores import resumen_de_emergencia
from .models import (DespliegueUnidad, Emergencia, FormularioSCI,
                     FormularioSCI211, RegistroRecursoSCI211)
from .services import desplegar_unidad


class IndicadoresDeEmergenciaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="IND-T")
        cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Indicadores", sigla="IND-T",
            ruc="0596000000700", direccion="Centro",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo, nombre="Estación Indicadores", codigo="EI-IND",
            direccion="Centro", latitud="-0.930000", longitud="-78.610000",
        )
        cls.usuario = get_user_model().objects.create_user(
            username="indicadores", cedula="0900000001", password="clave",
            estacion=cls.estacion,
        )
        cls.usuario.groups.add(Group.objects.get(name="Responsable institucional"))

    def crear_emergencia(self, **campos):
        valores = {
            "codigo": "IE-01012026-500", "tipo_emergencia": "Incendio estructural",
            "direccion": "Centro", "estacion_responsable": self.estacion,
            "registrado_por": self.usuario,
        }
        valores.update(campos)
        return Emergencia.objects.create(**valores)

    def crear_unidad(self, codigo="AB-IND-01"):
        categoria, _ = CategoriaRecurso.objects.get_or_create(
            codigo="CAT-IND", defaults={"nombre": "Vehículos"}
        )
        tipo, _ = TipoRecurso.objects.get_or_create(
            categoria=categoria, codigo="TIP-IND",
            defaults={"nombre": "Autobomba", "es_unidad_desplegable": True},
        )
        return Recurso.objects.create(
            estacion=self.estacion, tipo=tipo, codigo_interno=codigo,
            nombre="Autobomba", estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
            disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
            fecha_confirmacion_disponibilidad=timezone.now(),
        )

    def test_una_emergencia_recien_creada_no_tiene_nada_comprometido(self):
        resumen = resumen_de_emergencia(self.crear_emergencia())
        self.assertEqual(resumen["unidades_activas"], 0)
        self.assertEqual(resumen["unidades_totales"], 0)
        self.assertEqual(resumen["recursos_registrados"], 0)
        self.assertIsNone(resumen["tiempo_respuesta"])
        self.assertTrue(resumen["sigue_abierta"])

    def test_cuenta_las_unidades_desplegadas(self):
        emergencia = self.crear_emergencia()
        desplegar_unidad(emergencia, self.crear_unidad(), self.usuario)
        resumen = resumen_de_emergencia(emergencia)
        self.assertEqual(resumen["unidades_activas"], 1)
        self.assertEqual(resumen["unidades_totales"], 1)

    def test_una_unidad_finalizada_deja_de_contar_como_activa(self):
        emergencia = self.crear_emergencia()
        despliegue = desplegar_unidad(emergencia, self.crear_unidad(), self.usuario)
        DespliegueUnidad.objects.filter(pk=despliegue.pk).update(
            estado=DespliegueUnidad.Estado.FINALIZADA
        )
        resumen = resumen_de_emergencia(emergencia)
        self.assertEqual(resumen["unidades_activas"], 0)
        self.assertEqual(resumen["unidades_totales"], 1)

    def test_el_tiempo_de_respuesta_va_del_reporte_a_la_primera_llegada(self):
        reporte = timezone.now() - timedelta(hours=2)
        emergencia = self.crear_emergencia(fecha_reporte=reporte)
        despliegue = desplegar_unidad(emergencia, self.crear_unidad(), self.usuario)
        DespliegueUnidad.objects.filter(pk=despliegue.pk).update(
            fecha_llegada=reporte + timedelta(minutes=18)
        )
        self.assertEqual(resumen_de_emergencia(emergencia)["tiempo_respuesta"], "18 min")

    def test_el_personal_sale_de_los_registros_del_sci_211(self):
        emergencia = self.crear_emergencia()
        formulario = FormularioSCI211.objects.create(
            emergencia=emergencia, codigo="SCI-211-IND", punto_registro="PC",
            registrador_1="Responsable", creado_por=self.usuario,
            modificado_por=self.usuario,
        )
        for numero, personas in enumerate((4, 2), start=1):
            RegistroRecursoSCI211.objects.create(
                formulario=formulario, orden=numero, solicitado_por="CI",
                fecha_hora_solicitud=emergencia.fecha_reporte,
                clase_recurso="Vehículos", institucion_procedencia="Bomberos",
                matricula_identificacion=f"U-{numero}", numero_personas=personas,
                estado_recurso="disponible",
            )
        resumen = resumen_de_emergencia(emergencia)
        self.assertEqual(resumen["personal_comprometido"], 6)
        self.assertEqual(resumen["recursos_registrados"], 2)

    def test_el_avance_documental_cuenta_el_211_y_los_demas(self):
        emergencia = self.crear_emergencia()
        FormularioSCI211.objects.create(
            emergencia=emergencia, codigo="SCI-211-IND2", punto_registro="PC",
            registrador_1="Responsable", creado_por=self.usuario,
            modificado_por=self.usuario,
        )
        FormularioSCI.objects.create(
            emergencia=emergencia, codigo_sci="201", datos={},
            creado_por=self.usuario, modificado_por=self.usuario,
        )
        avance = resumen_de_emergencia(emergencia)["avance_documental"]
        self.assertEqual(avance["completados"], 2)
        self.assertEqual(avance["total"], 12)
        self.assertEqual(avance["porcentaje"], 17)

    def test_una_emergencia_cerrada_informa_su_duracion_total(self):
        reporte = timezone.now() - timedelta(hours=5)
        emergencia = self.crear_emergencia(
            fecha_reporte=reporte, fecha_cierre=reporte + timedelta(hours=3, minutes=25),
            estado=Emergencia.Estado.CERRADA,
        )
        resumen = resumen_de_emergencia(emergencia)
        self.assertEqual(resumen["duracion"], "3 h 25 min")
        self.assertFalse(resumen["sigue_abierta"])

    def test_una_duracion_de_varios_dias_se_expresa_en_dias(self):
        reporte = timezone.now() - timedelta(days=3)
        emergencia = self.crear_emergencia(
            fecha_reporte=reporte, fecha_cierre=reporte + timedelta(days=2, hours=4),
            estado=Emergencia.Estado.CERRADA,
        )
        self.assertEqual(resumen_de_emergencia(emergencia)["duracion"], "2 d 4 h")

    def test_el_detalle_muestra_el_panel_de_la_emergencia(self):
        emergencia = self.crear_emergencia()
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:detalle", args=[emergencia.pk]))
        self.assertContains(respuesta, "Situación de esta emergencia")
        self.assertContains(respuesta, "Unidades en el sitio")
        self.assertContains(respuesta, "Personal comprometido")
        self.assertContains(respuesta, "Formularios SCI")
