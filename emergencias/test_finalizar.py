"""Finalizar un formulario: guardar y bloquear en una sola petición, con aviso previo.

Quien llenaba un formulario por primera vez y pulsaba «Finalizar» recibía
«formulario incompleto» y perdía lo escrito: el botón era otro formulario que solo
mandaba el token, de modo que finalizaba lo que hubiera en la base y descartaba lo
que seguía en pantalla. Había que guardar, salir, volver a entrar y recién entonces
finalizar. Ahora es un solo envío —se guarda y, solo si se guardó, se finaliza— y
antes de enviarlo el navegador pide confirmación, porque finalizar no se deshace.
"""

import re
from pathlib import Path

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .models import Emergencia, FormularioSCI
from .test_validacion_sci import BaseValidacion

AVISO = ("¿Está seguro de finalizar el formulario? Al finalizar, el documento quedará "
         "bloqueado en modo solo lectura y no se podrá volver a editar.")

SCI_201_COMPLETO = {
    "lugar_incidente": "Av. Amazonas y Quito",
    "evaluacion_naturaleza": "Incendio en planta baja.",
    "evaluacion_amenazas": "Humo denso.",
    "evaluacion_areas_afectadas": "Planta baja.",
    "evaluacion_aislamiento": "Calle cerrada.",
    "objetivos_iniciales": "Confinar el fuego.",
    "preparado_por": "Mayor Andrade",
}


