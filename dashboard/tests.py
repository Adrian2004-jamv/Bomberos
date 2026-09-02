from pathlib import Path
from django.conf import settings
from datetime import datetime
from emergencias.models import Emergencia
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, HistorialEstadoRecurso, Recurso, TipoRecurso
from operaciones.models import EvaluacionCapacidadEstacion, RequisitoRecursoCapacidad, TipoCapacidadOperativa
class DashboardInstitucionalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="LAT-DASH")
        cls.cuerpo_uno = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Bomberos Uno",
            sigla="CBU-DASH",
            ruc="0595000000001",
            direccion="Centro",
        )
        cls.cuerpo_dos = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Bomberos Dos",
            sigla="CBD-DASH",
            ruc="0595000000002",
            direccion="Sur",
        )
        cls.estacion_uno = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo_uno,
            nombre="Central Uno",
            codigo="C1-DASH",
            direccion="Centro",
            latitud="-0.900000",
            longitud="-78.600000",
        )
        cls.estacion_uno_b = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo_uno,
            nombre="Norte Uno",
            codigo="N1-DASH",
            direccion="Norte",
            latitud="-0.910000",
            longitud="-78.610000",
        )
        cls.estacion_dos = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo_dos,
            nombre="Central Dos",
            codigo="C2-DASH",
            direccion="Sur",
            latitud="-1.000000",
            longitud="-78.650000",
        )
        categoria_vehiculo = CategoriaRecurso.objects.create(
            nombre="Vehículos", codigo="VEH-DASH"
        )
        categoria_equipo = CategoriaRecurso.objects.create(
            nombre="Equipos", codigo="EQU-DASH"
        )
        cls.tipo_vehiculo = TipoRecurso.objects.create(
            categoria=categoria_vehiculo, nombre="Autobomba", codigo="AUT-DASH"
        )
        cls.tipo_equipo = TipoRecurso.objects.create(
            categoria=categoria_equipo, nombre="Bomba portátil", codigo="BOM-DASH"
        )
        cls.recursos = [
            cls.crear_recurso("U-1", cls.estacion_uno, cls.tipo_vehiculo),
            cls.crear_recurso(
                "U-2",
                cls.estacion_uno,
                cls.tipo_equipo,
                estado=Recurso.EstadoOperativo.FUERA_SERVICIO,
                disponibilidad=Recurso.Disponibilidad.NO_DISPONIBLE,
            ),
            cls.crear_recurso("UB-1", cls.estacion_uno_b, cls.tipo_vehiculo),
            cls.crear_recurso("D-1", cls.estacion_dos, cls.tipo_vehiculo),
            cls.crear_recurso(
                "D-2",
                cls.estacion_dos,
                cls.tipo_equipo,
                estado=Recurso.EstadoOperativo.MANTENIMIENTO,
                disponibilidad=Recurso.Disponibilidad.RESERVADO,
            ),
        ]
        cls.capacidad = TipoCapacidadOperativa.objects.create(
            nombre="Incendio estructural", codigo="IE-DASH"
        )
        RequisitoRecursoCapacidad.objects.create(
            capacidad=cls.capacidad,
            tipo_recurso=cls.tipo_vehiculo,
            cantidad_minima=1,
        )
        cls.usuarios = {}
        cls.usuarios["provincial"] = cls.crear_usuario(
            "provincial-dash", "Responsable provincial", None, "0550000001"
        )
        cls.usuarios["institucional"] = cls.crear_usuario(
            "institucional-dash",
            "Responsable institucional",
            cls.estacion_uno,
            "0550000002",
        )
        cls.usuarios["estacion"] = cls.crear_usuario(
            "estacion-dash",
            "Responsable de estación",
            cls.estacion_uno,
            "0550000003",
        )
        cls.usuarios["encargado"] = cls.crear_usuario(
            "inventario-dash",
            "Encargado de inventario",
            cls.estacion_uno,
            "0550000004",
        )
        cls.usuarios["consulta"] = cls.crear_usuario(
            "consulta-dash",
            "Operador de consulta",
            cls.estacion_uno,
            "0550000005",
        )
        cls.evaluacion_antigua = EvaluacionCapacidadEstacion.objects.create(
            estacion=cls.estacion_uno,
            capacidad=cls.capacidad,
            estado=EvaluacionCapacidadEstacion.Estado.CUMPLE,
            porcentaje_cumplimiento="100.00",
            detalle_recursos=[],
            evaluado_por=cls.usuarios["provincial"],
        )
        cls.evaluacion_reciente = EvaluacionCapacidadEstacion.objects.create(
            estacion=cls.estacion_uno,
            capacidad=cls.capacidad,
            estado=EvaluacionCapacidadEstacion.Estado.NO_CUMPLE,
            porcentaje_cumplimiento="0.00",
            detalle_recursos=[],
            evaluado_por=cls.usuarios["provincial"],
        )
        EvaluacionCapacidadEstacion.objects.filter(
            pk=cls.evaluacion_antigua.pk
        ).update(fecha_evaluacion=timezone.now() - timedelta(days=1))
        cls.evaluacion_otra_institucion = EvaluacionCapacidadEstacion.objects.create(
            estacion=cls.estacion_dos,
            capacidad=cls.capacidad,
            estado=EvaluacionCapacidadEstacion.Estado.CUMPLE,
            porcentaje_cumplimiento="100.00",
            detalle_recursos=[],
            evaluado_por=cls.usuarios["provincial"],
        )

    @classmethod
    def crear_recurso(
        cls,
        codigo,
        estacion,
        tipo,
        estado=Recurso.EstadoOperativo.OPERATIVO,
        disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
    ):
        return Recurso.objects.create(
            estacion=estacion,
            tipo=tipo,
            codigo_interno=codigo,
            nombre=f"Recurso {codigo}",
            estado_operativo=estado,
            disponibilidad=disponibilidad,
        )

    @classmethod
    def crear_usuario(cls, username, grupo, estacion, cedula):
        usuario = get_user_model().objects.create_user(
            username=username,
            cedula=cedula,
            password="clave",
            estacion=estacion,
        )
        usuario.groups.add(Group.objects.get(name=grupo))
        return usuario

    def abrir_dashboard(self, clave):
        self.client.force_login(self.usuarios[clave])
        return self.client.get(reverse("dashboard:principal"))

    def test_acceso_requiere_autenticacion(self):
        respuesta = self.client.get(reverse("dashboard:principal"))
        self.assertRedirects(
            respuesta,
            f'{reverse("usuarios:login")}?next={reverse("dashboard:principal")}',
        )

    def test_usuario_provincial_obtiene_conteos_generales(self):
        respuesta = self.abrir_dashboard("provincial")
        resumen = respuesta.context["resumen"]
        self.assertEqual(resumen["total"], 5)
        self.assertEqual(resumen["operativos"], 3)
        self.assertEqual(resumen["fuera_servicio"], 1)
        self.assertEqual(resumen["disponibles"], 3)
        self.assertEqual(resumen["no_disponibles"], 1)
        self.assertEqual(resumen["estaciones"], 3)

    def test_responsable_institucional_solo_ve_su_cuerpo(self):
        respuesta = self.abrir_dashboard("institucional")
        resumen = respuesta.context["resumen"]
        self.assertEqual(resumen["total"], 3)
        self.assertEqual(resumen["estaciones"], 2)
        self.assertNotContains(respuesta, "Recurso D-1")
        self.assertNotContains(respuesta, self.estacion_dos.nombre)

    def test_responsable_estacion_solo_ve_su_estacion(self):
        respuesta = self.abrir_dashboard("estacion")
        resumen = respuesta.context["resumen"]
        self.assertEqual(resumen["total"], 2)
        self.assertEqual(resumen["estaciones"], 1)
        self.assertEqual(resumen["operativos"], 1)
        self.assertNotContains(respuesta, self.estacion_uno_b.nombre)

    def test_recursos_de_otra_institucion_no_se_contabilizan(self):
        respuesta = self.abrir_dashboard("institucional")
        categorias = {
            item["tipo__categoria__nombre"]: item["total"]
            for item in respuesta.context["categorias"]
        }
        self.assertEqual(categorias, {"Vehículos": 2, "Equipos": 1})

    def test_capacidades_usan_solo_ultima_evaluacion_por_estacion_y_tipo(self):
        respuesta = self.abrir_dashboard("provincial")
        resumen = respuesta.context["resumen"]
        self.assertEqual(resumen["capacidades_cumplidas"], 1)
        self.assertEqual(resumen["capacidades_no_cumplidas"], 1)
        evaluaciones = list(respuesta.context["evaluaciones_recientes"])
        self.assertIn(self.evaluacion_reciente, evaluaciones)
        self.assertNotIn(self.evaluacion_antigua, evaluaciones)

    def test_accesos_rapidos_respetan_permisos(self):
        respuesta_consulta = self.abrir_dashboard("consulta")
        self.assertContains(respuesta_consulta, "Consultar inventario")
        self.assertContains(respuesta_consulta, "Consultar capacidades")
        self.assertNotContains(respuesta_consulta, "Registrar recurso")
        self.assertNotContains(respuesta_consulta, "Ejecutar evaluación")

        respuesta_encargado = self.abrir_dashboard("encargado")
        self.assertContains(respuesta_encargado, "Registrar recurso")
        self.assertNotContains(respuesta_encargado, "Ejecutar evaluación")

        respuesta_responsable = self.abrir_dashboard("estacion")
        self.assertContains(respuesta_responsable, "Ejecutar evaluación")

    def test_actividad_reciente_tiene_limite_controlado(self):
        usuario = self.usuarios["encargado"]
        for indice in range(10):
            HistorialEstadoRecurso.objects.create(
                recurso=self.recursos[0],
                estado_anterior=Recurso.EstadoOperativo.OPERATIVO,
                estado_nuevo=Recurso.EstadoOperativo.MANTENIMIENTO,
                disponibilidad_anterior=Recurso.Disponibilidad.DISPONIBLE,
                disponibilidad_nueva=Recurso.Disponibilidad.NO_DISPONIBLE,
                motivo=f"Actividad {indice}",
                registrado_por=usuario,
            )
        respuesta = self.abrir_dashboard("encargado")
        self.assertEqual(len(respuesta.context["actividad_reciente"]), 8)

class DashboardSinDatosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_superuser(
            username="super-dashboard-vacio",
            cedula="0550000099",
            password="clave",
        )

    def test_dashboard_funciona_sin_recursos_ni_evaluaciones(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("dashboard:principal"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["resumen"]["total"], 0)
        self.assertContains(respuesta, "No existen recursos registrados en su ámbito")
        self.assertContains(
            respuesta,
            "Todavía no se han realizado evaluaciones de capacidades",
        )
        self.assertContains(respuesta, "No hay actividad reciente disponible")


class FiltroYPuntosClaveTests(TestCase):
    """El panel acota por fechas y resume cada emergencia en frases."""

    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="PCL")
        cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Panel", sigla="PCL",
            ruc="0596000001200", direccion="Centro",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo, nombre="Central Panel", codigo="PCL-C",
            direccion="Centro", latitud="-0.930000", longitud="-78.610000",
        )
        cls.usuario = get_user_model().objects.create_user(
            username="panel-clave", cedula="1500000001", password="clave",
            estacion=cls.estacion,
        )
        cls.usuario.groups.add(Group.objects.get(name="Responsable institucional"))

    def crear(self, codigo, dia):
        emergencia = Emergencia.objects.create(
            codigo=codigo, tipo_emergencia="Incendio estructural",
            direccion="Centro", estacion_responsable=self.estacion,
            registrado_por=self.usuario,
        )
        Emergencia.objects.filter(pk=emergencia.pk).update(
            fecha_reporte=timezone.make_aware(datetime(2026, 3, dia, 10, 0))
        )
        return emergencia

    def panel(self, consulta=""):
        self.client.force_login(self.usuario)
        return self.client.get(reverse("dashboard:principal") + consulta)

    def tablero(self, respuesta):
        """Solo el tablero de emergencias: «Actividad reciente» no se filtra."""
        return {item.codigo for item in respuesta.context["incidentes_en_curso"]}

    def test_sin_filtro_se_ven_todas(self):
        self.crear("IE-01032026-001", 1)
        self.crear("IE-10032026-001", 10)
        self.assertEqual(
            self.tablero(self.panel()), {"IE-01032026-001", "IE-10032026-001"}
        )

    def test_el_rango_deja_fuera_lo_anterior(self):
        self.crear("IE-01032026-001", 1)
        self.crear("IE-10032026-001", 10)
        respuesta = self.panel("?desde=2026-03-05&hasta=2026-03-15")
        self.assertEqual(self.tablero(respuesta), {"IE-10032026-001"})

    def test_un_rango_al_reves_se_endereza(self):
        self.crear("IE-10032026-001", 10)
        respuesta = self.panel("?desde=2026-03-15&hasta=2026-03-05")
        self.assertEqual(self.tablero(respuesta), {"IE-10032026-001"})

    def test_una_fecha_ilegible_no_rompe_el_panel(self):
        self.crear("IE-10032026-001", 10)
        respuesta = self.panel("?desde=no-es-fecha")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.tablero(respuesta), {"IE-10032026-001"})

    def test_el_periodo_filtrado_se_anuncia(self):
        self.crear("IE-10032026-001", 10)
        respuesta = self.panel("?desde=2026-03-05&hasta=2026-03-15")
        self.assertContains(respuesta, "entre el 05/03/2026 y el 15/03/2026")

    def test_cada_emergencia_trae_sus_puntos_clave(self):
        self.crear("IE-10032026-001", 10)
        respuesta = self.panel()
        self.assertContains(respuesta, "incident-board__claves")
        self.assertContains(respuesta, "Todavía sin unidades despachadas.")
        self.assertContains(respuesta, "Documentación SCI: 0 de 12 formularios.")


