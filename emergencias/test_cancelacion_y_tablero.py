"""El tablero de formularios por periodo, y descartar un incidente que no existió.

Dos cosas que se ven mal desde la escena:

* En un incidente reactivado todos los formularios seguían en verde —«finalizado»—
  porque el tablero miraba el último de cada código sin importar el periodo. Parecía
  que la emergencia de ahora ya había terminado cuando en realidad es una fase
  nueva. Cada periodo lleva sus propios formularios, y el tablero pinta los del
  vigente; lo del anterior consta aparte.
* Una llamada falsa o una broma no tenía salida limpia: el incidente se quedaba en
  el sistema, contando en las estadísticas. Ahora se descarta según el motivo.
"""

import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from instituciones.models import Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso

from .models import (DespliegueUnidad, Emergencia, FormularioSCI, FormularioSCI211,
                     PeriodoOperacional, PosicionUnidad, RegistroRecursoSCI211)
from .services import desplegar_unidad, reactivar_emergencia
from .services_sci import crear_sci211_desde_emergencia
from .test_periodo_operacional import BaseDelPeriodo
from .views import emergencias_permitidas


def estados_del_tablero(html):
    """{codigo: clave de estado} de las tarjetas de formularios de la ficha."""
    return {
        codigo: estado
        for estado, codigo in re.findall(
            r'class="sci-form-tab sci-form-tab--(\w+)" href="[^"]*/formularios-sci/(\d+)/', html
        )
    }


class TableroPorPeriodoTests(BaseDelPeriodo):
    def ficha(self, emergencia):
        self.client.force_login(self.usuario)
        return self.client.get(
            reverse("emergencias:detalle", args=[emergencia.pk])
        ).content.decode()

    def incidente_terminado_con_todo_finalizado(self, codigo="TAB-001"):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA, codigo)
        for sci in ("201", "202", "207"):
            self.crear_formulario(
                emergencia, sci, estado=FormularioSCI.Estado.FINALIZADO,
                datos={"lugar_incidente": "x", "objetivos": "x"},
            )
        return emergencia

    def test_en_el_periodo_uno_lo_finalizado_se_ve_finalizado(self):
        emergencia = self.incidente_terminado_con_todo_finalizado()
        estados = estados_del_tablero(self.ficha(emergencia))
        for sci in ("201", "202", "207"):
            self.assertEqual(estados[sci], "complete", sci)

    def test_al_reactivar_el_tablero_vuelve_a_empezar(self):
        """El caso: periodo 2 y todo en verde."""
        emergencia = self.incidente_terminado_con_todo_finalizado("TAB-002")
        reactivar_emergencia(emergencia, self.usuario, "Rebrote")
        html = self.ficha(emergencia)
        estados = estados_del_tablero(html)
        self.assertNotIn("complete", estados.values(), estados)
        for sci in ("201", "202", "207"):
            self.assertEqual(estados[sci], "pending", sci)

    def test_lo_del_periodo_anterior_consta_pero_no_se_pinta_como_actual(self):
        emergencia = self.incidente_terminado_con_todo_finalizado("TAB-003")
        reactivar_emergencia(emergencia, self.usuario, "Rebrote")
        html = self.ficha(emergencia)
        self.assertIn("Antes: P1 finalizado", html)
        # Y el historial sigue ahí, intacto.
        self.assertEqual(
            FormularioSCI.objects.filter(
                emergencia=emergencia, estado=FormularioSCI.Estado.FINALIZADO
            ).count(),
            3,
        )

    def test_un_borrador_del_periodo_nuevo_se_ve_como_incompleto(self):
        emergencia = self.incidente_terminado_con_todo_finalizado("TAB-004")
        nuevo = reactivar_emergencia(emergencia, self.usuario, "Rebrote")
        self.crear_formulario(emergencia, "202", periodo=nuevo, datos={"objetivos": "Fase 2"})
        estados = estados_del_tablero(self.ficha(emergencia))
        self.assertEqual(estados["202"], "incomplete")
        self.assertEqual(estados["201"], "pending")

    def test_el_listado_cuenta_solo_lo_del_periodo_vigente(self):
        emergencia = self.incidente_terminado_con_todo_finalizado("TAB-005")
        antes = emergencias_permitidas(self.usuario).get(pk=emergencia.pk)
        self.assertEqual(antes.formularios_registrados, 3)
        reactivar_emergencia(emergencia, self.usuario, "Rebrote")
        despues = emergencias_permitidas(self.usuario).get(pk=emergencia.pk)
        self.assertEqual(despues.formularios_registrados, 0)
        self.assertFalse(despues.tiene_sci211)


