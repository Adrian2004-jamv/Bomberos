"""Completitud de los formularios, coherencia de fechas y fuente única de verdad.

Las tres cosas que pidió el Cuerpo de Bomberos de Latacunga sobre el llenado:
que no falte ningún campo del formulario oficial, que ninguna fecha sea anterior
a la apertura del expediente, y que lo ya declarado no se vuelva a teclear.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion

from .esquemas_sci import ESQUEMAS_SCI, FECHA_HORA, NUMERO, TABLA
from .models import Emergencia, FormularioSCI
from .services_sci import (campos_obligatorios_vacios, estado_del_incidente,
                           fecha_de_referencia, fechas_anteriores_al_inicio,
                           finalizar_sci, prepoblar)


class BaseValidacion(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Validación", codigo="VAL-T")
        cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Validación", sigla="VAL-T",
            ruc="0599999999041", direccion="Dirección institucional",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo, nombre="Estación Validación", codigo="EV-VAL",
            direccion="Centro", latitud="-0.930000", longitud="-78.610000",
        )
        cls.usuario = get_user_model().objects.create_user(
            username="mando.validacion", password="clave-de-prueba",
            cedula="0500000401", estacion=cls.estacion,
        )
        cls.usuario.groups.add(Group.objects.get(name="Responsable de estación"))

    def crear_emergencia(self, codigo="VAL-001"):
        return Emergencia.objects.create(
            codigo=codigo, tipo_emergencia="Incendio estructural",
            fecha_reporte=timezone.now(), direccion="Av. Amazonas y Quito",
            estado=Emergencia.Estado.EN_ATENCION,
            estacion_responsable=self.estacion, registrado_por=self.usuario,
        )

    def crear_formulario(self, emergencia, codigo, datos=None, **extra):
        return FormularioSCI.objects.create(
            emergencia=emergencia, codigo_sci=codigo, datos=datos or {},
            creado_por=self.usuario, modificado_por=self.usuario, **extra,
        )


# ──────────────────────────────────────────────────────────────────────
# 1. Completitud frente al formulario oficial
# ──────────────────────────────────────────────────────────────────────

class EstructuraOficialTests(TestCase):
    """Los campos que faltaban frente a los .docx/.xlsx oficiales."""

    def test_el_204_tiene_las_seis_columnas_del_oficial(self):
        """La tabla 7 del SCI-204 oficial tiene seis columnas, no cuatro.

        Faltaban «Asignación táctica», «Ubicación» y «N.º de personas a cargo»,
        que es con lo que un Jefe de Operaciones sabe a quién mandó, a qué y
        con cuánta gente.
        """
        tabla = next(s for s in ESQUEMAS_SCI["204"]["secciones"] if s["nombre"] == "recursos")
        nombres = [c["nombre"] for c in tabla["columnas"]]
        for obligatoria in ("asignacion_tactica", "ubicacion", "personas_a_cargo"):
            self.assertIn(obligatoria, nombres)
        personas = next(c for c in tabla["columnas"] if c["nombre"] == "personas_a_cargo")
        self.assertEqual(personas["tipo"], NUMERO, "Contar personas es un número.")

    def test_el_204_declara_quien_lo_aprueba(self):
        self.assertIn("aprobado_por", ESQUEMAS_SCI["204"])

    def test_el_206_separa_la_unidad_medica_de_las_instalaciones(self):
        """Los campos 6 y 7 son de la Unidad Médica, no columnas de la tabla A.

        Estaban metidos dentro de la tabla que enumera las instalaciones de la
        periferia; al mezclarlos se perdió el campo 8 y la numeración del
        formulario quedó corrida respecto del oficial.
        """
        esquema = ESQUEMAS_SCI["206"]
        nombres = [s["nombre"] for s in esquema["secciones"]]
        self.assertIn("instalacion_um", nombres)
        self.assertIn("ubicacion_um", nombres)
        tabla = next(s for s in esquema["secciones"] if s["nombre"] == "asistencia")
        self.assertEqual(tabla["numero"], 8)
        etiquetas = [c["etiqueta"] for c in tabla["columnas"]]
        self.assertIn("8. Nombre de la institución", etiquetas)

    def test_cada_aprobador_declarado_se_puede_guardar(self):
        """Declarar quién aprueba sin dónde escribirlo imprimía el cargo.

        La hoja salía con «APROBADO POR: Comandante del Incidente (CI)» en el
        sitio donde debía ir el nombre de la persona.
        """
        campos = {f.name for f in FormularioSCI._meta.get_fields()}
        self.assertIn("aprobado_por", campos)
        self.assertIn("posicion_preparado_por", campos)
        con_aprobador = [c for c, e in ESQUEMAS_SCI.items() if e.get("aprobado_por")]
        self.assertTrue(con_aprobador, "Algún formulario debe declarar aprobador.")


class ObligatoriosTests(BaseValidacion):
    def test_no_se_finaliza_sin_los_campos_que_el_oficial_exige(self):
        emergencia = self.crear_emergencia()
        formulario = self.crear_formulario(
            emergencia, "201", {"estrategias": "Ataque indirecto"},
            preparado_por="Mayor Andrade",
        )
        with self.assertRaises(ValidationError) as caso:
            finalizar_sci(formulario, self.usuario)
        mensaje = " ".join(caso.exception.messages)
        self.assertIn("no admite estos campos en blanco", mensaje)
        self.assertIn("Evaluación inicial", mensaje)

    def test_con_los_obligatorios_llenos_se_finaliza(self):
        emergencia = self.crear_emergencia("VAL-OK")
        formulario = self.crear_formulario(emergencia, "201", {
            "lugar_incidente": "Av. Amazonas y Quito",
            "evaluacion_naturaleza": "Incendio en planta baja.",
            "evaluacion_amenazas": "Humo denso, riesgo de colapso de cubierta.",
            "evaluacion_areas_afectadas": "Planta baja y entrepiso.",
            "evaluacion_aislamiento": "Sin heridos. Calle cerrada al tránsito.",
            "objetivos_iniciales": "Confinar el fuego y proteger expuestos.",
        }, preparado_por="Mayor Andrade")
        finalizar_sci(formulario, self.usuario)
        formulario.refresh_from_db()
        self.assertEqual(formulario.estado, FormularioSCI.Estado.FINALIZADO)

    def test_un_documento_sin_firma_no_es_un_documento(self):
        emergencia = self.crear_emergencia("VAL-FIRMA")
        formulario = self.crear_formulario(emergencia, "201", {
            "lugar_incidente": "Av. Amazonas",
            "evaluacion_inicial": "Incendio controlado.",
            "objetivos_iniciales": "Enfriar la estructura.",
        })
        faltan = campos_obligatorios_vacios(formulario)
        self.assertTrue(any("Preparado por" in f for f in faltan), faltan)

    def test_el_202_exige_tambien_la_aprobacion_del_ci(self):
        emergencia = self.crear_emergencia("VAL-202")
        formulario = self.crear_formulario(
            emergencia, "202", {"objetivos": "Confinar el fuego"},
            preparado_por="Jefe de Planificación",
        )
        faltan = campos_obligatorios_vacios(formulario)
        self.assertTrue(any("Aprobado por" in f for f in faltan), faltan)
        formulario.aprobado_por = "Mayor Andrade"
        formulario.save(update_fields=["aprobado_por"])
        self.assertEqual(campos_obligatorios_vacios(formulario), [])

    def test_guardar_a_medias_sigue_permitido(self):
        """En plena intervención se anota lo que se sabe y se vuelve al rato."""
        emergencia = self.crear_emergencia("VAL-MEDIAS")
        self.client.force_login(self.usuario)
        respuesta = self.client.post(
            reverse("emergencias:sci_editar", args=["201", emergencia.pk]),
            {"evaluacion_amenazas": "Humo denso en el segundo piso."},
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "guardado correctamente")


# ──────────────────────────────────────────────────────────────────────
# 2. Coherencia de las fechas
# ──────────────────────────────────────────────────────────────────────

class FechasTests(BaseValidacion):
    def test_la_referencia_es_la_creacion_del_201(self):
        emergencia = self.crear_emergencia("VAL-REF")
        del_201 = self.crear_formulario(emergencia, "201", {"evaluacion_inicial": "x"})
        # Al minuto: es la precisión con la que los controles del formulario
        # guardan las fechas, y la misma que anuncia el «min» del editor.
        self.assertEqual(
            fecha_de_referencia(emergencia),
            del_201.fecha_creacion.replace(second=0, microsecond=0),
        )

    def test_sin_201_la_referencia_es_el_reporte(self):
        """Si no, la regla no regiría hasta que alguien creara el 201.

        Que es justo cuando más falta hace: al principio es cuando se teclean
        las horas a mano y con prisa.
        """
        emergencia = self.crear_emergencia("VAL-SIN201")
        self.assertEqual(
            fecha_de_referencia(emergencia),
            emergencia.fecha_reporte.replace(second=0, microsecond=0),
        )

    def test_una_fecha_anterior_se_detecta(self):
        emergencia = self.crear_emergencia("VAL-ANTES")
        referencia = fecha_de_referencia(emergencia)
        # Se localiza igual que lo hace el editor: el control del navegador
        # trabaja en hora local y «_momento» la interpreta así.
        antes = timezone.localtime(
            referencia - timezone.timedelta(hours=3)
        ).strftime("%Y-%m-%dT%H:%M")
        malas = fechas_anteriores_al_inicio(
            ESQUEMAS_SCI["202"], {"periodo_inicio": antes}, referencia,
        )
        self.assertEqual(len(malas), 1)
        self.assertIn("inicio del periodo", malas[0])

    def test_una_fecha_posterior_pasa(self):
        emergencia = self.crear_emergencia("VAL-DESPUES")
        referencia = fecha_de_referencia(emergencia)
        despues = timezone.localtime(
            referencia + timezone.timedelta(hours=2)
        ).strftime("%Y-%m-%dT%H:%M")
        self.assertEqual(
            fechas_anteriores_al_inicio(
                ESQUEMAS_SCI["202"], {"periodo_inicio": despues}, referencia,
            ),
            [],
        )

    def test_tambien_se_revisan_las_fechas_dentro_de_las_tablas(self):
        """El SCI-201 anota la hora de cada acción en una tabla, no en un campo."""
        emergencia = self.crear_emergencia("VAL-TABLA")
        referencia = fecha_de_referencia(emergencia)
        antes = timezone.localtime(
            referencia - timezone.timedelta(days=1)
        ).strftime("%Y-%m-%dT%H:%M")
        malas = fechas_anteriores_al_inicio(
            ESQUEMAS_SCI["201"],
            {"acciones": [{"fecha_hora": antes, "accion": "Arribo"}]},
            referencia,
        )
        self.assertEqual(len(malas), 1)
        self.assertIn("fila 1", malas[0])

    def test_un_valor_viejo_sin_formato_no_se_juzga(self):
        """Quien lo escribió ya no está para corregirlo; perderlo sería peor."""
        emergencia = self.crear_emergencia("VAL-VIEJO")
        referencia = fecha_de_referencia(emergencia)
        self.assertEqual(
            fechas_anteriores_al_inicio(
                ESQUEMAS_SCI["202"], {"periodo_inicio": "ayer por la tarde"}, referencia,
            ),
            [],
        )

    def test_el_servidor_rechaza_el_guardado_con_una_fecha_anterior(self):
        emergencia = self.crear_emergencia("VAL-POST")
        self.crear_formulario(emergencia, "201", {"evaluacion_inicial": "x"})
        antes = timezone.localtime(
            fecha_de_referencia(emergencia) - timezone.timedelta(days=2)
        ).strftime("%Y-%m-%dT%H:%M")
        self.client.force_login(self.usuario)
        respuesta = self.client.post(
            reverse("emergencias:sci_editar", args=["202", emergencia.pk]),
            {"objetivos": "Confinar", "periodo_inicio": antes},
            follow=True,
        )
        self.assertContains(respuesta, "anteriores a la apertura del expediente")
        guardado = FormularioSCI.objects.get(emergencia=emergencia, codigo_sci="202")
        self.assertNotEqual(guardado.datos.get("periodo_inicio"), antes)

    def test_el_editor_pone_la_cota_en_cada_control_de_fecha(self):
        """El navegador no deja escribir lo que el servidor rechazaría."""
        emergencia = self.crear_emergencia("VAL-MIN")
        self.crear_formulario(emergencia, "201", {"evaluacion_inicial": "x"})
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci_editar", args=["202", emergencia.pk])
        )
        minimo = timezone.localtime(
            fecha_de_referencia(emergencia)
        ).strftime("%Y-%m-%dT%H:%M")
        self.assertContains(respuesta, f'min="{minimo}"')


# ──────────────────────────────────────────────────────────────────────
# 4. Fuente única de verdad
# ──────────────────────────────────────────────────────────────────────

class FuenteUnicaTests(BaseValidacion):
    def test_el_estado_recoge_lo_que_el_incidente_ya_declaro(self):
        emergencia = self.crear_emergencia("VAL-SSOT")
        self.crear_formulario(emergencia, "201", {
            "lugar_incidente": "Bodega de la Panamericana Sur",
            "ubicacion_pc": "Esquina norte, junto al portón",
        }, preparado_por="Mayor Luis Andrade")
        estado = estado_del_incidente(emergencia)
        self.assertEqual(estado["comandante_incidente"], "Mayor Luis Andrade")
        self.assertEqual(estado["lugar_incidente"], "Bodega de la Panamericana Sur")
        self.assertEqual(estado["ubicacion_pc"], "Esquina norte, junto al portón")
        # El periodo operacional es del SCI-201: ya no se ofrece a los demás formularios.
        self.assertNotIn("periodo_numero", estado)

    def test_sin_201_el_lugar_sale_de_la_emergencia(self):
        emergencia = self.crear_emergencia("VAL-DIR")
        estado = estado_del_incidente(emergencia)
        self.assertEqual(estado["lugar_incidente"], emergencia.direccion)

    def test_un_campo_con_valor_propio_no_se_pisa(self):
        """Lo que alguien escribió manda sobre lo que el sistema deduce."""
        emergencia = self.crear_emergencia("VAL-PISA")
        estado = estado_del_incidente(emergencia)
        ofrecido = prepoblar(
            ESQUEMAS_SCI["201"], {"lugar_incidente": "Lo que escribí yo"}, estado,
        )
        self.assertNotIn("lugar_incidente", ofrecido)

    def test_un_campo_vacio_se_ofrece_hecho(self):
        emergencia = self.crear_emergencia("VAL-OFRECE")
        estado = estado_del_incidente(emergencia)
        ofrecido = prepoblar(ESQUEMAS_SCI["201"], {}, estado)
        self.assertEqual(ofrecido["lugar_incidente"], emergencia.direccion)

    def test_las_fechas_del_periodo_salen_del_periodo(self):
        """Antes se copiaban del formulario más reciente que las tuviera.

        Tres documentos del mismo periodo podían declarar tres fechas distintas
        sin que nada lo advirtiera.
        """
        emergencia = self.crear_emergencia("VAL-FECHAS")
        periodo = emergencia.periodo_vigente()
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci_editar", args=["202", emergencia.pk])
        )
        esperado = timezone.localtime(periodo.inicio).strftime("%Y-%m-%dT%H:%M")
        self.assertContains(respuesta, esperado)

    def test_el_211_hereda_el_puesto_de_comando_del_201(self):
        """Dónde está el PC lo declara el campo 8 del SCI-201."""
        from .services_sci import crear_sci211_desde_emergencia

        emergencia = self.crear_emergencia("VAL-211")
        self.crear_formulario(emergencia, "201", {
            "ubicacion_pc": "Patio de la escuela Isabel la Católica",
        })
        sci211 = crear_sci211_desde_emergencia(emergencia, self.usuario)
        self.assertEqual(
            sci211.punto_registro, "Patio de la escuela Isabel la Católica"
        )

    def test_sin_el_201_el_211_conserva_su_valor_de_siempre(self):
        from .services_sci import crear_sci211_desde_emergencia

        emergencia = self.crear_emergencia("VAL-211B")
        sci211 = crear_sci211_desde_emergencia(emergencia, self.usuario)
        self.assertEqual(sci211.punto_registro, "Puesto de Comando")

    def test_el_201_sugiere_al_comandante_como_firmante(self):
        emergencia = self.crear_emergencia("VAL-CI")
        self.crear_formulario(emergencia, "201", {"evaluacion_inicial": "x"},
                              preparado_por="Mayor Luis Andrade")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci_editar", args=["202", emergencia.pk])
        )
        self.assertContains(respuesta, "Mayor Luis Andrade")


class LaHoraExactaDeAperturaTests(BaseValidacion):
    """Escribir la hora exacta de apertura se rechazaba por unos segundos.

    Lo encontró el usuario en pantalla: el aviso decía que «23/10/2026 20:14» era
    anterior a la apertura del expediente, ocurrida a las «23/10/2026 20:14». Las
    dos horas eran idénticas y el mensaje, incomprensible.

    La causa: los controles «datetime-local» solo guardan horas y minutos, de
    modo que la hora exacta de apertura llega como 20:14:00 mientras el
    expediente se abrió a las 20:14:16. Dieciséis segundos bastaban. Y era el
    propio «min» del formulario —que también se recorta al minuto— el que
    ofrecía ese valor como válido.
    """

    def test_la_hora_exacta_de_apertura_se_acepta(self):
        emergencia = self.crear_emergencia("VAL-EXACTA")
        self.crear_formulario(emergencia, "201", {"evaluacion_inicial": "x"})
        referencia = fecha_de_referencia(emergencia)
        exacta = timezone.localtime(referencia).strftime("%Y-%m-%dT%H:%M")
        self.assertEqual(
            fechas_anteriores_al_inicio(
                ESQUEMAS_SCI["202"], {"periodo_inicio": exacta}, referencia,
            ),
            [],
            "La hora exacta de apertura no puede ser anterior a sí misma.",
        )

    def test_la_referencia_no_lleva_segundos(self):
        """Así el «min» del navegador y la regla del servidor son el mismo valor."""
        emergencia = self.crear_emergencia("VAL-SEG")
        self.crear_formulario(emergencia, "201", {"evaluacion_inicial": "x"})
        referencia = fecha_de_referencia(emergencia)
        self.assertEqual(referencia.second, 0)
        self.assertEqual(referencia.microsecond, 0)

    def test_lo_que_el_min_ofrece_el_servidor_lo_acepta(self):
        """Las dos mitades de la regla tienen que decir lo mismo.

        Si el navegador ofrece un valor que el servidor rechaza, el usuario se
        queda sin saber qué escribir: lo escribe, se lo rechazan, y el aviso le
        señala dos horas iguales.
        """
        emergencia = self.crear_emergencia("VAL-COHER")
        self.crear_formulario(emergencia, "201", {"evaluacion_inicial": "x"})
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci_editar", args=["202", emergencia.pk])
        )
        import re as _re

        minimos = _re.findall(rb'min="([^"]+)"', respuesta.content)
        self.assertTrue(minimos, "El editor debe poner la cota en los controles.")
        minimo = minimos[0].decode()
        guardado = self.client.post(
            reverse("emergencias:sci_editar", args=["202", emergencia.pk]),
            {"objetivos": "Confinar el fuego", "periodo_inicio": minimo},
            follow=True,
        )
        self.assertContains(guardado, "guardado correctamente")
        self.assertNotContains(guardado, "anteriores a la apertura")


# ──────────────────────────────────────────────────────────────────────
# 4. El punto 4 del SCI-201, un campo por cada sub-punto
# ──────────────────────────────────────────────────────────────────────

SUBPUNTOS = {
    "evaluacion_naturaleza": "Incendio estructural con propagación al entrepiso.",
    "evaluacion_amenazas": "Riesgo de colapso de la cubierta.",
    "evaluacion_areas_afectadas": "Planta baja, entrepiso y bodega contigua.",
    "evaluacion_aislamiento": "Perímetro de 50 m, calle cerrada.",
}


class EvaluacionInicialSeparadaTests(BaseValidacion):
    """Naturaleza, amenazas, áreas afectadas y aislamiento, cada una en su campo.

    El punto 4 del formulario oficial las lista como viñetas y se guardaban
    como un solo párrafo, que no se puede consultar: nadie puede preguntarle a
    un texto libre cuántos incidentes tuvieron riesgo de colapso. Con una clave
    por sub-punto, los reportes y las estadísticas pueden leerlas.
    """

    def editor(self, emergencia):
        self.client.force_login(self.usuario)
        return self.client.get(
            reverse("emergencias:sci_editar", args=["201", emergencia.pk])
        ).content.decode()

    def test_el_editor_ofrece_un_campo_por_sub_punto(self):
        import re as _re

        html = self.editor(self.crear_emergencia("EVA-EDIT"))
        for nombre in SUBPUNTOS:
            self.assertEqual(
                len(_re.findall(rf'<textarea name="{nombre}"', html)), 1, nombre
            )
        # Y ya no la casilla única en la que se mezclaban.
        self.assertNotIn('name="evaluacion_inicial"', html)

    def test_cada_sub_punto_se_guarda_en_su_propia_clave(self):
        emergencia = self.crear_emergencia("EVA-GUARDA")
        self.client.force_login(self.usuario)
        self.client.post(
            reverse("emergencias:sci_editar", args=["201", emergencia.pk]),
            dict(SUBPUNTOS),
        )
        datos = FormularioSCI.objects.get(emergencia=emergencia, codigo_sci="201").datos
        for nombre, texto in SUBPUNTOS.items():
            self.assertEqual(datos[nombre], texto)
        # Las claves no se contaminan entre sí: cada texto vive solo en la suya.
        for nombre, texto in SUBPUNTOS.items():
            otros = [v for k, v in datos.items() if k != nombre and isinstance(v, str)]
            self.assertNotIn(texto, otros, nombre)

    def test_cada_sub_punto_vacio_se_pide_por_su_nombre(self):
        """El aviso dice cuál falta, no un genérico «evaluación inicial»."""
        emergencia = self.crear_emergencia("EVA-FALTA")
        formulario = self.crear_formulario(
            emergencia, "201",
            {"lugar_incidente": "Av. Amazonas", "objetivos_iniciales": "Confinar",
             "evaluacion_naturaleza": "Incendio", "evaluacion_amenazas": "Colapso"},
            preparado_por="Mayor Andrade",
        )
        faltan = " | ".join(campos_obligatorios_vacios(formulario))
        self.assertIn("Áreas afectadas", faltan)
        self.assertIn("Aislamiento", faltan)
        self.assertNotIn("Naturaleza", faltan)
        self.assertNotIn("Amenazas", faltan)

    def test_la_hoja_de_impresion_rotula_cada_sub_punto(self):
        emergencia = self.crear_emergencia("EVA-HOJA")
        self.crear_formulario(emergencia, "201", dict(SUBPUNTOS))
        self.client.force_login(self.usuario)
        html = self.client.get(
            reverse("emergencias:sci_visualizar", args=["201", emergencia.pk])
        ).content.decode()
        for titulo in ("Naturaleza del incidente", "Amenazas", "Áreas afectadas",
                       "Aislamiento"):
            self.assertIn(f"• {titulo}.", html)
        for texto in SUBPUNTOS.values():
            self.assertIn(texto, html)

    # -- lo escrito cuando era una sola casilla ---------------------------------

    def test_lo_antiguo_se_ve_y_se_conserva_al_guardar(self):
        """Un borrador de cuando era una casilla no pierde su texto.

        No se reparte solo —no hay forma de saber dónde acaba la naturaleza y
        empiezan las amenazas en un párrafo— pero tampoco se borra: se muestra
        mientras los cuatro campos estén vacíos, y el primer guardado lo deja
        donde estaba.
        """
        emergencia = self.crear_emergencia("EVA-ANTIGUO")
        self.crear_formulario(
            emergencia, "201", {"evaluacion_inicial": "Humo denso y dos heridos."},
        )
        self.assertIn("Humo denso y dos heridos.", self.editor(emergencia))

        self.client.post(
            reverse("emergencias:sci_editar", args=["201", emergencia.pk]),
            {"evaluacion_naturaleza": "Incendio en bodega"},
        )
        datos = FormularioSCI.objects.get(emergencia=emergencia, codigo_sci="201").datos
        self.assertEqual(datos["evaluacion_inicial"], "Humo denso y dos heridos.")
        self.assertEqual(datos["evaluacion_naturaleza"], "Incendio en bodega")
        # Con un sub-punto ya escrito, lo antiguo deja de mostrarse en el editor.
        self.assertNotIn("Texto escrito antes de separar", self.editor(emergencia))

    def test_el_periodo_cerrado_conserva_a_la_vista_lo_antiguo(self):
        from .services import iniciar_periodo_operacional

        emergencia = self.crear_emergencia("EVA-CERRADO")
        self.crear_formulario(
            emergencia, "201", {"evaluacion_inicial": "Texto de una sola casilla."},
        )
        iniciar_periodo_operacional(emergencia, self.usuario, "Relevo de turno")
        self.assertIn("Texto de una sola casilla.", self.editor(emergencia))

    # -- la guarda -------------------------------------------------------------

    def test_ningun_campo_enumera_conceptos_distintos_en_su_ayuda(self):
        """El antipatrón: «Incluya: - A. - B. - C.» sobre una sola casilla.

        Si la ayuda de un campo lista varios conceptos, cada uno es un dato
        distinto y merece su campo. Esta guarda lo busca en todos los esquemas
        para que no vuelva a colarse.
        """
        import re as _re

        enumera = _re.compile(r"(?:^|\s)[-•]\s*\w[^-•]*[-•]\s*\w")
        culpables = [
            f"SCI-{codigo} · {seccion['etiqueta']}"
            for codigo, esquema in ESQUEMAS_SCI.items()
            for seccion in esquema["secciones"]
            if enumera.search(seccion.get("ayuda", ""))
        ]
        self.assertEqual(culpables, [], culpables)

    # -- el panel y el PDF ------------------------------------------------------

    def test_el_panel_y_el_pdf_leen_los_cuatro_campos(self):
        from dashboard.pdf import generar_pdf_emergencia
        from dashboard.services import datos_informe_emergencia

        emergencia = self.crear_emergencia("EVA-INFORME")
        self.crear_formulario(emergencia, "201", dict(SUBPUNTOS))
        datos = datos_informe_emergencia(emergencia)
        self.assertEqual(
            [etiqueta for etiqueta, _ in datos["evaluacion_items"]],
            ["Naturaleza del incidente", "Amenazas", "Áreas afectadas", "Aislamiento"],
        )
        self.assertTrue(generar_pdf_emergencia(datos).startswith(b"%PDF"))

    def test_el_panel_sigue_mostrando_el_texto_antiguo(self):
        from dashboard.services import datos_informe_emergencia

        emergencia = self.crear_emergencia("EVA-INFORME-VIEJO")
        self.crear_formulario(
            emergencia, "201", {"evaluacion_inicial": "Evaluación de una casilla."},
        )
        datos = datos_informe_emergencia(emergencia)
        self.assertEqual(
            datos["evaluacion_items"],
            [("Evaluación inicial", "Evaluación de una casilla.")],
        )


# ──────────────────────────────────────────────────────────────────────
# 5. Tablas dinámicas: una fila para empezar, y solo se guarda lo escrito
# ──────────────────────────────────────────────────────────────────────

class TablasDinamicasTests(BaseValidacion):
    """Nada de 24 filas en blanco: una para empezar y un botón para las demás.

    El SCI-201 precargaba 24 filas de acciones y los demás formularios entre 4
    y 14. Nadie las iba a llenar: ensuciaban la hoja, obligaban a desplazarse en
    el teléfono y daban a entender que había que completarlas. Ahora la pantalla
    abre con una sola fila y se agregan las que hagan falta. El papel es otra
    cosa: la hoja impresa y la de lectura no llevan relleno —solo las filas con
    datos— y el formulario en blanco del catálogo conserva sus renglones, que
    es el único que se imprime para escribirlo a mano.
    """

    def editar(self, codigo, emergencia):
        self.client.force_login(self.usuario)
        return self.client.get(
            reverse("emergencias:sci_editar", args=[codigo, emergencia.pk])
        ).content.decode()

    def guardar(self, codigo, emergencia, datos):
        self.client.force_login(self.usuario)
        return self.client.post(
            reverse("emergencias:sci_editar", args=[codigo, emergencia.pk]), datos
        )

    def test_toda_tabla_dinamica_abre_con_una_sola_fila(self):
        """Los 12 esquemas: ninguna tabla de filas libres precarga más de una."""
        from .esquemas_sci import secciones_con_valores

        excesos = []
        for codigo, esquema in ESQUEMAS_SCI.items():
            for seccion in secciones_con_valores(esquema, {}):
                if seccion["tipo"] != TABLA or seccion.get("filas_fijas"):
                    continue
                if len(seccion["filas"]) != 1:
                    excesos.append(f"SCI-{codigo}/{seccion['nombre']}: {len(seccion['filas'])}")
        self.assertEqual(excesos, [], excesos)

    def test_las_tablas_de_filas_fijas_conservan_sus_posiciones_oficiales(self):
        """El SCI-203 trae las posiciones del organigrama escritas: no son filas vacías."""
        from .esquemas_sci import secciones_con_valores

        comando = next(
            s for s in secciones_con_valores(ESQUEMAS_SCI["203"], {})
            if s["nombre"] == "comando"
        )
        self.assertGreater(len(comando["filas"]), 1)

    def test_el_201_abre_con_una_fila_y_el_boton_de_agregar(self):
        import re as _re

        html = self.editar("201", self.crear_emergencia("DIN-201"))
        self.assertEqual(len(_re.findall(r'name="acciones-\d+-accion"', html)), 1)
        self.assertIn('name="acciones-0-accion"', html)
        self.assertNotIn('name="acciones-1-accion"', html)
        self.assertIn("Agregar acción", html)
        self.assertIn("sci-tabla__quitar", html)

    def test_el_editor_generico_tambien_abre_con_una_fila_por_tabla(self):
        import re as _re

        html = self.editar("214", self.crear_emergencia("DIN-214"))
        self.assertEqual(len(_re.findall(r'name="actividades-\d+-evento"', html)), 1)
        self.assertEqual(len(_re.findall(r'name="personal-\d+-nombre"', html)), 1)
        self.assertIn("Agregar actividad", html)
        self.assertIn("Agregar persona", html)

    def test_al_reabrir_solo_estan_las_filas_guardadas(self):
        import re as _re

        emergencia = self.crear_emergencia("DIN-REABRE")
        self.crear_formulario(emergencia, "201", {"acciones": [
            {"fecha_hora": "", "accion": "Primera"},
            {"fecha_hora": "", "accion": "Segunda"},
        ]})
        html = self.editar("201", emergencia)
        self.assertEqual(len(_re.findall(r'name="acciones-\d+-accion"', html)), 2)

    # -- el guardado --------------------------------------------------------------

    def test_las_filas_vacias_no_se_guardan_y_las_demas_no_se_mezclan(self):
        """Tres escritas, una quitada del medio y una en blanco sin quitar.

        Lo que manda el navegador tras quitar la fila del medio ya viene
        renumerado, pero el servidor no debe depender de eso: lee los índices que
        llegan, en orden, e ignora las filas sin contenido, estén donde estén.
        """
        emergencia = self.crear_emergencia("DIN-GUARDA")
        self.guardar("201", emergencia, {
            "acciones-0-accion": "Arribo de la primera unidad",
            "acciones-0-fecha_hora": "",
            # el índice 1 se quitó; el 2 conserva su propia acción
            "acciones-2-accion": "Extricación de la víctima",
            "acciones-2-fecha_hora": "",
            # una fila en blanco que nadie quitó, y otra con solo espacios
            "acciones-3-accion": "",
            "acciones-3-fecha_hora": "",
            "acciones-4-accion": "   ",
            "acciones-4-fecha_hora": "",
        })
        filas = FormularioSCI.objects.get(
            emergencia=emergencia, codigo_sci="201"
        ).datos["acciones"]
        self.assertEqual(
            [fila["accion"] for fila in filas],
            ["Arribo de la primera unidad", "Extricación de la víctima"],
        )
        self.assertFalse(any(not any(fila.values()) for fila in filas))

    def test_un_formulario_sin_filas_guarda_una_lista_vacia(self):
        emergencia = self.crear_emergencia("DIN-VACIO")
        self.guardar("201", emergencia, {
            "acciones-0-accion": "", "acciones-0-fecha_hora": "",
        })
        datos = FormularioSCI.objects.get(emergencia=emergencia, codigo_sci="201").datos
        self.assertEqual(datos["acciones"], [])

    # -- la hoja impresa ------------------------------------------------------------

    # -- la guarda -------------------------------------------------------------------

    def test_los_dos_editores_cargan_el_comportamiento_de_agregar_y_quitar(self):
        """Sin el fragmento el botón existe pero no hace nada, y no avisa.

        El comportamiento va en línea, no como archivo estático: llega con la
        página, sin una segunda descarga que pueda fallar con la señal perdida.
        """
        from pathlib import Path

        from django.conf import settings

        raiz = Path(settings.BASE_DIR) / "templates" / "emergencias"
        for plantilla in ("sci_editar.html", "sci_editar_201.html"):
            fuente = (raiz / plantilla).read_text(encoding="utf-8")
            self.assertIn("fragmentos/tablas_dinamicas.html", fuente, plantilla)
        fragmento = (raiz / "fragmentos" / "tablas_dinamicas.html").read_text(encoding="utf-8")
        # Renumera todas las filas tras agregar o quitar, y deshace el botón
        # «Ahora» copiado, cuyo evento no viaja con el clon.
        self.assertIn("renumerar()", fragmento)
        self.assertIn("campo-con-ahora", fragmento)


# ──────────────────────────────────────────────────────────────────────
# 6. La hoja impresa y la de lectura: solo las filas con datos
# ──────────────────────────────────────────────────────────────────────

class HojaDeLecturaTests(BaseValidacion):
    """Un documento oficial no lleva renglones de relleno.

    En el editor la tabla abría con una fila y crecía con el botón de agregar,
    pero la hoja impresa seguía dibujando entre 5 y 24 filas vacías con bordes:
    una estrategia registrada salía como una fila entre seis en blanco. El
    documento impreso y toda vista de solo lectura se dibujan ahora con las filas
    que existen, sean 1 o 20.
    """

    def con_datos(self, esquema, filas_llenas, vacias=2):
        """Una tabla guardada con ``filas_llenas`` filas escritas y alguna vacía."""
        datos = {}
        for seccion in esquema["secciones"]:
            if seccion["tipo"] != TABLA or seccion.get("filas_fijas"):
                continue
            columnas = [c["nombre"] for c in seccion["columnas"]]
            llenas = [
                {nombre: (f"valor {n}" if indice == 0 else "") for indice, nombre in enumerate(columnas)}
                for n in range(filas_llenas)
            ]
            datos[seccion["nombre"]] = llenas + [{nombre: "" for nombre in columnas}] * vacias
        return datos

    def test_en_lectura_cada_tabla_tiene_exactamente_las_filas_guardadas(self):
        """Los 12 esquemas, con 1 y con 7 filas escritas y dos vacías de paso."""
        from .esquemas_sci import MODO_LECTURA, secciones_con_valores

        mal = []
        for codigo, esquema in ESQUEMAS_SCI.items():
            for escritas in (1, 7):
                datos = self.con_datos(esquema, escritas)
                for seccion in secciones_con_valores(esquema, datos, MODO_LECTURA):
                    if seccion["tipo"] != TABLA or seccion.get("filas_fijas"):
                        continue
                    if len(seccion["filas"]) != escritas:
                        mal.append(f"SCI-{codigo}/{seccion['nombre']}: {len(seccion['filas'])} != {escritas}")
        self.assertEqual(mal, [], mal)

    def test_una_tabla_sin_datos_se_lee_vacia_y_no_con_renglones(self):
        from .esquemas_sci import MODO_LECTURA, secciones_con_valores

        for codigo, esquema in ESQUEMAS_SCI.items():
            for seccion in secciones_con_valores(esquema, {}, MODO_LECTURA):
                if seccion["tipo"] == TABLA:
                    self.assertEqual(seccion["filas"], [], f"SCI-{codigo}/{seccion['nombre']}")

    def test_en_lectura_una_posicion_fija_sin_nadie_asignado_no_se_imprime(self):
        """SCI-203: el listado de asignación solo muestra a quien está asignado."""
        from .esquemas_sci import MODO_EDICION, MODO_LECTURA, secciones_con_valores

        esquema = ESQUEMAS_SCI["203"]
        comando = next(s for s in esquema["secciones"] if s["nombre"] == "comando")
        columnas = [c["nombre"] for c in comando["columnas"]]
        posiciones = comando["filas_fijas"]
        datos = {"comando": [
            {columnas[0]: posiciones[0], columnas[1]: "Mayor Andrade"},
        ] + [{columnas[0]: p, columnas[1]: ""} for p in posiciones[1:]]}

        en_lectura = next(
            s for s in secciones_con_valores(esquema, datos, MODO_LECTURA)
            if s["nombre"] == "comando"
        )
        self.assertEqual(len(en_lectura["filas"]), 1)
        self.assertEqual(en_lectura["filas"][0]["celdas"][0]["valor"], posiciones[0])
        # En el editor siguen todas: ahí hay que poder escribir en cualquiera.
        en_edicion = next(
            s for s in secciones_con_valores(esquema, datos, MODO_EDICION)
            if s["nombre"] == "comando"
        )
        self.assertEqual(len(en_edicion["filas"]), len(posiciones))

    def test_el_formulario_en_blanco_del_catalogo_conserva_sus_renglones(self):
        """El único que se imprime para escribirlo a mano."""
        from .esquemas_sci import MODO_BLANCO, secciones_con_valores

        esquema = ESQUEMAS_SCI["202"]
        plan = next(
            s for s in secciones_con_valores(esquema, {}, MODO_BLANCO) if s["nombre"] == "plan"
        )
        tabla = next(s for s in esquema["secciones"] if s["nombre"] == "plan")
        self.assertEqual(len(plan["filas"]), tabla["filas_impresion"])
        self.assertGreater(len(plan["filas"]), 1)

    # -- las hojas de verdad -----------------------------------------------------------

    def hoja(self, codigo, emergencia):
        self.client.force_login(self.usuario)
        return self.client.get(
            reverse("emergencias:sci_visualizar", args=[codigo, emergencia.pk])
        ).content.decode()

    def test_la_hoja_del_201_imprime_solo_las_acciones_guardadas(self):
        import re as _re

        emergencia = self.crear_emergencia("LEC-201")
        self.crear_formulario(emergencia, "201", {"acciones": [
            {"fecha_hora": "", "accion": "Arribo"},
            {"fecha_hora": "", "accion": "Extricación"},
        ]})
        html = self.hoja("201", emergencia)
        tabla = html[html.index('class="sci201-actions"'):]
        tabla = tabla[:tabla.index("</table>")]
        self.assertEqual(len(_re.findall(r"<tr>", tabla)) - 1, 2)  # menos el encabezado
        self.assertIn("Arribo", tabla)
        self.assertIn("Extricación", tabla)

    def test_sin_acciones_la_hoja_del_201_lo_dice_en_una_fila(self):
        import re as _re

        emergencia = self.crear_emergencia("LEC-201-VACIO")
        self.crear_formulario(emergencia, "201", {})
        html = self.hoja("201", emergencia)
        tabla = html[html.index('class="sci201-actions"'):]
        tabla = tabla[:tabla.index("</table>")]
        self.assertEqual(len(_re.findall(r"<tr>", tabla)) - 1, 1)
        self.assertIn("Sin acciones registradas", tabla)

    def test_la_hoja_generica_imprime_solo_las_filas_guardadas(self):
        """SCI-214: una persona y una actividad son una fila cada una, no seis y catorce."""
        import re as _re

        emergencia = self.crear_emergencia("LEC-214")
        self.crear_formulario(emergencia, "214", {
            "personal": [{"nombre": "Cap. Vaca", "posicion": "Jefe", "institucion": "CB"}],
            "actividades": [{"hora": "10:15", "evento": "Arribo de la primera unidad"}],
        })
        html = self.hoja("214", emergencia)
        self.assertEqual(len(_re.findall(r"<tbody>.*?</tbody>", html, _re.S)), 2)
        for tbody in _re.findall(r"<tbody>.*?</tbody>", html, _re.S):
            self.assertEqual(tbody.count("<tr>"), 1, tbody[:200])
        self.assertIn("Cap. Vaca", html)
        self.assertIn("Arribo de la primera unidad", html)
        self.assertNotIn("Sin registros", html)

    def test_sin_filas_la_hoja_generica_dice_sin_registros(self):
        import re as _re

        emergencia = self.crear_emergencia("LEC-214-VACIO")
        self.crear_formulario(emergencia, "214", {})
        html = self.hoja("214", emergencia)
        for tbody in _re.findall(r"<tbody>.*?</tbody>", html, _re.S):
            self.assertEqual(tbody.count("<tr>"), 1)
            self.assertIn("Sin registros", tbody)

    # -- el aviso de disponibilidad no es parte del documento --------------------------

    def test_el_aviso_del_editor_no_se_imprime_pero_tampoco_se_borra(self):
        from .esquemas_sci import MODO_EDICION, MODO_LECTURA, secciones_con_valores

        guardado = "AB-01 - Autobomba (Estación Central) · ya asignada a otra emergencia"
        datos = {"plan": [{
            "estrategia": "Ataque", "tactica": "Línea", "recursos_lugar": "",
            "recursos_solicitar": guardado, "asignacion": "Norte",
        }]}
        esquema = ESQUEMAS_SCI["202"]

        def celda(modo):
            plan = next(s for s in secciones_con_valores(esquema, datos, modo) if s["nombre"] == "plan")
            columnas = [c["columna"]["nombre"] for c in plan["filas"][0]["celdas"]]
            return plan["filas"][0]["celdas"][columnas.index("recursos_solicitar")]["valor"]

        self.assertEqual(celda(MODO_LECTURA), "AB-01 - Autobomba (Estación Central)")
        # En el editor la cadena guardada sigue siendo la misma: es lo que
        # selecciona la opción del desplegable al reabrir el formulario.
        self.assertEqual(celda(MODO_EDICION), guardado)
        # Y lo guardado no se tocó.
        self.assertIn("ya asignada a otra emergencia", datos["plan"][0]["recursos_solicitar"])

    def test_una_celda_sin_aviso_o_con_punto_medio_en_el_nombre_queda_igual(self):
        from .esquemas_sci import sin_aviso_de_disponibilidad as limpio

        self.assertEqual(limpio("AMB-1 - Ambulancia (Estación Sur)"), "AMB-1 - Ambulancia (Estación Sur)")
        self.assertEqual(limpio("Rescate · norte (Base)"), "Rescate · norte (Base)")
        self.assertEqual(limpio(""), "")
        self.assertEqual(limpio(None), "")