class EstiloDelTableroTests(TestCase):
    """Las reglas que las plantillas dan por existentes deben existir."""

    def hoja(self, ruta):
        return (Path(settings.BASE_DIR) / "static" / ruta).read_text(encoding="utf-8")

    def test_el_boton_principal_tiene_su_regla(self):
        # Se usa en varias plantillas; sin la regla se ve como uno secundario.
        self.assertIn(".button--primary", self.hoja("css/componentes.css"))

    def test_los_puntos_clave_ocupan_la_fila_entera(self):
        hoja = self.hoja("dashboard/css/dashboard.css")
        bloque = hoja[hoja.index(".incident-board__claves"):]
        self.assertIn("grid-column: 1 / -1", bloque[:400])


class FiltroPorIncidenteTests(FiltroYPuntosClaveTests):
    """El tablero se acota a una emergencia concreta o a un tipo."""

    def crear_tipo(self, codigo, dia, tipo):
        emergencia = self.crear(codigo, dia)
        Emergencia.objects.filter(pk=emergencia.pk).update(tipo_emergencia=tipo)
        emergencia.refresh_from_db()
        return emergencia

    def test_se_acota_a_una_sola_emergencia(self):
        una = self.crear("IE-01032026-001", 1)
        self.crear("IE-10032026-001", 10)
        respuesta = self.panel(f"?emergencia={una.pk}")
        self.assertEqual(self.tablero(respuesta), {"IE-01032026-001"})

    def test_se_acota_por_tipo(self):
        self.crear_tipo("IF-01032026-001", 1, "Incendio forestal")
        self.crear_tipo("AV-10032026-001", 10, "Accidente vehicular")
        respuesta = self.panel("?tipo=Incendio forestal")
        self.assertEqual(self.tablero(respuesta), {"IF-01032026-001"})

    def test_un_identificador_absurdo_no_rompe_el_panel(self):
        self.crear("IE-10032026-001", 10)
        respuesta = self.panel("?emergencia=no-es-numero")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.tablero(respuesta), {"IE-10032026-001"})

    def test_el_desplegable_se_arma_con_lo_del_ambito(self):
        self.crear("IE-10032026-001", 10)
        respuesta = self.panel()
        codigos = {item["codigo"] for item in respuesta.context["emergencias_del_filtro"]}
        self.assertEqual(codigos, {"IE-10032026-001"})

    def test_el_desplegable_no_ofrece_emergencias_de_otro_ambito(self):
        self.crear("IE-10032026-001", 10)
        otro_canton = Canton.objects.create(nombre="Salcedo", codigo="PCX")
        otro_cuerpo = CuerpoBomberos.objects.create(
            canton=otro_canton, nombre="Bomberos Ajenos", sigla="PCX",
            ruc="0596000001300", direccion="Centro",
        )
        otra = Estacion.objects.create(
            cuerpo_bomberos=otro_cuerpo, nombre="Ajena", codigo="PCX-C",
            direccion="Centro", latitud="-1.000000", longitud="-78.600000",
        )
        Emergencia.objects.create(
            codigo="IE-99992026-999", tipo_emergencia="Incendio estructural",
            direccion="Otro sitio", estacion_responsable=otra,
            registrado_por=self.usuario,
        )
        respuesta = self.panel()
        codigos = {item["codigo"] for item in respuesta.context["emergencias_del_filtro"]}
        self.assertNotIn("IE-99992026-999", codigos)

    def test_se_explica_de_donde_salen_los_tiempos(self):
        self.crear("IE-10032026-001", 10)
        respuesta = self.panel()
        self.assertContains(respuesta, "los calcula el sistema solo")
        self.assertContains(respuesta, "150 m de la dirección")
