"""El periodo operacional del incidente y la inmutabilidad de lo ya escrito.

Un expediente de incidente es un documento legal: lo que se declaró en una fase
no se reescribe en la siguiente. Cuando una emergencia cerrada vuelve a
activarse —el rescoldo que reaviva, la estructura que cede tras darla por
controlada— no se reabre el periodo anterior, se abre el siguiente, y lo del
anterior queda como quedó.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion

from .models import Emergencia, FormularioSCI, PeriodoOperacional
from .services import periodo_actual, reactivar_emergencia


class BaseDelPeriodo(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Periodo", codigo="PER-T")
        cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Periodo", sigla="PER-T",
            ruc="0599999999031", direccion="Dirección institucional",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo, nombre="Estación Periodo", codigo="EP-PER",
            direccion="Centro", latitud="-0.930000", longitud="-78.610000",
        )
        cls.usuario = get_user_model().objects.create_user(
            username="mando.periodo", password="clave-de-prueba",
            cedula="0500000301", estacion=cls.estacion,
        )
        cls.usuario.groups.add(Group.objects.get(name="Responsable de estación"))

    def crear_emergencia(self, estado=Emergencia.Estado.EN_ATENCION, codigo="PER-001"):
        return Emergencia.objects.create(
            codigo=codigo, tipo_emergencia="Incendio estructural",
            fecha_reporte=timezone.now(), direccion="Calle de prueba",
            estado=estado, estacion_responsable=self.estacion,
            registrado_por=self.usuario,
            fecha_cierre=timezone.now()
            if estado in {Emergencia.Estado.CERRADA, Emergencia.Estado.CANCELADA}
            else None,
        )

    def crear_formulario(self, emergencia, codigo="202", periodo=None, **extra):
        return FormularioSCI.objects.create(
            emergencia=emergencia, codigo_sci=codigo,
            periodo=periodo or periodo_actual(emergencia),
            datos=extra.pop("datos", {"objetivos": "Controlar el fuego"}),
            creado_por=self.usuario, modificado_por=self.usuario, **extra,
        )


class PeriodoInicialTests(BaseDelPeriodo):
    def test_toda_emergencia_tiene_su_periodo_uno(self):
        emergencia = self.crear_emergencia()
        periodo = periodo_actual(emergencia)
        self.assertEqual(periodo.numero, 1)
        self.assertTrue(periodo.esta_abierto)

    def test_pedirlo_dos_veces_no_crea_dos(self):
        emergencia = self.crear_emergencia()
        primero = periodo_actual(emergencia)
        self.assertEqual(periodo_actual(emergencia).pk, primero.pk)
        self.assertEqual(emergencia.periodos.count(), 1)

    def test_el_periodo_no_puede_terminar_antes_de_empezar(self):
        emergencia = self.crear_emergencia()
        periodo = periodo_actual(emergencia)
        periodo.fin = periodo.inicio - timezone.timedelta(hours=1)
        with self.assertRaises(ValidationError):
            periodo.full_clean()


class ReactivarTests(BaseDelPeriodo):
    def test_reactivar_abre_el_periodo_siguiente(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA)
        periodo_actual(emergencia)
        nuevo = reactivar_emergencia(emergencia, self.usuario, "Rebrote en el ala norte")
        emergencia.refresh_from_db()
        self.assertEqual(nuevo.numero, 2)
        self.assertTrue(nuevo.esta_abierto)
        self.assertEqual(nuevo.motivo, "Rebrote en el ala norte")
        self.assertEqual(nuevo.abierto_por, self.usuario)
        self.assertEqual(emergencia.estado, Emergencia.Estado.EN_ATENCION)
        self.assertIsNone(emergencia.fecha_cierre)

    def test_el_periodo_anterior_queda_cerrado(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA)
        primero = periodo_actual(emergencia)
        reactivar_emergencia(emergencia, self.usuario, "Rebrote")
        primero.refresh_from_db()
        self.assertFalse(primero.esta_abierto)
        self.assertGreaterEqual(primero.fin, primero.inicio)

    def test_una_emergencia_en_curso_no_se_reactiva(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION)
        with self.assertRaises(ValidationError) as caso:
            reactivar_emergencia(emergencia, self.usuario, "Porque sí")
        self.assertIn("sigue en curso", " ".join(caso.exception.messages))

    def test_el_motivo_es_obligatorio(self):
        """Queda en el expediente como la justificación del periodo nuevo."""
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA)
        for vacio in ("", "   ", None):
            with self.subTest(motivo=vacio):
                with self.assertRaises(ValidationError) as caso:
                    reactivar_emergencia(emergencia, self.usuario, vacio)
                self.assertIn("por qué", " ".join(caso.exception.messages))

    def test_reactivar_dos_veces_llega_al_periodo_tres(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA)
        reactivar_emergencia(emergencia, self.usuario, "Primer rebrote")
        emergencia.refresh_from_db()
        emergencia.estado = Emergencia.Estado.CERRADA
        emergencia.fecha_cierre = timezone.now()
        emergencia.save(update_fields=["estado", "fecha_cierre"])
        tercero = reactivar_emergencia(emergencia, self.usuario, "Segundo rebrote")
        self.assertEqual(tercero.numero, 3)
        self.assertEqual(
            [p.numero for p in emergencia.periodos.order_by("numero")], [1, 2, 3]
        )

    def test_la_puerta_ordinaria_sigue_sin_reabrir_nada(self):
        """Reactivar no puede colarse por el cambio de estado de siempre.

        Si «cambiar_estado_emergencia» aceptara salir de CERRADA, se podría
        reabrir una emergencia sin abrir periodo, y los formularios del periodo
        anterior volverían a ser editables. El mapa de transiciones lo impide y
        esta guarda vigila que siga impidiéndolo.
        """
        from .services import TRANSICIONES_EMERGENCIA, cambiar_estado_emergencia

        self.assertEqual(TRANSICIONES_EMERGENCIA[Emergencia.Estado.CERRADA], set())
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA)
        with self.assertRaises(ValidationError):
            cambiar_estado_emergencia(
                emergencia, Emergencia.Estado.EN_ATENCION, self.usuario
            )


class InmutabilidadTests(BaseDelPeriodo):
    def test_un_borrador_de_periodo_cerrado_deja_de_ser_editable(self):
        """El candado del periodo manda sobre el del documento.

        Un borrador a medias cuando se cerró el periodo se queda a medias: eso
        es lo que pasó y lo que el expediente debe mostrar.
        """
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA)
        formulario = self.crear_formulario(emergencia)
        self.assertTrue(formulario.es_editable)
        reactivar_emergencia(emergencia, self.usuario, "Rebrote")
        formulario.refresh_from_db()
        self.assertEqual(formulario.estado, FormularioSCI.Estado.BORRADOR)
        self.assertFalse(formulario.es_editable)

    def test_el_mismo_codigo_convive_en_dos_periodos(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA)
        viejo = self.crear_formulario(emergencia, "202", datos={"objetivos": "Fase 1"})
        nuevo_periodo = reactivar_emergencia(emergencia, self.usuario, "Rebrote")
        reciente = self.crear_formulario(
            emergencia, "202", periodo=nuevo_periodo, datos={"objetivos": "Fase 2"},
        )
        self.assertNotEqual(viejo.pk, reciente.pk)
        viejo.refresh_from_db()
        self.assertEqual(viejo.datos["objetivos"], "Fase 1")
        self.assertEqual(reciente.datos["objetivos"], "Fase 2")
        self.assertEqual(
            FormularioSCI.objects.filter(emergencia=emergencia, codigo_sci="202").count(),
            2,
        )

    def test_no_caben_dos_del_mismo_codigo_en_un_periodo(self):
        from django.db import IntegrityError, transaction

        emergencia = self.crear_emergencia()
        periodo = periodo_actual(emergencia)
        self.crear_formulario(emergencia, "202", periodo=periodo)
        with self.assertRaises(IntegrityError), transaction.atomic():
            FormularioSCI.objects.create(
                emergencia=emergencia, codigo_sci="202", periodo=periodo,
                creado_por=self.usuario, modificado_por=self.usuario,
            )


class RutasDelPeriodoTests(BaseDelPeriodo):
    """Las rutas «…/periodo/<n>/…» respondían con un error 500.

    Existían desde que se añadió el número de periodo, pero las vistas no
    recibían ese argumento: Django las llamaba con un parámetro que no estaba en
    su firma. Abrir un periodo nuevo llevaba justo a esa pantalla.
    """

    def test_las_tres_rutas_responden(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA)
        self.crear_formulario(emergencia, "202")
        nuevo = reactivar_emergencia(emergencia, self.usuario, "Rebrote")
        self.crear_formulario(emergencia, "202", periodo=nuevo)
        self.client.force_login(self.usuario)

        for numero in (1, 2):
            with self.subTest(periodo=numero, vista="visualizar"):
                respuesta = self.client.get(reverse(
                    "emergencias:sci_visualizar_periodo",
                    kwargs={"codigo": "202", "emergencia_pk": emergencia.pk,
                            "periodo": numero},
                ))
                self.assertEqual(respuesta.status_code, 200)

    def test_editar_el_periodo_cerrado_redirige_a_la_consulta(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA)
        self.crear_formulario(emergencia, "202")
        reactivar_emergencia(emergencia, self.usuario, "Rebrote")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci_editar_periodo",
                    kwargs={"codigo": "202", "emergencia_pk": emergencia.pk,
                            "periodo": 1}),
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "periodo operacional 1, cerrado")

    def test_editar_el_periodo_abierto_funciona(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA)
        self.crear_formulario(emergencia, "202")
        nuevo = reactivar_emergencia(emergencia, self.usuario, "Rebrote")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse(
            "emergencias:sci_editar_periodo",
            kwargs={"codigo": "202", "emergencia_pk": emergencia.pk,
                    "periodo": nuevo.numero},
        ))
        self.assertEqual(respuesta.status_code, 200)

    def test_un_periodo_que_no_existe_es_404(self):
        emergencia = self.crear_emergencia()
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse(
            "emergencias:sci_visualizar_periodo",
            kwargs={"codigo": "202", "emergencia_pk": emergencia.pk, "periodo": 9},
        ))
        self.assertEqual(respuesta.status_code, 404)


class VistaDeReactivarTests(BaseDelPeriodo):
    def test_la_ficha_ofrece_reactivar_solo_si_termino(self):
        self.client.force_login(self.usuario)
        en_curso = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "PER-CURSO")
        respuesta = self.client.get(reverse("emergencias:detalle", args=[en_curso.pk]))
        self.assertNotContains(respuesta, "Reactivar la emergencia")

        cerrada = self.crear_emergencia(Emergencia.Estado.CERRADA, "PER-CERR")
        respuesta = self.client.get(reverse("emergencias:detalle", args=[cerrada.pk]))
        self.assertContains(respuesta, "Reactivar la emergencia")

    def test_reactivar_desde_la_vista(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA, "PER-POST")
        self.client.force_login(self.usuario)
        respuesta = self.client.post(
            reverse("emergencias:reactivar", args=[emergencia.pk]),
            {"motivo": "Rebrote confirmado por la unidad en sitio"},
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.EN_ATENCION)
        self.assertEqual(emergencia.periodos.count(), 2)
        self.assertContains(respuesta, "periodo operacional 2")

    def test_sin_motivo_la_vista_no_reactiva(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA, "PER-SINMOT")
        self.client.force_login(self.usuario)
        respuesta = self.client.post(
            reverse("emergencias:reactivar", args=[emergencia.pk]),
            {"motivo": "   "}, follow=True,
        )
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.CERRADA)
        self.assertEqual(emergencia.periodos.count(), 1)
        self.assertContains(respuesta, "por qué")

    def test_el_historial_aparece_con_dos_periodos(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA, "PER-HIST")
        reactivar_emergencia(emergencia, self.usuario, "Rebrote del ala norte")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:detalle", args=[emergencia.pk]))
        self.assertContains(respuesta, "Periodos operacionales")
        self.assertContains(respuesta, "Rebrote del ala norte")
        self.assertContains(respuesta, "Solo lectura")


class TerminarLaEmergenciaDesdeLaFichaTests(BaseDelPeriodo):
    """Terminar un incidente no tenía botón en ninguna pantalla.

    La ruta «<pk>/estado/» y su vista existían y funcionaban desde el principio,
    pero ninguna plantilla las ofrecía: se podía abrir una emergencia y no
    cerrarla. Y como el SCI-211 y el SCI-214 son bitácoras que solo se finalizan
    cuando la emergencia termina, la documentación del incidente se quedaba
    abierta para siempre. El usuario lo encontró al intentar cerrar sus
    formularios.
    """

    def test_la_ficha_ofrece_las_fases_a_las_que_puede_pasar(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "FASE-CURSO")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:detalle", args=[emergencia.pk]))
        self.assertContains(respuesta, "Fase del incidente")
        ofrecidas = {t["valor"] for t in respuesta.context["transiciones_emergencia"]}
        self.assertEqual(
            ofrecidas,
            {Emergencia.Estado.CONTROLADA, Emergencia.Estado.CERRADA,
             Emergencia.Estado.CANCELADA},
        )
        self.assertContains(
            respuesta, reverse("emergencias:cambiar_estado", args=[emergencia.pk])
        )

    def test_terminar_la_emergencia_desde_la_ficha(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "FASE-CIERRA")
        self.client.force_login(self.usuario)
        respuesta = self.client.post(
            reverse("emergencias:cambiar_estado", args=[emergencia.pk]),
            {"estado": Emergencia.Estado.CERRADA}, follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.CERRADA)
        self.assertIsNotNone(emergencia.fecha_cierre)

    def test_cerrada_ya_no_ofrece_fases_pero_si_reactivar(self):
        """De CERRADA solo se sale reactivando, que abre un periodo nuevo."""
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA, "FASE-FIN")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:detalle", args=[emergencia.pk]))
        self.assertEqual(respuesta.context["transiciones_emergencia"], [])
        self.assertNotContains(respuesta, "Fase del incidente")
        self.assertContains(respuesta, "Reactivar la emergencia")

    def test_terminar_permite_cerrar_la_bitacora_que_esperaba(self):
        """Es la cadena entera: sin el botón, el SCI-214 no se cerraba nunca."""
        from .services_sci import finalizar_sci

        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "FASE-214")
        bitacora = self.crear_formulario(
            emergencia, "214",
            datos={"actividades": [{"hora": "09:15", "evento": "Arribo"}]},
            preparado_por="Luis Herrera",
        )
        with self.assertRaises(ValidationError) as caso:
            finalizar_sci(bitacora, self.usuario)
        self.assertIn("cuando la emergencia termina", " ".join(caso.exception.messages))

        self.client.force_login(self.usuario)
        self.client.post(
            reverse("emergencias:cambiar_estado", args=[emergencia.pk]),
            {"estado": Emergencia.Estado.CERRADA},
        )
        bitacora.refresh_from_db()
        cerrada = finalizar_sci(bitacora, self.usuario)
        self.assertEqual(cerrada.estado, FormularioSCI.Estado.FINALIZADO)

    def test_quien_solo_consulta_no_ve_las_fases(self):
        from django.contrib.auth.models import Group

        consulta = get_user_model().objects.create_user(
            username="consulta.fase", password="clave-de-prueba",
            cedula="0500000302", estacion=self.estacion,
        )
        consulta.groups.add(Group.objects.get(name="Operador de consulta"))
        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "FASE-CONS")
        self.client.force_login(consulta)
        respuesta = self.client.get(reverse("emergencias:detalle", args=[emergencia.pk]))
        self.assertEqual(respuesta.context["transiciones_emergencia"], [])
        self.assertNotContains(respuesta, "Fase del incidente")

    def test_lo_que_cuesta_deshacer_pide_confirmacion(self):
        """Terminar y cancelar avisan; pasar a controlada no.

        Controlada es un paso intermedio del que se vuelve —el propio mapa de
        transiciones permite regresar a «en atención»—, así que pedir
        confirmación ahí sería un estorbo. Terminar y cancelar dejan huella en el
        expediente y de ellas solo se sale reactivando.
        """
        import re as _re

        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "FASE-CONF")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:detalle", args=[emergencia.pk]))
        html = respuesta.content.decode()
        # Cada formulario de fase lleva el estado en un campo oculto y su botón
        # detrás; se mira, formulario por formulario, si ese botón avisa.
        confirman = {}
        for bloque in _re.findall(
            r'<input type="hidden" name="estado".*?</form>', html, _re.S
        ):
            estado = _re.search(r'value="(\w+)"', bloque).group(1)
            confirman[estado] = "data-confirmar" in bloque
        self.assertEqual(
            confirman, {"controlada": False, "cerrada": True, "cancelada": True}
        )
