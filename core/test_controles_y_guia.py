"""Los controles de fecha y hora, y el botón de la guía.

Dos defectos que se ven de pie, con prisa y con guantes:

* En «15. Fecha y hora» del SCI-201 el control mostraba «dd/mm/aa» y el icono del
  calendario cortado: la columna de la tabla le daba 66 px y la hoja, 10 px de letra.
  Ahora todo control de fecha y hora declara el ancho que necesita su texto.
* El botón «Guía» cambiaba de sitio —uno en la barra de arriba, que en escritorio no
  se veía, y otro distinto en la cabecera de cinco pantallas— y la letra del modal
  del tour era de 12 a 14 px. Ahora es uno solo, fijo arriba a la derecha.
"""

import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

RAIZ = Path(settings.BASE_DIR)


def fuente(*partes):
    texto = RAIZ.joinpath(*partes).read_text(encoding="utf-8")
    return texto.replace(chr(13) + chr(10), chr(10))


def regla(css, selector):
    """El cuerpo de la primera regla cuyo selector es exactamente ``selector``."""
    encontrada = re.search(r"(?:^|[};/])\s*" + re.escape(selector) + r"\s*\{([^{}]*)\}", css)
    assert encontrada, f"no hay una regla «{selector}»"
    return encontrada.group(1)


class ControlesDeFechaYHoraTests(SimpleTestCase):
    TIPOS = ('input[type="date"]', 'input[type="time"]', 'input[type="datetime-local"]')

    def css(self):
        return fuente("static", "css", "componentes.css")

    def test_todo_control_de_fecha_y_hora_ocupa_su_caja_y_no_baja_de_44_px(self):
        css = self.css()
        base = regla(css, ",\n".join(self.TIPOS))
        self.assertIn("width: 100%", base)
        self.assertIn("box-sizing: border-box", base)
        altura = re.search(r"min-height:\s*([0-9.]+)rem", base)
        self.assertGreaterEqual(float(altura.group(1)) * 16, 44)
        # La letra no baja de 15 px: en el SCI la hoja traía 10 y 11.
        letra = re.search(r"font-size:\s*([0-9.]+)rem", base)
        self.assertGreaterEqual(float(letra.group(1)) * 16, 15)

    def test_cada_tipo_declara_el_ancho_que_necesita_su_texto(self):
        css = self.css()
        minimos = {
            'input[type="date"]': 10,           # dd/mm/aaaa + icono
            'input[type="time"]': 8,            # --:-- + icono
            'input[type="datetime-local"]': 14, # dd/mm/aaaa --:-- + icono
        }
        for selector, rem in minimos.items():
            with self.subTest(tipo=selector):
                cuerpo = regla(css, selector)
                valor = float(re.search(r"min-width:\s*([0-9.]+)rem", cuerpo).group(1))
                self.assertGreaterEqual(valor, rem)

    def test_el_icono_tiene_blanco_de_pulsacion(self):
        css = self.css()
        indicador = regla(
            css, ",\n".join(f"{t}::-webkit-calendar-picker-indicator" for t in self.TIPOS)
        )
        self.assertIn("cursor: pointer", indicador)
        self.assertIn("padding:", indicador)

    def test_el_boton_ahora_es_pulsable_y_el_campo_con_ahora_deja_envolver(self):
        css = self.css()
        ahora = regla(css, ".campo-ahora")
        altura = re.search(r"min-height:\s*([0-9.]+)rem", ahora)
        self.assertGreaterEqual(float(altura.group(1)) * 16, 44)
        envoltura = regla(css, ".campo-con-ahora")
        self.assertIn("flex-wrap: wrap", envoltura)
        # El campo ya no puede encogerse por debajo de su ancho mínimo.
        self.assertNotRegex(css, r"\.campo-con-ahora\s*>\s*input\s*\{[^}]*min-width:\s*0")

    def test_las_tablas_del_sci_ya_no_recortan_el_control(self):
        css = fuente("static", "emergencias", "css", "sci_editor.css")
        # Antes: «min-width:0; font-size:11px» sobre el control de la celda.
        self.assertNotRegex(
            css, r'input\[type="datetime-local"\][^{}]*\{[^}]*min-width:\s*0'
        )
        self.assertNotRegex(css, r'input\[type="time"\][^{}]*\{[^}]*font-size:\s*11px')
        # La tabla que lleva un control de fecha deja de ser de disposición fija.
        self.assertIn('.sci-tabla table:has(input[type="datetime-local"]', css)
        self.assertIn("table-layout:auto", css)
        self.assertIn(".sci-tabla{overflow-x:auto}", css)

    def test_la_columna_de_la_fecha_del_201_cabe_el_control_completo(self):
        css = fuente("static", "emergencias", "css", "sci_editor.css")
        ancho = re.search(
            r"@media screen and \(min-width:761px\)\{\.sci201-actions th:first-child,"
            r"\.sci201-actions td:first-child\{width:([0-9.]+)rem\}\}", css,
        )
        self.assertIsNotNone(ancho)
        # 14,5 rem de control mínimo más el relleno de la celda.
        self.assertGreaterEqual(float(ancho.group(1)), 15)
        control = re.search(
            r'\.sci201-actions input\[type="datetime-local"\]\{height:([0-9.]+)rem', css
        )
        self.assertGreaterEqual(float(control.group(1)) * 16, 44)

    def test_la_cuadricula_del_211_solo_usa_cuatro_columnas_si_caben(self):
        css = fuente("static", "emergencias", "css", "sci211.css")
        self.assertIn("@media(max-width:1399px){.official-resource-grid{grid-template-columns:repeat(2", css)
        self.assertNotIn("@media(max-width:900px){.official-resource-grid", css)

    def test_el_encabezado_del_periodo_no_hereda_los_11_px_de_su_etiqueta(self):
        css = fuente("static", "emergencias", "css", "sci_editor.css")
        self.assertIn('.sci-periodo input[type="datetime-local"]', css)
        self.assertRegex(css, r"\.sci-periodo input\[type=\"time\"\]\{font-size:\.95rem\}")