class GuardarYFinalizarTests(BaseValidacion):
    def editar(self, codigo, emergencia):
        return reverse("emergencias:sci_editar", args=[codigo, emergencia.pk])

    def enviar(self, codigo, emergencia, datos, accion=None):
        self.client.force_login(self.usuario)
        cuerpo = dict(datos)
        if accion:
            cuerpo["accion"] = accion
        return self.client.post(self.editar(codigo, emergencia), cuerpo)

    def formulario(self, emergencia, codigo="201"):
        return FormularioSCI.objects.get(emergencia=emergencia, codigo_sci=codigo)

    # -- el caso que fallaba -------------------------------------------------------

    def test_un_solo_envio_guarda_y_finaliza(self):
        """Primera vez, directo a «Finalizar»: nada guardado antes."""
        emergencia = self.crear_emergencia("FIN-UNO")
        self.assertFalse(FormularioSCI.objects.filter(emergencia=emergencia).exists())

        respuesta = self.enviar("201", emergencia, SCI_201_COMPLETO, accion="finalizar")

        self.assertEqual(respuesta.status_code, 302)
        formulario = self.formulario(emergencia)
        self.assertEqual(formulario.estado, FormularioSCI.Estado.FINALIZADO)
        self.assertEqual(formulario.finalizado_por, self.usuario)
        # Lo escrito está ahí: es lo que antes se perdía.
        self.assertEqual(formulario.datos["evaluacion_naturaleza"], "Incendio en planta baja.")
        self.assertEqual(formulario.datos["objetivos_iniciales"], "Confinar el fuego.")
        self.assertEqual(formulario.preparado_por, "Mayor Andrade")
        self.assertFalse(formulario.es_editable)

    def test_el_mensaje_dice_que_se_guardo_y_se_finalizo(self):
        emergencia = self.crear_emergencia("FIN-MSG")
        respuesta = self.enviar("201", emergencia, SCI_201_COMPLETO, accion="finalizar")
        pagina = self.client.get(respuesta["Location"])
        self.assertContains(pagina, "guardado y finalizado")

    def test_si_el_cierre_se_rechaza_lo_escrito_queda_guardado(self):
        """Falta la firma: no se puede finalizar, pero lo escrito no se pierde."""
        emergencia = self.crear_emergencia("FIN-RECHAZO")
        datos = {k: v for k, v in SCI_201_COMPLETO.items() if k != "preparado_por"}
        respuesta = self.enviar("201", emergencia, datos, accion="finalizar")

        formulario = self.formulario(emergencia)
        self.assertEqual(formulario.estado, FormularioSCI.Estado.BORRADOR)
        self.assertEqual(formulario.datos["evaluacion_amenazas"], "Humo denso.")
        # Y vuelve al editor, donde lo escrito sigue y se explica qué falta.
        # Sin descargar la página aún: leerla aquí consumiría el mensaje.
        self.assertRedirects(
            respuesta, self.editar("201", emergencia), fetch_redirect_response=False
        )
        pagina = self.client.get(self.editar("201", emergencia))
        self.assertContains(pagina, "Sus cambios se guardaron")
        self.assertContains(pagina, "Preparado por")
        self.assertContains(pagina, "Humo denso.")

    def test_una_bitacora_que_espera_se_guarda_pero_no_se_cierra(self):
        """SCI-214 con la emergencia en curso: se guarda y se explica por qué no cierra."""
        emergencia = self.crear_emergencia("FIN-BITACORA")
        respuesta = self.enviar("214", emergencia, {
            "actividades-0-hora": "10:15",
            "actividades-0-evento": "Arribo de la primera unidad",
            "preparado_por": "Cap. Vaca",
        }, accion="finalizar")

        formulario = self.formulario(emergencia, "214")
        self.assertEqual(formulario.estado, FormularioSCI.Estado.BORRADOR)
        self.assertEqual(formulario.datos["actividades"][0]["evento"], "Arribo de la primera unidad")
        pagina = self.client.get(respuesta["Location"])
        self.assertContains(pagina, "Sus cambios se guardaron")
        self.assertContains(pagina, "se cierra cuando la emergencia")

    def test_guardar_sin_finalizar_sigue_siendo_guardar(self):
        emergencia = self.crear_emergencia("FIN-GUARDAR")
        self.enviar("201", emergencia, SCI_201_COMPLETO)
        self.assertEqual(self.formulario(emergencia).estado, FormularioSCI.Estado.BORRADOR)

    # -- lo que no debe perderse ---------------------------------------------------

    def test_un_error_de_validacion_devuelve_lo_escrito(self):
        """Antes la pantalla volvía con la versión vieja de la base.

        Una fecha anterior a la apertura del expediente se rechaza; lo que el
        usuario había escrito en los demás campos tiene que seguir ahí para que
        corrija solo la fecha.
        """
        emergencia = self.crear_emergencia("FIN-ECO")
        respuesta = self.enviar("201", emergencia, {
            **SCI_201_COMPLETO,
            "acciones-0-fecha_hora": "2000-01-01T00:00",
            "acciones-0-accion": "Acción con fecha imposible",
        }, accion="finalizar")

        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        self.assertIn("Acción con fecha imposible", html)
        self.assertIn("Incendio en planta baja.", html)
        # Y no se guardó ni se finalizó nada: el envío entero se rechazó.
        formulario = FormularioSCI.objects.filter(emergencia=emergencia, codigo_sci="201").first()
        if formulario is not None:
            self.assertEqual(formulario.estado, FormularioSCI.Estado.BORRADOR)
            self.assertNotIn("evaluacion_naturaleza", formulario.datos)

    def test_reenviar_una_finalizacion_no_pisa_ni_falla(self):
        """La cola del teléfono puede entregar dos veces lo mismo.

        Con señal débil una petición puede llegar al servidor y no volver; el
        reintento no debe dar un error ni reescribir un documento ya cerrado.
        """
        emergencia = self.crear_emergencia("FIN-DOBLE")
        self.enviar("201", emergencia, SCI_201_COMPLETO, accion="finalizar")
        respuesta = self.enviar(
            "201", emergencia, {**SCI_201_COMPLETO, "lugar_incidente": "OTRO LUGAR"},
            accion="finalizar",
        )
        self.assertEqual(respuesta.status_code, 302)
        formulario = self.formulario(emergencia)
        self.assertEqual(formulario.estado, FormularioSCI.Estado.FINALIZADO)
        self.assertEqual(formulario.datos["lugar_incidente"], "Av. Amazonas y Quito")


