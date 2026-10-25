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