class BotonDeLaGuiaTests(SimpleTestCase):
    def test_es_uno_solo_fijo_arriba_a_la_derecha(self):
        css = fuente("static", "css", "componentes.css")
        boton = regla(css, ".tour-btn")
        self.assertIn("position: fixed", boton)
        self.assertRegex(boton, r"top:\s*\.75rem")
        self.assertRegex(boton, r"right:")
        self.assertNotRegex(boton, r"bottom:")
        altura = re.search(r"min-height:\s*([0-9.]+)rem", boton)
        self.assertGreaterEqual(float(altura.group(1)) * 16, 44)
        # Ya no se esconde el texto en pantallas estrechas ni se oculta con la barra.
        self.assertNotIn(".tour-btn span { display: none; }", css)

    def test_vive_fuera_de_la_barra_de_arriba(self):
        """La barra se oculta en escritorio; dentro de ella el botón desaparecía."""
        marcado = fuente("templates", "componentes", "navbar.html")
        barra = re.search(r'<header class="navbar">.*?</header>', marcado, re.S).group(0)
        self.assertNotIn("tour-btn", barra)
        self.assertEqual(marcado.count('class="tour-btn"'), 1)
        self.assertIn("<span>Guía</span>", marcado)

    def test_ninguna_pantalla_lleva_su_propio_boton_de_guia(self):
        culpables = []
        for plantilla in (RAIZ / "templates").rglob("*.html"):
            texto = plantilla.read_text(encoding="utf-8", errors="replace")
            if plantilla.name == "navbar.html":
                continue
            if "bomberosTour" in texto or re.search(r"\bguide-btn\b|--guide\b", texto):
                culpables.append(plantilla.name)
        self.assertEqual(culpables, [])
        css = fuente("static", "css", "componentes.css")
        self.assertNotRegex(css, r"\.guide-btn|--guide")

    def test_el_texto_del_tour_es_legible(self):
        css = fuente("static", "css", "componentes.css")
        medidas = {
            ".driver-popover .driver-popover-title": 1.2,
            ".driver-popover .driver-popover-description": 1.0,
            ".driver-popover .driver-popover-progress-text": 0.9,
        }
        for selector, minimo in medidas.items():
            with self.subTest(selector=selector):
                tam = float(re.search(r"font-size:\s*([0-9.]+)rem", regla(css, selector)).group(1))
                # De fábrica: 19 px, 14 px y 13 px.
                self.assertGreaterEqual(tam, minimo)
        botones = regla(css, ".driver-popover .driver-popover-footer button")
        self.assertGreaterEqual(float(re.search(r"font-size:\s*([0-9.]+)rem", botones).group(1)), 1.0)
        self.assertGreaterEqual(
            float(re.search(r"min-height:\s*([0-9.]+)rem", botones).group(1)) * 16, 44
        )

    def test_la_barra_pegajosa_del_editor_queda_por_debajo_del_boton(self):
        """Si se pegara a 0,5 rem, la tapaba el botón fijo de la esquina."""
        for hoja in ("sci_editor.css", "sci_catalog.css"):
            css = fuente("static", "emergencias", "css", hoja)
            self.assertIn(".sci-workspace__toolbar{position:sticky;top:4rem;", css, hoja)


class UnoSoloEnCadaPestanaTests(TestCase):
    PESTANAS = (
        "/emergencias/", "/dashboard/", "/instituciones/", "/inventario/",
        "/mapa/", "/usuarios/", "/emergencias/formularios-sci/211/",
    )

    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user(
            username="admin.guia", password="clave-de-prueba", cedula="0500000555",
            is_superuser=True, is_staff=True,
        )

    def test_cada_pestana_trae_un_solo_boton_de_guia(self):
        self.client.force_login(self.admin)
        for ruta in self.PESTANAS:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 200)
                html = respuesta.content.decode()
                self.assertEqual(html.count('class="tour-btn"'), 1)
                self.assertNotIn("guide-btn", html)
                self.assertNotIn("incident-action--guide", html)
                self.assertNotIn("inventory-action--guide", html)
                self.assertEqual(len(re.findall(r">\s*Guía\s*<", html)), 1, ruta)