class SCI211PorPeriodoTests(BaseDelPeriodo):
    """El 211 era uno por emergencia: en el periodo 2 no se podía crear otro."""

    def finalizar_211_del_periodo_uno(self, emergencia):
        formulario = FormularioSCI211.objects.create(
            emergencia=emergencia, codigo=f"SCI-211-{emergencia.codigo}",
            punto_registro="Puesto de Comando", registrador_1="Registrador",
            creado_por=self.usuario, modificado_por=self.usuario,
            estado=FormularioSCI211.Estado.FINALIZADO,
        )
        return formulario

    def test_el_211_nace_en_el_periodo_vigente(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "S211-001")
        formulario = crear_sci211_desde_emergencia(emergencia, self.usuario)
        self.assertEqual(formulario.numero_periodo, 1)

    def test_en_el_periodo_dos_se_puede_abrir_un_211_nuevo(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA, "S211-002")
        viejo = self.finalizar_211_del_periodo_uno(emergencia)
        reactivar_emergencia(emergencia, self.usuario, "Rebrote")
        emergencia = Emergencia.objects.get(pk=emergencia.pk)

        # El vigente todavía no existe: el del periodo 1 no cuenta como «el de ahora».
        self.assertIsNone(emergencia.formulario_sci_211)
        nuevo = crear_sci211_desde_emergencia(emergencia, self.usuario)

        self.assertEqual(nuevo.numero_periodo, 2)
        self.assertTrue(nuevo.codigo.endswith("-P2"))
        self.assertTrue(nuevo.es_editable)
        self.assertEqual(emergencia.formulario_sci_211.pk, nuevo.pk)
        # El anterior sigue como estaba: finalizado, del periodo 1 y sin poder tocarse.
        viejo.refresh_from_db()
        self.assertEqual(viejo.numero_periodo, 1)
        self.assertEqual(viejo.estado, FormularioSCI211.Estado.FINALIZADO)
        self.assertFalse(viejo.es_editable)

    def test_no_caben_dos_211_en_el_mismo_periodo(self):
        from django.db import IntegrityError, transaction

        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "S211-003")
        crear_sci211_desde_emergencia(emergencia, self.usuario)
        with self.assertRaises(IntegrityError), transaction.atomic():
            FormularioSCI211.objects.create(
                emergencia=emergencia, periodo=emergencia.periodo_vigente(),
                codigo="OTRO-CODIGO", punto_registro="PC", registrador_1="R",
                creado_por=self.usuario, modificado_por=self.usuario,
            )

    def test_el_boton_de_crear_el_211_funciona_en_el_periodo_dos(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA, "S211-004")
        self.finalizar_211_del_periodo_uno(emergencia)
        reactivar_emergencia(emergencia, self.usuario, "Rebrote")
        self.client.force_login(self.usuario)
        respuesta = self.client.post(reverse("emergencias:sci211_crear", args=[emergencia.pk]))
        nuevo = FormularioSCI211.objects.get(emergencia=emergencia, periodo__numero=2)
        self.assertRedirects(
            respuesta, reverse("emergencias:sci211_editar", args=[nuevo.pk]),
            fetch_redirect_response=False,
        )

    def test_el_tablero_ofrece_el_211_como_registro_abierto_en_el_periodo_dos(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA, "S211-005")
        self.finalizar_211_del_periodo_uno(emergencia)
        reactivar_emergencia(emergencia, self.usuario, "Rebrote")
        self.client.force_login(self.usuario)
        html = self.client.get(
            reverse("emergencias:detalle", args=[emergencia.pk])
        ).content.decode()
        self.assertEqual(estados_del_tablero(html)["211"], "open")
        self.assertIn("Antes: P1 finalizado", html)


