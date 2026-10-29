"""La hoja impresa del SCI-201 no pierde bordes ni cambia de maqueta al imprimir.

Dos fallos del mismo PDF:

* Una hoja carta imprime con unos 740 px de ancho útil. Las reglas «para teléfono»
  (``max-width: 760px``) valían también para el papel, y el formulario salía
  maquetado como en un móvil: cada celda en su propia fila, la página 1 desbordaba
  sobre una segunda y las cuatro páginas oficiales salían como cinco.
* La rejilla del SCI-201 dibujaba el borde superior e izquierdo en el contenedor y
  solo el derecho e inferior en cada celda. Al partirse entre dos páginas, el
  contenedor solo existe en la primera, y la segunda empezaba sin línea superior.

El navegador no está en las pruebas, así que se leen las hojas de estilo; el
resultado se verificó imprimiendo a PDF con Chrome y mirando cada página.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

HOJAS_DE_IMPRESION = (
    "static/emergencias/css/sci_editor.css",
    "static/emergencias/css/sci_graficos.css",
)


def consultas(css):
    return re.findall(r"@media([^{]*)\{", css)


class SoloEnPantallaTests(SimpleTestCase):
    def fuente(self, ruta):
        return (Path(settings.BASE_DIR) / ruta).read_text(encoding="utf-8")

    def test_ninguna_regla_de_telefono_vale_para_el_papel(self):
        """Toda consulta por ancho de pantalla debe decir «screen»."""
        for ruta in HOJAS_DE_IMPRESION:
            for consulta in consultas(self.fuente(ruta)):
                if "width" in consulta:
                    self.assertIn("screen", consulta, f"{ruta}: @media{consulta}")

    def test_las_consultas_acotadas_siguen_existiendo(self):
        """Sin ellas el editor dejaría de adaptarse al teléfono."""
        css = self.fuente("static/emergencias/css/sci_editor.css")
        self.assertGreaterEqual(css.count("@media screen and (max-width:760px)"), 4)


class BordesDelSCI201Tests(SimpleTestCase):
    def bloque_de_impresion(self):
        css = (Path(settings.BASE_DIR) / "static/emergencias/css/sci_editor.css").read_text(encoding="utf-8")
        inicio = css.index("Impresión de la hoja del SCI-201")
        return css[css.index("@media print{", inicio):]

    def test_cada_celda_de_la_rejilla_lleva_sus_cuatro_lados(self):
        bloque = self.bloque_de_impresion()
        celda = re.search(r"\.sci201-grid>\*\{([^}]*)\}", bloque).group(1)
        self.assertIn("border:1px solid #777!important", celda)
        # Se solapa con la vecina para que la línea no se doble.
        self.assertIn("margin:0 -1px -1px 0", celda)
        # El salto cae entre celdas; si una es más alta que la página, cada trozo se cierra.
        self.assertIn("break-inside:avoid", celda)
        self.assertIn("box-decoration-break:clone", celda)
        contenedor = re.search(r"\.sci201-grid\{([^}]*)\}", bloque).group(1)
        self.assertIn("border:0", contenedor)
        self.assertIn("padding:0 1px 1px 0", contenedor)

    def test_el_recuadro_del_croquis_se_cierra_por_los_cuatro_lados(self):
        """En pantalla no lleva borde inferior (lo pone la fila de abajo); en papel sí."""
        bloque = self.bloque_de_impresion()
        self.assertIn(".sci201-drawing{border:1px solid #777!important", bloque)

    def test_la_tabla_de_acciones_repite_su_encabezado_con_su_borde_superior(self):
        bloque = self.bloque_de_impresion()
        self.assertIn(".sci201-actions{border-collapse:separate;border-spacing:0}", bloque)
        self.assertIn(".sci201-actions th{border-top:1px solid #777!important}", bloque)
        self.assertIn(".sci201-actions thead{display:table-header-group}", bloque)
        self.assertIn(".sci201-actions tr{break-inside:avoid", bloque)

    def test_la_hoja_cabe_en_una_pagina_carta(self):
        """Carta menos márgenes de 10 mm son 980 px: 980 exactos desbordan por redondeo."""
        self.assertIn(".sci201-page{min-height:975px", self.bloque_de_impresion())


# ──────────────────────────────────────────────────────────────────────
# Las tablas de la hoja impresa no se salen del papel
# ──────────────────────────────────────────────────────────────────────

class TablasDeLaHojaTests(SimpleTestCase):
    """El SCI-211 de catálogo se imprimía con la última columna fuera de la hoja.

    La tabla del punto «Registro y control de recursos» tiene doce columnas. Las once
    que llevaban ancho sumaban el 100 % y a «Observaciones» no le quedaba nada: como
    la tabla es de disposición fija, se hacía más ancha que la hoja y la columna salía
    por el borde derecho, cortada, y arrastraba una segunda página casi vacía. Además
    la hoja horizontal medía en pantalla lo mismo que una vertical (760 px), y todas
    las celdas llevaban su estilo en línea, de modo que ninguna regla de impresión
    podía corregirlas.
    """

    def fuente(self, ruta):
        return (Path(settings.BASE_DIR) / ruta).read_text(encoding="utf-8")

    def test_los_anchos_de_las_columnas_dejan_sitio_a_las_que_no_lo_declaran(self):
        from emergencias.esquemas_sci import ESQUEMA_CATALOGO_211, ESQUEMAS_SCI

        esquemas = dict(ESQUEMAS_SCI, **{"211": ESQUEMA_CATALOGO_211})
        for codigo, esquema in esquemas.items():
            for seccion in esquema["secciones"]:
                if seccion["tipo"] != "tabla":
                    continue
                anchos = [float(c["ancho"].rstrip("%")) for c in seccion["columnas"] if c["ancho"]]
                libres = [c for c in seccion["columnas"] if not c["ancho"]]
                with self.subTest(formulario=codigo, tabla=seccion["nombre"]):
                    self.assertLessEqual(sum(anchos), 100)
                    if libres:
                        # Cada columna sin ancho necesita un trozo real de la hoja.
                        self.assertLessEqual(
                            sum(anchos), 100 - 8 * len(libres),
                            "las columnas sin ancho se quedan sin sitio y la tabla se sale",
                        )

    def test_la_tabla_de_la_hoja_es_de_disposicion_fija_y_parte_el_texto(self):
        plantilla = self.fuente("templates/emergencias/sci_preview.html")
        regla = re.search(r"\.sci-tbl\{([^}]*)\}", plantilla).group(1)
        self.assertIn("table-layout:fixed", regla)
        self.assertIn("max-width:100%", regla)
        celdas = re.search(r"\.sci-tbl th,\.sci-tbl td\{([^}]*)\}", plantilla).group(1)
        for propiedad in ("overflow-wrap:anywhere", "word-wrap:break-word", "word-break:break-word"):
            self.assertIn(propiedad, celdas)

    def test_la_tabla_densa_baja_la_letra_y_el_relleno(self):
        plantilla = self.fuente("templates/emergencias/sci_preview.html")
        self.assertIn(".sci-tbl--densa th{padding:3px 2px;font-size:7.5px", plantilla)
        self.assertIn(".sci-tbl--densa td{padding:3px 2px;font-size:8.5px", plantilla)
        # Se activa sola cuando la tabla pasa de ocho columnas.
        self.assertIn("seccion.columnas|length > 8", plantilla)

    def test_al_imprimir_el_encabezado_se_repite_y_ninguna_fila_se_parte(self):
        plantilla = self.fuente("templates/emergencias/sci_preview.html")
        impresion = plantilla[plantilla.index("@media print{body{background:#fff}"):]
        self.assertIn(".sci-tbl thead{display:table-header-group}", impresion)
        self.assertIn(".sci-tbl tr{break-inside:avoid", impresion)

    def test_las_celdas_ya_no_llevan_estilo_en_linea(self):
        """Un estilo en línea gana a toda regla de la hoja, también a las de impresión."""
        fuente = self.fuente("templates/emergencias/sci_preview.html")
        self.assertNotIn('<th style="height:26px', fuente)
        self.assertNotIn('<td style="height:26px', fuente)
        self.assertNotIn('<table style="width:100%;border-collapse', fuente)

    def test_la_hoja_horizontal_es_mas_ancha_que_la_vertical_en_pantalla(self):
        plantilla = self.fuente("templates/emergencias/sci_preview.html")
        self.assertIn(".paper--horizontal{width:min(1040px,calc(100% - 24px))", plantilla)
        self.assertIn("paper--horizontal", plantilla.split("<main class=\"paper")[1][:120])

    def test_el_sci_211_con_datos_ya_era_de_disposicion_fija(self):
        """La plantilla de impresión del 211 real no tenía el problema: se conserva así."""
        pdf = self.fuente("templates/emergencias/sci211/pdf.html")
        self.assertIn("table-layout:fixed", pdf)
        self.assertIn("overflow-wrap:anywhere", pdf)
