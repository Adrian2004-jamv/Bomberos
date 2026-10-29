"""El periodo operacional es del SCI-201 y de ningún otro formulario.

El Cuerpo de Bomberos de Latacunga pidió acotarlo: el resumen del incidente (SCI-201)
se vuelve a escribir en cada periodo operacional, y lo declarado en un periodo
cerrado no se reescribe. Todos los demás formularios (SCI-202, 211, 214…) vuelven a
guardarse una sola vez por emergencia. Y «Reactivar emergencia» desaparece: una
emergencia terminada ya no se reabre, y iniciar un periodo no habilita ningún otro
formulario.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion

from . import services
from .models import (Emergencia, FormularioSCI, FormularioSCI211,
                     PeriodoOperacional)
from .services import iniciar_periodo_operacional, periodo_actual


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

    def crear_formulario(self, emergencia, codigo="202", **extra):
        return FormularioSCI.objects.create(
            emergencia=emergencia, codigo_sci=codigo,
            datos=extra.pop("datos", {"objetivos": "Controlar el fuego"}),
            creado_por=self.usuario, modificado_por=self.usuario, **extra,
        )

    def entrar(self):
        self.client.force_login(self.usuario)

    def ruta(self, nombre, codigo, emergencia):
        return reverse(f"emergencias:{nombre}", args=[codigo, emergencia.pk])

    def guardar_201(self, emergencia, **campos):
        """Guarda el SCI-201 desde la pantalla, como lo hace quien lo llena."""
        datos = {"objetivos_iniciales": "Controlar el fuego", "preparado_por": "Capitán Vaca"}
        datos.update(campos)
        self.entrar()
        return self.client.post(self.ruta("sci_editar", "201", emergencia), datos)


class SoloElSCI201LlevaPeriodoTests(BaseDelPeriodo):
    """El modelo y la base lo imponen: no es una costumbre de las pantallas."""

    def test_un_formulario_que_no_es_el_201_no_lleva_periodo(self):
        emergencia = self.crear_emergencia()
        for codigo in ("202", "203", "214", "222"):
            with self.subTest(codigo=codigo):
                formulario = self.crear_formulario(emergencia, codigo)
                self.assertIsNone(formulario.periodo_id)
                self.assertIsNone(formulario.numero_periodo)
        # Y no crearlos no dejó periodos por el camino.
        self.assertEqual(emergencia.periodos.count(), 0)

    def test_aunque_se_le_ponga_uno_a_mano_se_guarda_sin_periodo(self):
        emergencia = self.crear_emergencia()
        periodo = periodo_actual(emergencia)
        formulario = self.crear_formulario(emergencia, "202", periodo=periodo)
        formulario.refresh_from_db()
        self.assertIsNone(formulario.periodo_id)

    def test_el_201_nace_con_el_periodo_uno(self):
        emergencia = self.crear_emergencia()
        self.assertEqual(emergencia.periodos.count(), 0)
        formulario = self.crear_formulario(emergencia, "201")
        self.assertEqual(formulario.numero_periodo, 1)
        self.assertEqual(emergencia.periodos.count(), 1)

    def test_pedir_el_periodo_vigente_dos_veces_no_crea_dos(self):
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

    def test_no_caben_dos_formularios_iguales_por_emergencia(self):
        """Dos NULL nunca chocan en SQL: por eso hay una restricción propia."""
        emergencia = self.crear_emergencia()
        self.crear_formulario(emergencia, "202")
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear_formulario(emergencia, "202")

    def test_no_caben_dos_201_en_el_mismo_periodo(self):
        emergencia = self.crear_emergencia()
        primero = self.crear_formulario(emergencia, "201")
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear_formulario(emergencia, "201", periodo=primero.periodo)

    def test_el_201_si_convive_en_dos_periodos(self):
        emergencia = self.crear_emergencia()
        self.crear_formulario(emergencia, "201")
        nuevo = iniciar_periodo_operacional(emergencia, self.usuario, "Relevo de turno")
        segundo = self.crear_formulario(emergencia, "201")
        self.assertEqual(segundo.periodo, nuevo)
        self.assertEqual(
            FormularioSCI.objects.filter(emergencia=emergencia, codigo_sci="201").count(), 2
        )

    def test_la_base_rechaza_un_periodo_en_un_formulario_que_no_es_el_201(self):
        """La garantía es de la base: ni un ``update`` directo la salta."""
        emergencia = self.crear_emergencia()
        periodo = periodo_actual(emergencia)
        formulario = self.crear_formulario(emergencia, "202")
        with self.assertRaises(IntegrityError), transaction.atomic():
            FormularioSCI.objects.filter(pk=formulario.pk).update(periodo=periodo)

    def test_la_base_rechaza_un_201_sin_periodo(self):
        emergencia = self.crear_emergencia()
        formulario = self.crear_formulario(emergencia, "201")
        with self.assertRaises(IntegrityError), transaction.atomic():
            FormularioSCI.objects.filter(pk=formulario.pk).update(periodo=None)

    def test_un_formulario_sin_periodo_se_edita_mientras_sea_borrador(self):
        emergencia = self.crear_emergencia()
        formulario = self.crear_formulario(emergencia, "202")
        self.assertTrue(formulario.es_editable)
        formulario.estado = FormularioSCI.Estado.FINALIZADO
        self.assertFalse(formulario.es_editable)

    def test_el_201_de_un_periodo_cerrado_deja_de_ser_editable(self):
        emergencia = self.crear_emergencia()
        primero = self.crear_formulario(emergencia, "201")
        self.assertTrue(primero.es_editable)
        iniciar_periodo_operacional(emergencia, self.usuario, "Relevo de turno")
        primero = FormularioSCI.objects.get(pk=primero.pk)
        self.assertEqual(primero.estado, FormularioSCI.Estado.BORRADOR)
        self.assertFalse(primero.es_editable)

    def test_el_sci211_es_uno_por_emergencia_y_ya_no_tiene_periodo(self):
        emergencia = self.crear_emergencia()
        campos = dict(
            emergencia=emergencia, punto_registro="Puesto de Comando",
            registrador_1="Capitán Vaca", creado_por=self.usuario,
            modificado_por=self.usuario,
        )
        FormularioSCI211.objects.create(codigo="SCI-211-UNO", **campos)
        with self.assertRaises(IntegrityError), transaction.atomic():
            FormularioSCI211.objects.create(codigo="SCI-211-DOS", **campos)
        self.assertFalse(hasattr(FormularioSCI211, "periodo"))
        self.assertEqual(emergencia.formulario_sci_211.codigo, "SCI-211-UNO")


class IniciarPeriodoTests(BaseDelPeriodo):
    def test_abre_el_periodo_siguiente_y_cierra_el_vigente(self):
        emergencia = self.crear_emergencia()
        self.crear_formulario(emergencia, "201")
        primero = periodo_actual(emergencia)
        nuevo = iniciar_periodo_operacional(emergencia, self.usuario, "Relevo de turno")
        primero.refresh_from_db()
        self.assertEqual(nuevo.numero, 2)
        self.assertTrue(nuevo.esta_abierto)
        self.assertEqual(nuevo.motivo, "Relevo de turno")
        self.assertEqual(nuevo.abierto_por, self.usuario)
        self.assertFalse(primero.esta_abierto)
        self.assertGreaterEqual(primero.fin, primero.inicio)

    def test_no_toca_la_emergencia_ni_los_demas_formularios(self):
        """Lo que antes hacía «reactivar»: ya no ocurre."""
        emergencia = self.crear_emergencia(Emergencia.Estado.CONTROLADA)
        self.crear_formulario(emergencia, "201")
        otro = self.crear_formulario(emergencia, "202")
        finalizado = self.crear_formulario(
            emergencia, "203", estado=FormularioSCI.Estado.FINALIZADO,
        )
        iniciar_periodo_operacional(emergencia, self.usuario, "Relevo de turno")
        emergencia.refresh_from_db()
        otro.refresh_from_db()
        finalizado.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.CONTROLADA)
        self.assertIsNone(emergencia.fecha_cierre)
        # Siguen siendo el mismo registro, con el mismo estado.
        self.assertTrue(otro.es_editable)
        self.assertFalse(finalizado.es_editable)
        self.assertEqual(
            FormularioSCI.objects.filter(emergencia=emergencia, codigo_sci="202").count(), 1
        )

    def test_hay_que_guardar_el_201_antes(self):
        emergencia = self.crear_emergencia()
        with self.assertRaises(ValidationError) as caso:
            iniciar_periodo_operacional(emergencia, self.usuario, "Relevo")
        self.assertIn("Guarde primero el SCI-201", " ".join(caso.exception.messages))
        self.assertEqual(emergencia.periodos.count(), 0)

    def test_el_motivo_es_obligatorio(self):
        emergencia = self.crear_emergencia()
        self.crear_formulario(emergencia, "201")
        for vacio in ("", "   ", None):
            with self.subTest(motivo=vacio):
                with self.assertRaises(ValidationError) as caso:
                    iniciar_periodo_operacional(emergencia, self.usuario, vacio)
                self.assertIn("por qué", " ".join(caso.exception.messages))
        self.assertEqual(emergencia.periodos.count(), 1)

    def test_una_emergencia_terminada_no_abre_periodos(self):
        for estado in (Emergencia.Estado.CERRADA, Emergencia.Estado.CANCELADA):
            with self.subTest(estado=estado):
                emergencia = self.crear_emergencia(estado, f"PER-{estado}")
                self.crear_formulario(emergencia, "201")
                with self.assertRaises(ValidationError) as caso:
                    iniciar_periodo_operacional(emergencia, self.usuario, "Rebrote")
                self.assertIn("ya terminó", " ".join(caso.exception.messages))
                self.assertEqual(emergencia.periodos.count(), 1)

    def test_el_tercer_periodo_exige_haber_guardado_el_segundo(self):
        emergencia = self.crear_emergencia()
        self.crear_formulario(emergencia, "201")
        iniciar_periodo_operacional(emergencia, self.usuario, "Primer relevo")
        # El 201 del periodo 2 todavía no se guardó: no hay sobre qué abrir el 3.
        with self.assertRaises(ValidationError):
            iniciar_periodo_operacional(emergencia, self.usuario, "Segundo relevo")
        self.crear_formulario(emergencia, "201")
        tercero = iniciar_periodo_operacional(emergencia, self.usuario, "Segundo relevo")
        self.assertEqual(tercero.numero, 3)
        self.assertEqual([p.numero for p in emergencia.periodos.order_by("numero")], [1, 2, 3])

    def test_quien_no_es_de_la_estacion_no_puede(self):
        otro_canton = Canton.objects.create(nombre="Otro", codigo="OTR-T")
        otro_cuerpo = CuerpoBomberos.objects.create(
            canton=otro_canton, nombre="Bomberos Otro", sigla="OTR-T",
            ruc="0599999999032", direccion="Otra dirección",
        )
        otra = Estacion.objects.create(
            cuerpo_bomberos=otro_cuerpo, nombre="Estación Otra", codigo="EP-OTR",
            direccion="Lejos", latitud="-0.940000", longitud="-78.620000",
        )
        ajeno = get_user_model().objects.create_user(
            username="mando.ajeno", password="clave-de-prueba",
            cedula="0500000399", estacion=otra,
        )
        ajeno.groups.add(Group.objects.get(name="Responsable de estación"))
        emergencia = self.crear_emergencia()
        self.crear_formulario(emergencia, "201")
        with self.assertRaises(ValidationError):
            iniciar_periodo_operacional(emergencia, ajeno, "Relevo")

    def test_reactivar_ya_no_existe(self):
        """El código que reabría emergencias y habilitaba todos los formularios se fue."""
        self.assertFalse(hasattr(services, "reactivar_emergencia"))
        with self.assertRaises(NoReverseMatch):
            reverse("emergencias:reactivar", args=[1])
        self.assertEqual(
            services.TRANSICIONES_EMERGENCIA[Emergencia.Estado.CERRADA], set(),
        )
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA)
        with self.assertRaises(ValidationError):
            services.cambiar_estado_emergencia(
                emergencia, Emergencia.Estado.EN_ATENCION, self.usuario
            )
        self.entrar()
        ficha = self.client.get(reverse("emergencias:detalle", args=[emergencia.pk]))
        self.assertNotContains(ficha, "Reactivar")
        self.assertNotContains(ficha, "Iniciar periodo operacional")
        self.assertNotContains(ficha, "dialogo-periodo")


class BotonDelPeriodoEnElSCI201Tests(BaseDelPeriodo):
    """El botón vive en el SCI-201 y aparece solo cuando corresponde."""

    def boton(self, html):
        return "Iniciar periodo operacional" in html

    def test_antes_de_guardar_el_201_no_hay_boton_ni_se_crea_nada(self):
        emergencia = self.crear_emergencia()
        self.entrar()
        html = self.client.get(self.ruta("sci_editar", "201", emergencia)).content.decode()
        self.assertFalse(self.boton(html))
        self.assertIn("periodo operacional 1", html)
        # Mirar el formulario no lo crea: el periodo 1 nace al guardar.
        self.assertEqual(emergencia.periodos.count(), 0)
        self.assertFalse(FormularioSCI.objects.filter(emergencia=emergencia).exists())

    def test_al_guardar_el_201_por_primera_vez_aparece_iniciar_el_periodo_2(self):
        emergencia = self.crear_emergencia()
        respuesta = self.guardar_201(emergencia)
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(emergencia.periodos.get().numero, 1)
        html = self.client.get(self.ruta("sci_editar", "201", emergencia)).content.decode()
        self.assertIn("Iniciar periodo operacional 2", html)
        self.assertNotIn("Iniciar periodo operacional 3", html)

    def test_el_boton_no_envia_nada_por_si_solo(self):
        import re as _re

        emergencia = self.crear_emergencia()
        self.guardar_201(emergencia)
        html = self.client.get(self.ruta("sci_editar", "201", emergencia)).content.decode()
        boton = _re.search(r"<button[^>]*data-abrir-periodo[^>]*>", html)
        self.assertIsNotNone(boton)
        self.assertIn('type="button"', boton.group(0))
        # El formulario que sí envía vive dentro del diálogo, no en el 201.
        antes, _, despues = html.partition('<dialog id="dialogo-periodo"')
        self.assertNotIn("/periodo/iniciar/", antes)
        self.assertIn("/periodo/iniciar/", despues)

    def test_el_dialogo_lleva_el_aviso_y_exige_el_motivo(self):
        import re as _re

        emergencia = self.crear_emergencia()
        self.guardar_201(emergencia)
        html = self.client.get(self.ruta("sci_editar", "201", emergencia)).content.decode()
        self.assertIn(
            "¿Está seguro de iniciar el Periodo Operacional 2? Se abrirán nuevos campos "
            "para la fecha actual, mientras que los registros del periodo anterior "
            "quedarán bloqueados y en solo lectura para su consulta e impresión.",
            html,
        )
        dialogo = _re.search(r'<dialog id="dialogo-periodo".*?</dialog>', html, _re.S).group(0)
        self.assertRegex(dialogo, r'<textarea[^>]*name="motivo"[^>]*required')
        confirmar = _re.search(r'<button type="submit"[^>]*data-enviar-periodo[^>]*>', dialogo)
        self.assertIn("disabled", confirmar.group(0))
        # El diálogo está fuera del formulario del 201: un formulario dentro de otro no vale.
        formulario_201 = _re.search(r'<form[^>]*id="sci201-form".*?</form>', html, _re.S).group(0)
        self.assertNotIn("dialogo-periodo", formulario_201)

    def test_iniciar_el_periodo_deja_el_1_bloqueado_y_abre_el_2_en_el_mismo_documento(self):
        emergencia = self.crear_emergencia()
        self.guardar_201(emergencia, objetivos_iniciales="Confinar el fuego")
        respuesta = self.client.post(
            reverse("emergencias:sci201_iniciar_periodo", args=[emergencia.pk]),
            {"motivo": "Relevo de turno de la mañana"},
        )
        self.assertRedirects(
            respuesta, self.ruta("sci_editar", "201", emergencia),
            fetch_redirect_response=False,
        )
        self.assertEqual(emergencia.periodos.count(), 2)
        html = self.client.get(self.ruta("sci_editar", "201", emergencia)).content.decode()
        # Lo del periodo 1, bloqueado y a la vista; debajo, el campo del 2.
        self.assertIn("Confinar el fuego", html)
        self.assertIn("P1 · cerrado", html)
        self.assertIn('name="objetivos_iniciales"', html)
        self.assertIn("Relevo de turno de la mañana", html)
        # El 3 no se ofrece hasta que se guarde el 2.
        self.assertFalse(self.boton(html))

    def test_guardar_el_periodo_2_no_reescribe_el_1(self):
        emergencia = self.crear_emergencia()
        self.guardar_201(emergencia, objetivos_iniciales="Confinar el fuego")
        iniciar_periodo_operacional(emergencia, self.usuario, "Relevo de turno")
        self.guardar_201(
            emergencia, objetivos_iniciales="Enfriar y vigilar", preparado_por="Teniente Chango",
        )
        primero = FormularioSCI.objects.get(
            emergencia=emergencia, codigo_sci="201", periodo__numero=1
        )
        segundo = FormularioSCI.objects.get(
            emergencia=emergencia, codigo_sci="201", periodo__numero=2
        )
        self.assertEqual(primero.datos["objetivos_iniciales"], "Confinar el fuego")
        self.assertEqual(primero.preparado_por, "Capitán Vaca")
        self.assertEqual(segundo.datos["objetivos_iniciales"], "Enfriar y vigilar")
        # Y con el 2 guardado ya se ofrece el 3.
        html = self.client.get(self.ruta("sci_editar", "201", emergencia)).content.decode()
        self.assertIn("Iniciar periodo operacional 3", html)

    def test_sin_motivo_el_servidor_no_abre_el_periodo(self):
        emergencia = self.crear_emergencia()
        self.guardar_201(emergencia)
        self.client.post(
            reverse("emergencias:sci201_iniciar_periodo", args=[emergencia.pk]),
            {"motivo": "   "},
        )
        self.assertEqual(emergencia.periodos.count(), 1)

    def test_con_el_201_finalizado_la_hoja_de_impresion_ofrece_el_boton(self):
        emergencia = self.crear_emergencia()
        self.guardar_201(emergencia)
        FormularioSCI.objects.filter(emergencia=emergencia, codigo_sci="201").update(
            estado=FormularioSCI.Estado.FINALIZADO
        )
        # El 201 finalizado no abre el editor: lleva a la hoja, y ahí está el botón.
        respuesta = self.client.get(self.ruta("sci_editar", "201", emergencia), follow=True)
        self.assertContains(respuesta, "Iniciar periodo operacional 2")
        self.assertContains(respuesta, 'id="dialogo-periodo"')

    def test_en_los_demas_formularios_no_hay_boton_ni_periodos(self):
        emergencia = self.crear_emergencia()
        self.guardar_201(emergencia)
        for codigo in ("202", "203", "204", "205", "206", "207", "214", "215", "221", "222"):
            for nombre in ("sci_editar", "sci_visualizar"):
                with self.subTest(codigo=codigo, vista=nombre):
                    html = self.client.get(self.ruta(nombre, codigo, emergencia)).content.decode()
                    self.assertFalse(self.boton(html))
                    self.assertNotIn("dialogo-periodo", html)
                    self.assertNotIn("Un solo documento", html)
                    self.assertNotIn("· cerrado", html)
                    self.assertNotIn("periodo operacional 1", html)

    def test_en_una_emergencia_terminada_no_se_ofrece(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA)
        self.crear_formulario(emergencia, "201")
        self.entrar()
        for nombre in ("sci_editar", "sci_visualizar"):
            html = self.client.get(
                self.ruta(nombre, "201", emergencia), follow=True
            ).content.decode()
            self.assertFalse(self.boton(html), nombre)
        self.client.post(
            reverse("emergencias:sci201_iniciar_periodo", args=[emergencia.pk]),
            {"motivo": "Rebrote"},
        )
        self.assertEqual(emergencia.periodos.count(), 1)

    def test_quien_solo_consulta_no_ve_el_boton_ni_puede_iniciar(self):
        emergencia = self.crear_emergencia()
        self.crear_formulario(emergencia, "201")
        lector = get_user_model().objects.create_user(
            username="lector.periodo", password="clave-de-prueba",
            cedula="0500000398", estacion=self.estacion,
        )
        lector.groups.add(Group.objects.get(name="Operador de consulta"))
        self.client.force_login(lector)
        html = self.client.get(self.ruta("sci_visualizar", "201", emergencia)).content.decode()
        self.assertFalse(self.boton(html))
        self.assertNotIn("dialogo-periodo", html)
        respuesta = self.client.post(
            reverse("emergencias:sci201_iniciar_periodo", args=[emergencia.pk]),
            {"motivo": "Relevo"},
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(emergencia.periodos.count(), 1)

    def test_la_ficha_ya_no_ofrece_iniciar_periodos(self):
        emergencia = self.crear_emergencia()
        self.guardar_201(emergencia)
        iniciar_periodo_operacional(emergencia, self.usuario, "Relevo de turno")
        html = self.client.get(reverse("emergencias:detalle", args=[emergencia.pk])).content.decode()
        self.assertNotIn("Iniciar periodo operacional", html)
        self.assertNotIn("Reactivar", html)
        # Pero sí cuenta cómo van los periodos del SCI-201.
        self.assertIn("Periodos operacionales del SCI-201", html)
        self.assertIn("Relevo de turno", html)

    def test_las_rutas_viejas_con_periodo_de_otros_formularios_llevan_a_la_hoja_unica(self):
        emergencia = self.crear_emergencia()
        self.entrar()
        for nombre in ("sci_editar_periodo", "sci_visualizar_periodo"):
            with self.subTest(vista=nombre):
                respuesta = self.client.get(
                    reverse(f"emergencias:{nombre}", args=["202", emergencia.pk, 1])
                )
                self.assertEqual(respuesta.status_code, 302)
                self.assertNotIn("/periodo/", respuesta["Location"])


class LosDemasFormulariosSeGuardanUnaVezTests(BaseDelPeriodo):
    """Sin periodos: un registro por emergencia y código, como siempre."""

    def test_guardar_dos_veces_actualiza_el_mismo_registro(self):
        emergencia = self.crear_emergencia()
        self.entrar()
        ruta = self.ruta("sci_editar", "202", emergencia)
        self.client.post(ruta, {"objetivos": "Controlar el fuego", "preparado_por": "Capitán Vaca"})
        self.client.post(ruta, {"objetivos": "Controlar y enfriar", "preparado_por": "Capitán Vaca"})
        registro = FormularioSCI.objects.get(emergencia=emergencia, codigo_sci="202")
        self.assertEqual(registro.datos["objetivos"], "Controlar y enfriar")
        self.assertIsNone(registro.periodo_id)

    def test_iniciar_un_periodo_del_201_no_bloquea_los_demas_formularios(self):
        emergencia = self.crear_emergencia()
        self.guardar_201(emergencia)
        self.client.post(
            self.ruta("sci_editar", "202", emergencia),
            {"objetivos": "Controlar el fuego", "preparado_por": "Capitán Vaca"},
        )
        iniciar_periodo_operacional(emergencia, self.usuario, "Relevo de turno")
        # El 202 sigue siendo el mismo registro y se sigue escribiendo en él.
        respuesta = self.client.post(
            self.ruta("sci_editar", "202", emergencia),
            {"objetivos": "Enfriar y vigilar", "preparado_por": "Capitán Vaca"},
        )
        self.assertEqual(respuesta.status_code, 302)
        registro = FormularioSCI.objects.get(emergencia=emergencia, codigo_sci="202")
        self.assertEqual(registro.datos["objetivos"], "Enfriar y vigilar")
        html = self.client.get(self.ruta("sci_editar", "202", emergencia)).content.decode()
        self.assertIn('id="sci-document-form"', html)
        self.assertNotIn("P1 · cerrado", html)

    def test_el_listado_cuenta_el_201_una_vez_aunque_tenga_dos_periodos(self):
        from .views import emergencias_permitidas

        emergencia = self.crear_emergencia()
        self.crear_formulario(emergencia, "201")
        self.crear_formulario(emergencia, "202")
        iniciar_periodo_operacional(emergencia, self.usuario, "Relevo de turno")
        self.crear_formulario(emergencia, "201")
        anotada = emergencias_permitidas(self.usuario).get(pk=emergencia.pk)
        self.assertEqual(anotada.formularios_registrados, 2)
        self.assertEqual(anotada.cantidad_formularios_genericos, 2)

    def test_el_estado_del_201_en_la_ficha_es_el_del_periodo_vigente(self):
        emergencia = self.crear_emergencia()
        self.crear_formulario(
            emergencia, "201", estado=FormularioSCI.Estado.FINALIZADO,
        )
        iniciar_periodo_operacional(emergencia, self.usuario, "Relevo de turno")
        self.entrar()
        ficha = self.client.get(reverse("emergencias:detalle", args=[emergencia.pk]))
        item = next(i for i in ficha.context["catalogo_sci"] if i["codigo"] == "201")
        # El periodo 1 está finalizado, pero el vigente es el 2 y no se ha escrito.
        self.assertEqual(item["clave_estado"], "pending")
        self.assertEqual(item["anteriores"], ["P1 finalizado"])
        otro = next(i for i in ficha.context["catalogo_sci"] if i["codigo"] == "202")
        self.assertEqual(otro["anteriores"], [])
        self.assertEqual(otro["periodos"], 0)


class HojaUnicaDelSCI201Tests(BaseDelPeriodo):
    """La hoja del SCI-201 con varios periodos dentro, como el formulario en Word.

    No es una pila de periodos completos con sus diecisiete puntos repetidos: en el
    Word, el punto 4 lleva el texto del P1 y debajo, dentro del mismo recuadro, el del P2.
    """

    DATOS_P1 = {
        "lugar_incidente": "Bodega de la avenida Unidad Nacional",
        "objetivos_iniciales": "Confinar el fuego en la bodega",
        "evaluacion_naturaleza": "Incendio estructural declarado",
        "acciones": [{"fecha_hora": "2026-10-27T08:00", "accion": "Primer ataque"}],
    }

    def incidente_con_dos_periodos(self):
        emergencia = self.crear_emergencia(codigo="PER-201")
        self.crear_formulario(
            emergencia, "201", datos=dict(self.DATOS_P1), preparado_por="Capitán Vaca",
        )
        nuevo = iniciar_periodo_operacional(emergencia, self.usuario, "Relevo nocturno")
        self.entrar()
        return emergencia, nuevo

    def test_cada_punto_lleva_el_periodo_cerrado_encima_de_su_campo(self):
        import re as _re

        emergencia, _ = self.incidente_con_dos_periodos()
        html = self.client.get(self.ruta("sci_editar", "201", emergencia)).content.decode()
        punto = _re.search(
            r'<label class="sci201-box">5\. Objetivo\(s\)(.*?)</label>', html, _re.S
        )
        self.assertIsNotNone(punto)
        self.assertIn("Confinar el fuego en la bodega", punto.group(1))
        self.assertIn('name="objetivos_iniciales"', punto.group(1))
        self.assertLess(
            punto.group(1).index("Confinar el fuego en la bodega"),
            punto.group(1).index('name="objetivos_iniciales"'),
            "lo cerrado va encima del campo que se escribe",
        )
        vacio = _re.search(r"7\. Tácticas:(.*?)</label>", html, _re.S)
        self.assertNotIn("cerrado", vacio.group(1))

    def test_la_bitacora_de_acciones_sigue_siendo_una_sola(self):
        emergencia, _ = self.incidente_con_dos_periodos()
        html = self.client.get(self.ruta("sci_editar", "201", emergencia)).content.decode()
        self.assertIn("Primer ataque", html)
        self.assertIn('name="acciones-0-accion"', html)
        self.assertLess(html.index("Primer ataque"), html.index('name="acciones-0-accion"'))

    def test_lo_cerrado_no_tiene_un_solo_control(self):
        import re as _re

        emergencia, _ = self.incidente_con_dos_periodos()
        html = self.client.get(self.ruta("sci_editar", "201", emergencia)).content.decode()
        bloques = _re.findall(r'<span class="sci201-previo">.*?</span></span>', html, _re.S)
        self.assertGreaterEqual(len(bloques), 2)
        for bloque in bloques:
            for prohibido in ("<input", "<textarea", "<select", "name="):
                self.assertNotIn(prohibido, bloque)

    def test_la_hoja_de_impresion_reune_los_periodos_sin_repetir_el_formulario(self):
        emergencia, nuevo = self.incidente_con_dos_periodos()
        self.crear_formulario(
            emergencia, "201", datos={"objetivos_iniciales": "Enfriar y vigilar el rescoldo"},
        )
        html = self.client.get(self.ruta("sci_visualizar", "201", emergencia)).content.decode()
        self.assertEqual(html.count('class="sci201-page"'), 4)
        self.assertLess(html.index("Confinar el fuego en la bodega"),
                        html.index("Enfriar y vigilar el rescoldo"))
        self.assertIn("P1", html)
        self.assertIn("en curso", html)

    def test_con_un_solo_periodo_la_hoja_sale_como_el_formulario_oficial(self):
        emergencia = self.crear_emergencia(codigo="PER-UNO")
        self.crear_formulario(
            emergencia, "201", datos={"objetivos_iniciales": "Controlar el fuego"},
        )
        self.entrar()
        for nombre in ("sci_editar", "sci_visualizar"):
            with self.subTest(vista=nombre):
                html = self.client.get(self.ruta(nombre, "201", emergencia)).content.decode()
                self.assertIn("Controlar el fuego", html)
                self.assertNotIn("P1 ·", html)
                self.assertNotIn("sci201-previo", html)
                self.assertNotIn("Un solo documento", html)

    def test_un_periodo_cerrado_se_imprime_por_separado(self):
        emergencia, nuevo = self.incidente_con_dos_periodos()
        self.crear_formulario(emergencia, "201", datos={"objetivos_iniciales": "Del dos"})
        respuesta = self.client.get(
            reverse("emergencias:sci_visualizar_periodo", args=["201", emergencia.pk, 1])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Documento del periodo operacional 1")
        # Editar un periodo cerrado lleva al documento continuo, no a otra pantalla.
        editar = self.client.get(
            reverse("emergencias:sci_editar_periodo", args=["201", emergencia.pk, 1])
        )
        self.assertEqual(editar.status_code, 302)
        self.assertIn("#periodo-1", editar["Location"])

    def test_un_periodo_que_no_existe_es_404(self):
        emergencia = self.crear_emergencia()
        self.crear_formulario(emergencia, "201")
        self.entrar()
        respuesta = self.client.get(
            reverse("emergencias:sci_visualizar_periodo", args=["201", emergencia.pk, 9])
        )
        self.assertEqual(respuesta.status_code, 404)


class TerminarLaEmergenciaDesdeLaFichaTests(BaseDelPeriodo):
    """Terminar un incidente tiene su botón en la ficha, y de CERRADA no se vuelve."""

    def test_la_ficha_ofrece_las_fases_a_las_que_puede_pasar(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "FASE-CURSO")
        self.entrar()
        respuesta = self.client.get(reverse("emergencias:detalle", args=[emergencia.pk]))
        self.assertContains(respuesta, "Fase del incidente")
        ofrecidas = {t["valor"] for t in respuesta.context["transiciones_emergencia"]}
        # La cancelación no es una fase: tiene su propio flujo con el motivo.
        self.assertEqual(
            ofrecidas, {Emergencia.Estado.CONTROLADA, Emergencia.Estado.CERRADA},
        )
        self.assertTrue(respuesta.context["puede_cancelar"])
        self.assertContains(
            respuesta, reverse("emergencias:cambiar_estado", args=[emergencia.pk])
        )

    def test_terminar_la_emergencia_desde_la_ficha(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "FASE-CIERRA")
        self.entrar()
        respuesta = self.client.post(
            reverse("emergencias:cambiar_estado", args=[emergencia.pk]),
            {"estado": Emergencia.Estado.CERRADA}, follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        emergencia.refresh_from_db()
        self.assertEqual(emergencia.estado, Emergencia.Estado.CERRADA)
        self.assertIsNotNone(emergencia.fecha_cierre)

    def test_cerrada_ya_no_ofrece_fases_y_no_se_reabre(self):
        emergencia = self.crear_emergencia(Emergencia.Estado.CERRADA, "FASE-FIN")
        self.entrar()
        respuesta = self.client.get(reverse("emergencias:detalle", args=[emergencia.pk]))
        self.assertEqual(respuesta.context["transiciones_emergencia"], [])
        self.assertNotContains(respuesta, "Fase del incidente")
        self.assertNotContains(respuesta, "Iniciar periodo operacional")

    def test_terminar_permite_cerrar_la_bitacora_que_esperaba(self):
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

        self.entrar()
        self.client.post(
            reverse("emergencias:cambiar_estado", args=[emergencia.pk]),
            {"estado": Emergencia.Estado.CERRADA},
        )
        bitacora.refresh_from_db()
        cerrada = finalizar_sci(bitacora, self.usuario)
        self.assertEqual(cerrada.estado, FormularioSCI.Estado.FINALIZADO)

    def test_quien_solo_consulta_no_ve_las_fases(self):
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
        import re as _re

        emergencia = self.crear_emergencia(Emergencia.Estado.EN_ATENCION, "FASE-CONF")
        self.entrar()
        html = self.client.get(
            reverse("emergencias:detalle", args=[emergencia.pk])
        ).content.decode()
        confirman = {}
        for bloque in _re.findall(
            r'<input type="hidden" name="estado".*?</form>', html, _re.S
        ):
            estado = _re.search(r'value="(\w+)"', bloque).group(1)
            confirman[estado] = "data-confirmar" in bloque
        self.assertEqual(confirman, {"controlada": False, "cerrada": True})


class RespaldoDeLaUnificacionTests(BaseDelPeriodo):
    """Lo de los periodos anteriores, que la migración 0021 dejó dentro del registro."""

    RESPALDO = [{
        "periodo": 1, "estado": "finalizado", "preparado_por": "Capitán Vaca",
        "datos": {"objetivos": "Plan del periodo uno"},
    }]

    def test_guardar_el_formulario_no_pierde_el_respaldo(self):
        from .esquemas_sci import RESPALDO_DE_PERIODOS

        emergencia = self.crear_emergencia()
        self.crear_formulario(
            emergencia, "202",
            datos={"objetivos": "Plan del periodo dos", RESPALDO_DE_PERIODOS: self.RESPALDO},
        )
        self.entrar()
        self.client.post(
            self.ruta("sci_editar", "202", emergencia),
            {"objetivos": "Plan corregido", "preparado_por": "Capitán Vaca"},
        )
        registro = FormularioSCI.objects.get(emergencia=emergencia, codigo_sci="202")
        self.assertEqual(registro.datos["objetivos"], "Plan corregido")
        self.assertEqual(registro.datos[RESPALDO_DE_PERIODOS], self.RESPALDO)

    def test_el_respaldo_no_cuenta_como_contenido_ni_se_muestra(self):
        from .esquemas_sci import RESPALDO_DE_PERIODOS
        from .services_sci import tiene_contenido

        self.assertFalse(tiene_contenido({RESPALDO_DE_PERIODOS: self.RESPALDO}))
        emergencia = self.crear_emergencia()
        self.crear_formulario(
            emergencia, "202", datos={RESPALDO_DE_PERIODOS: self.RESPALDO},
        )
        self.entrar()
        html = self.client.get(self.ruta("sci_editar", "202", emergencia)).content.decode()
        self.assertNotIn("Plan del periodo uno", html)
        self.assertNotIn(RESPALDO_DE_PERIODOS, html)