class ConUnidades(BaseDelPeriodo):
    def crear_unidad(self, codigo="AB-CAN-01"):
        categoria, _ = CategoriaRecurso.objects.get_or_create(
            codigo="CAT-CAN", defaults={"nombre": "Vehículos"}
        )
        tipo, _ = TipoRecurso.objects.get_or_create(
            categoria=categoria, codigo="TIP-CAN",
            defaults={"nombre": "Autobomba", "es_unidad_desplegable": True},
        )
        return Recurso.objects.create(
            estacion=self.estacion, tipo=tipo, codigo_interno=codigo, nombre="Autobomba",
            estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
            disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
            fecha_confirmacion_disponibilidad=timezone.now(),
        )

    def incidente_con_todo(self, codigo="CAN-001"):
        """Una unidad despachada, un 201 y un 211 con un registro ligado al despliegue."""
        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, codigo)
        unidad = self.crear_unidad(f"AB-{codigo}")
        desplegar_unidad(emergencia, unidad, self.usuario, "Salida por un aviso dudoso")
        self.crear_formulario(emergencia, "201", datos={"lugar_incidente": "Calle falsa"})
        crear_sci211_desde_emergencia(emergencia, self.usuario)
        unidad.refresh_from_db()
        self.assertEqual(unidad.disponibilidad, Recurso.Disponibilidad.ASIGNADO)
        return emergencia, unidad

    def cancelar(self, emergencia, motivo, **extra):
        self.client.force_login(self.usuario)
        return self.client.post(
            reverse("emergencias:cancelar", args=[emergencia.pk]),
            {"motivo": motivo, **extra},
        )