class AvisoAntesDeFinalizarTests(BaseValidacion):
    """Los botones de finalizar viven en el formulario que se edita y piden confirmación."""

    def html_del_editor(self, codigo, emergencia):
        self.client.force_login(self.usuario)
        return self.client.get(
            reverse("emergencias:sci_editar", args=[codigo, emergencia.pk])
        ).content.decode()

    def comprobar(self, html):
        # El botón está dentro del formulario que se edita...
        formulario = html[html.index("<form method=\"post\" id=\"sci"):]
        formulario = formulario[:formulario.index("</form>")]
        boton = re.search(r'<button[^>]*value="finalizar"[^>]*>', formulario)
        self.assertIsNotNone(boton, "El botón de finalizar debe estar dentro del formulario.")
        # ...con el aviso, y ya no hay otro formulario que finalice por su cuenta.
        self.assertIn(AVISO, boton.group(0))
        self.assertIn("Confirmar y Finalizar", boton.group(0))
        self.assertEqual(len(re.findall(r'<form[^>]*action="[^"]*/finalizar/"', html)), 0)

    def test_el_editor_generico_lo_tiene(self):
        self.comprobar(self.html_del_editor("214", self.crear_emergencia("AV-GEN")))

    def test_el_editor_del_201_lo_tiene(self):
        self.comprobar(self.html_del_editor("201", self.crear_emergencia("AV-201")))

    def test_ningun_boton_de_finalizar_carece_de_aviso(self):
        """Auditoría: cualquier botón «finalizar» de cualquier plantilla pide confirmación."""
        raiz = Path(settings.BASE_DIR) / "templates"
        sin_aviso = []
        for plantilla in raiz.rglob("*.html"):
            fuente = plantilla.read_text(encoding="utf-8")
            for boton in re.findall(r'<button[^>]*value="finalizar"[^>]*>', fuente):
                if "data-confirmar=" not in boton:
                    sin_aviso.append(plantilla.relative_to(raiz).as_posix())
        self.assertEqual(sin_aviso, [], f"Botones de finalizar sin aviso: {sin_aviso}")


class DialogoDeConfirmacionTests(BaseValidacion):
    """El aviso se muestra ANTES de que salga el envío, también con guardado sin conexión.

    sin-conexion.js escucha el envío en el propio formulario y lanza el «fetch» al
    instante: un oyente normal en el documento llegaba cuando el envío ya había
    salido y el aviso no frenaba nada. Estas comprobaciones leen el código porque el
    proyecto no tiene un motor de JavaScript en las pruebas; el comportamiento se
    verificó en el navegador.
    """

    def fuente(self, *partes):
        return (Path(settings.BASE_DIR).joinpath(*partes)).read_text(encoding="utf-8")

    def test_el_oyente_va_en_la_fase_de_captura_y_detiene_el_evento(self):
        js = self.fuente("static", "js", "app.js")
        self.assertIn("stopImmediatePropagation", js)
        # El tercer argumento «true» de addEventListener es la captura.
        self.assertRegex(js, r'addEventListener\("submit",[\s\S]*?\},\s*true\);')

    def test_el_dialogo_se_pide_con_texto_y_se_cancela_sin_enviar(self):
        js = self.fuente("static", "js", "app.js")
        self.assertIn("showModal", js)
        self.assertIn("data-dialogo-cancelar", js)
        self.assertIn("dialogo-confirmar__spinner", js)

    def test_la_finalizacion_en_cola_bloquea_el_formulario_y_avisa_al_dialogo(self):
        js = self.fuente("static", "pwa", "js", "sin-conexion.js")
        self.assertIn('pulsado.value === "finalizar"', js)
        self.assertIn("bomberos:envio-en-cola", js)
        self.assertIn("campo.disabled = true", js)
        self.assertIn("bomberos:envio-en-cola", self.fuente("static", "js", "app.js"))

    def test_las_paginas_cargan_la_version_nueva_de_los_guiones(self):
        """Sin subir el número, el navegador sigue con el guion anterior."""
        base = self.fuente("templates", "base.html")
        self.assertIn("js/app.js' %}?v=5", base)
        self.assertIn("pwa/js/sin-conexion.js' %}?v=2", base)
        self.assertIn("css/componentes.css' %}?v=13", base)