class EliminarFalsasAlarmasTests(ConUnidades):
    """«Falsa alarma» (la broma incluida): el incidente no existió y no debe quedar."""

    def test_se_elimina_sin_dejar_nada_huerfano(self):
        for motivo in ("falsa_alarma",):
            with self.subTest(motivo=motivo):
                emergencia, unidad = self.incidente_con_todo(f"CAN-{motivo[:3].upper()}")
                pk = emergencia.pk
                self.assertEqual(RegistroRecursoSCI211.objects.filter(formulario__emergencia_id=pk).count(), 1)

                respuesta = self.cancelar(emergencia, motivo, confirmo="1")

                self.assertRedirects(
                    respuesta, reverse("emergencias:lista"), fetch_redirect_response=False
                )
                self.assertFalse(Emergencia.objects.filter(pk=pk).exists())
                # Nada de lo que colgaba de ella sigue en la base...
                self.assertEqual(DespliegueUnidad.objects.filter(emergencia_id=pk).count(), 0)
                self.assertEqual(PosicionUnidad.objects.filter(despliegue__emergencia_id=pk).count(), 0)
                self.assertEqual(FormularioSCI.objects.filter(emergencia_id=pk).count(), 0)
                self.assertEqual(FormularioSCI211.objects.filter(emergencia_id=pk).count(), 0)
                self.assertEqual(PeriodoOperacional.objects.filter(emergencia_id=pk).count(), 0)
                # ...ni quedó una fila apuntando a un padre que ya no existe.
                self.assertEqual(
                    RegistroRecursoSCI211.objects.exclude(
                        formulario__in=FormularioSCI211.objects.all()
                    ).count(), 0,
                )
                # La unidad vuelve al inventario: si no, quedaría «asignada» a una
                # emergencia que no existe y no se volvería a ofrecer nunca.
                unidad.refresh_from_db()
                self.assertEqual(unidad.disponibilidad, Recurso.Disponibilidad.DISPONIBLE)

    def test_no_cuenta_en_las_estadisticas(self):
        emergencia, _ = self.incidente_con_todo("CAN-EST")
        antes = Emergencia.objects.count()
        self.cancelar(emergencia, "falsa_alarma", confirmo="1")
        self.assertEqual(Emergencia.objects.count(), antes - 1)

    def test_el_motivo_retirado_ya_no_se_acepta(self):
        """Una petición hecha a mano con «broma» no debe borrar ni cancelar nada."""
        emergencia, _ = self.incidente_con_todo("CAN-BRO")
        self.cancelar(emergencia, "broma", confirmo="1")
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.EN_ATENCION)

    def test_el_servidor_exige_la_confirmacion(self):
        """El navegador la pide, pero este extremo atiende peticiones de cualquiera."""
        emergencia, _ = self.incidente_con_todo("CAN-CONF")
        respuesta = self.cancelar(emergencia, "falsa_alarma")  # sin «confirmo»
        self.assertTrue(Emergencia.objects.filter(pk=emergencia.pk).exists())
        pagina = self.client.get(respuesta["Location"])
        # El texto del propio diálogo también dice «no se puede deshacer»: se busca
        # el del mensaje, que es lo que demuestra que el servidor lo rechazó.
        self.assertContains(pagina, "confirme que entiende")

    def test_queda_constancia_en_el_registro_del_servidor(self):
        emergencia, _ = self.incidente_con_todo("CAN-LOG")
        with self.assertLogs("emergencias.services", level="WARNING") as registro:
            self.cancelar(emergencia, "falsa_alarma", confirmo="1")
        texto = " ".join(registro.output)
        self.assertIn("CAN-LOG", texto)
        self.assertIn(self.usuario.username, texto)

    def test_con_formularios_finalizados_no_se_elimina(self):
        """Un expediente con documentos cerrados no se borra por un clic."""
        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "CAN-FIN")
        self.crear_formulario(
            emergencia, "201", estado=FormularioSCI.Estado.FINALIZADO, datos={"lugar_incidente": "x"},
        )
        respuesta = self.cancelar(emergencia, "falsa_alarma", confirmo="1")
        self.assertTrue(Emergencia.objects.filter(pk=emergencia.pk).exists())
        self.assertContains(self.client.get(respuesta["Location"]), "formularios finalizados")

    def test_con_mas_de_un_periodo_no_se_elimina(self):
        """Hubo actividad real en el periodo anterior y debe conservarse."""
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA, "CAN-P2")
        reactivar_emergencia(emergencia, self.usuario, "Rebrote")
        respuesta = self.cancelar(emergencia, "falsa_alarma", confirmo="1")
        self.assertTrue(Emergencia.objects.filter(pk=emergencia.pk).exists())
        self.assertContains(self.client.get(respuesta["Location"]), "más de un periodo")


class CancelarPorOtrosMotivosTests(ConUnidades):
    def test_un_error_de_despacho_deja_el_incidente_cancelado_con_su_motivo(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "CAN-ERR")
        self.cancelar(emergencia, "error_despacho", detalle="Era de otra jurisdicción")
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.CANCELADA)
        self.assertEqual(emergencia.motivo_cancelacion, "error_despacho")
        self.assertEqual(emergencia.detalle_cancelacion, "Era de otra jurisdicción")
        self.assertIsNotNone(emergencia.fecha_cierre)
        # Y sale de «en atención».
        self.assertNotIn(
            Emergencia.Estado.CANCELADA, {Emergencia.Estado.EN_ATENCION, Emergencia.Estado.REPORTADA}
        )

    def test_la_ficha_muestra_el_motivo(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "CAN-VER")
        self.cancelar(emergencia, "error_despacho", detalle="Era de otra jurisdicción")
        pagina = self.client.get(reverse("emergencias:detalle", args=[emergencia.pk]))
        self.assertContains(pagina, "Motivo de la cancelación")
        self.assertContains(pagina, "Error de despacho")
        self.assertContains(pagina, "Era de otra jurisdicción")

    def test_otro_motivo_exige_describirlo(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "CAN-OTRO")
        respuesta = self.cancelar(emergencia, "otro")
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.EN_ATENCION)
        self.assertContains(self.client.get(respuesta["Location"]), "Describa el motivo")
        self.cancelar(emergencia, "otro", detalle="Se resolvió por teléfono")
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.CANCELADA)

    def test_un_motivo_inventado_se_rechaza(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "CAN-INV")
        self.cancelar(emergencia, "porque_si")
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.EN_ATENCION)

    def test_con_una_unidad_en_la_escena_no_se_cancela(self):
        """La regla de siempre: la unidad quedaría asignada a un incidente terminado."""
        emergencia, _ = self.incidente_con_todo("CAN-UNI")
        respuesta = self.cancelar(emergencia, "error_despacho")
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.EN_ATENCION)
        self.assertContains(
            self.client.get(respuesta["Location"]), "Todavía hay unidades en la emergencia"
        )

    def test_una_emergencia_terminada_no_se_cancela_ni_se_elimina(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA, "CAN-TERM")
        for motivo in ("falsa_alarma", "error_despacho"):
            self.cancelar(emergencia, motivo, confirmo="1")
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.CERRADA)

    def test_quien_no_gestiona_no_puede_descartar(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "CAN-PERM")
        consulta = get_user_model().objects.create_user(
            username="consulta.cancelar", password="clave-de-prueba",
            cedula="0500000399", estacion=self.estacion,
        )
        consulta.groups.add(Group.objects.get(name="Operador de consulta"))
        self.client.force_login(consulta)
        self.client.post(
            reverse("emergencias:cancelar", args=[emergencia.pk]),
            {"motivo": "falsa_alarma", "confirmo": "1"},
        )
        self.assertTrue(Emergencia.objects.filter(pk=emergencia.pk).exists())

    def test_una_estacion_ajena_ni_siquiera_la_ve(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "CAN-AJENA")
        otra = Estacion.objects.create(
            cuerpo_bomberos=self.estacion.cuerpo_bomberos, nombre="Otra Estación",
            codigo="EP-OTRA", direccion="Otra", latitud="-0.940000", longitud="-78.620000",
        )
        ajeno = get_user_model().objects.create_user(
            username="mando.ajeno", password="clave-de-prueba", cedula="0500000398", estacion=otra,
        )
        ajeno.groups.add(Group.objects.get(name="Responsable de estación"))
        self.client.force_login(ajeno)
        respuesta = self.client.post(
            reverse("emergencias:cancelar", args=[emergencia.pk]),
            {"motivo": "falsa_alarma", "confirmo": "1"},
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(Emergencia.objects.filter(pk=emergencia.pk).exists())

    def test_solo_se_acepta_post(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "CAN-GET")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:cancelar", args=[emergencia.pk]))
        self.assertEqual(respuesta.status_code, 405)


class FichaConElBotonDeCancelarTests(ConUnidades):
    def ficha(self, emergencia):
        self.client.force_login(self.usuario)
        return self.client.get(
            reverse("emergencias:detalle", args=[emergencia.pk])
        ).content.decode()

    def test_una_emergencia_en_curso_ofrece_cancelar_con_los_tres_motivos(self):
        html = self.ficha(self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "FIC-001"))
        self.assertIn('data-abrir-dialogo="dialogo-cancelar"', html)
        self.assertIn('id="dialogo-cancelar"', html)
        for valor in ("falsa_alarma", "error_despacho", "otro"):
            self.assertIn(f'value="{valor}"', html)
        # «Broma» era una segunda forma de decir «falsa alarma»: ya no se ofrece.
        self.assertNotIn('value="broma"', html)
        # La falsa alarma elimina y lo advierte; los otros dos no piden la casilla.
        self.assertEqual(html.count('data-elimina="1"'), 1)
        self.assertEqual(html.count('data-elimina="0"'), 2)

    def test_una_emergencia_terminada_no_lo_ofrece(self):
        html = self.ficha(self.crear_emergencia(Emergencia.Estado.CERRADA, "FIC-002"))
        self.assertNotIn('id="dialogo-cancelar"', html)
        self.assertNotIn('data-abrir-dialogo="dialogo-cancelar"', html)

    def test_cancelar_ya_no_es_uno_de_los_botones_de_fase(self):
        """Tiene su propio flujo: pide el motivo y el motivo decide qué pasa."""
        html = self.ficha(self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "FIC-003"))
        fases = re.findall(r'<input type="hidden" name="estado" value="(\w+)"', html)
        self.assertEqual(sorted(fases), ["cerrada", "controlada"])
