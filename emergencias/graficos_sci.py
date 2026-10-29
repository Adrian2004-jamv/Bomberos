"""Los dos campos gráficos de los formularios SCI: el croquis y el organigrama.

El formulario oficial del SCI-201 pide un «mapa situacional o croquis» (punto 14)
y un «organigrama actual» (punto 17), y el SCI-202 repite el organigrama. Eran un
cuadro de texto: nadie dibuja un croquis con palabras, y el campo se quedaba vacío
o con una descripción que la hoja impresa no podía sustituir.

El croquis tuvo primero un lienzo para dibujar a mano. Los bomberos lo descartaron:
en la escena es más rápido fotografiar un plano o pedir el mapa del lugar que
dibujarlo con el dedo. Ahora el campo guarda una imagen que el navegador arma —una
foto subida o la captura del mapa en las coordenadas de la emergencia— y lo que
viene del navegador se valida aquí igual que antes.

Cada uno se guarda junto al texto que ya existía, no en su lugar, con la misma
convención que las firmas de las tablas (``nombre__firma``):

* ``croquis``              -> la nota de texto de siempre (se conserva lo ya escrito)
* ``croquis__dibujo``      -> la imagen del croquis, PNG o JPEG como ``data:`` URI
                             (el nombre es de cuando era un dibujo; cambiarlo obligaría
                             a migrar lo ya guardado)
* ``organigrama``          -> el texto de siempre
* ``organigrama__grafico`` -> las cajas y sus conexiones, en JSON

Lo que llega del navegador no se da por bueno: aquí se normaliza todo antes de
guardarlo, porque ese texto acabará dentro de una página que otros abren.

El organigrama se dibuja en el navegador (``static/emergencias/js/sci_organigrama.js``)
y también aquí, a SVG, para la hoja impresa, el periodo cerrado y el resumen de la
emergencia, que deben verse igual sin ejecutar nada. La geometría —tamaño de caja,
recorrido de las conexiones, corte del texto— está duplicada a propósito en los dos
sitios y las constantes de abajo son las mismas que lee el JavaScript.
"""

import base64
import binascii
import io
import json
import re

from django.utils.html import escape
from django.utils.safestring import mark_safe

# El «lienzo» del organigrama: las coordenadas que se guardan son las de este
# espacio, no píxeles de pantalla, de modo que el mismo dibujo se ve igual en el
# teléfono, en el escritorio y en el papel.
LIENZO_ANCHO = 760
LIENZO_ALTO = 700
CAJA_ANCHO = 150
CAJA_ALTO = 56
CARACTERES_POR_LINEA = 20
LINEAS_POR_CAJA = 3
MAX_CAJAS = 40
MAX_CONEXIONES = 80
MAX_TEXTO_CAJA = 60
MAX_JSON = 30000

# El croquis. Lo que el navegador manda es una imagen ya reducida y comprimida: el
# mapa capturado ocupa CROQUIS_ANCHO × CROQUIS_ALTO píxeles de pantalla a
# CROQUIS_DENSIDAD píxeles de imagen por cada uno (el doble, para que el papel salga
# nítido), y una foto subida se reduce a que su lado largo no pase de
# CROQUIS_LADO_MAX. El tope de caracteres deja el envío por debajo del límite de
# cuerpo de Django (2,5 MB) con el resto del formulario. El servidor no se fía de la
# reducción: ningún lado puede pasar de CROQUIS_LADO_ABSOLUTO, porque una imagen que
# declara decenas de miles de píxeles de lado ocupa gigabytes al abrirla.
CROQUIS_ANCHO = 760
CROQUIS_ALTO = 800
CROQUIS_DENSIDAD = 2
CROQUIS_LADO_MAX = 1600
CROQUIS_LADO_ABSOLUTO = 4096
MAX_CROQUIS = 1_500_000
# Cada tipo admitido: su prefijo ``data:`` y la firma con que empieza el archivo.
IMAGENES_CROQUIS = {
    "data:image/png;base64,": b"\x89PNG\r\n\x1a\n",
    "data:image/jpeg;base64,": b"\xff\xd8\xff",
}
PREFIJO_PNG = "data:image/png;base64,"


def clave_dibujo(nombre):
    return f"{nombre}__dibujo"


def clave_grafico(nombre):
    return f"{nombre}__grafico"


def imagen_de_croquis(valor):
    """``(tipo, bytes)`` si el valor es una imagen de croquis aceptable; si no, ``None``.

    Se comprueban el prefijo, el tamaño, la firma del archivo y las dimensiones, no
    solo el prefijo: el valor viaja en un campo de formulario y cualquiera puede
    mandar otra cosa. Las dimensiones se leen de la cabecera sin decodificar la
    imagen, de modo que comprobarlas no cuesta lo que se quiere evitar.
    """
    valor = str(valor or "").strip()
    if len(valor) > MAX_CROQUIS:
        return None
    for prefijo, firma in IMAGENES_CROQUIS.items():
        if not valor.startswith(prefijo):
            continue
        try:
            crudo = base64.b64decode(valor[len(prefijo):], validate=True)
        except (binascii.Error, ValueError):
            return None
        if not crudo.startswith(firma) or not _dimensiones_razonables(crudo):
            return None
        return prefijo[len("data:"):-len(";base64,")], crudo
    return None


def _dimensiones_razonables(crudo):
    try:
        from PIL import Image
        with Image.open(io.BytesIO(crudo)) as imagen:
            ancho, alto = imagen.size
    except Exception:  # no es una imagen, o está dañada
        return False
    return 0 < ancho <= CROQUIS_LADO_ABSOLUTO and 0 < alto <= CROQUIS_LADO_ABSOLUTO


def limpiar_croquis(valor):
    """Devuelve la imagen si es un PNG o un JPEG de tamaño razonable; si no, ``""``."""
    if imagen_de_croquis(valor) is None:
        return ""
    return str(valor).strip()


def _acotar(valor, minimo, maximo):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return minimo
    if numero != numero:  # NaN
        return minimo
    return int(round(max(minimo, min(maximo, numero))))


def limpiar_organigrama(texto):
    """Normaliza el JSON del editor: cajas dentro del lienzo y conexiones que existan.

    Devuelve el JSON compacto, o ``""`` si no queda ninguna caja. Descarta sin
    avisar lo que no encaje —cajas repetidas, conexiones a una caja que no existe,
    exceso de elementos—, porque es el resultado de un editor, no de una persona:
    una petición hecha a mano no debe poder guardar nada que el editor no produciría.
    """
    texto = str(texto or "").strip()
    if not texto or len(texto) > MAX_JSON:
        return ""
    try:
        crudo = json.loads(texto)
    except (TypeError, ValueError):
        return ""
    if not isinstance(crudo, dict):
        return ""

    cajas, ids = [], set()
    for caja in (crudo.get("nodos") or [])[:MAX_CAJAS]:
        if not isinstance(caja, dict):
            continue
        identificador = re.sub(r"[^A-Za-z0-9_-]", "", str(caja.get("id", "")))[:16]
        if not identificador or identificador in ids:
            continue
        ids.add(identificador)
        cajas.append({
            "id": identificador,
            "x": _acotar(caja.get("x"), 0, LIENZO_ANCHO - CAJA_ANCHO),
            "y": _acotar(caja.get("y"), 0, LIENZO_ALTO - CAJA_ALTO),
            "t": " ".join(str(caja.get("t", "")).split())[:MAX_TEXTO_CAJA],
        })
    if not cajas:
        return ""

    conexiones, vistas = [], set()
    for enlace in (crudo.get("enlaces") or [])[:MAX_CONEXIONES]:
        if not isinstance(enlace, dict):
            continue
        origen, destino = str(enlace.get("de", "")), str(enlace.get("a", ""))
        par = (origen, destino)
        if origen == destino or origen not in ids or destino not in ids or par in vistas:
            continue
        vistas.add(par)
        conexiones.append({"de": origen, "a": destino})
    return json.dumps({"nodos": cajas, "enlaces": conexiones},
                      separators=(",", ":"), ensure_ascii=False)


def _lineas(texto):
    """Parte el texto de una caja en líneas de ancho fijo, como lo hace el JS."""
    lineas, actual = [], ""
    for palabra in texto.split():
        while len(palabra) > CARACTERES_POR_LINEA:
            if actual:
                lineas.append(actual)
                actual = ""
            lineas.append(palabra[:CARACTERES_POR_LINEA])
            palabra = palabra[CARACTERES_POR_LINEA:]
        candidata = f"{actual} {palabra}".strip()
        if len(candidata) <= CARACTERES_POR_LINEA:
            actual = candidata
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    if len(lineas) > LINEAS_POR_CAJA:
        lineas = lineas[:LINEAS_POR_CAJA]
        lineas[-1] = lineas[-1][:CARACTERES_POR_LINEA - 1] + "…"
    return lineas


def puntos_de_conexion(origen, destino):
    """Los vértices de una conexión entre dos cajas, en ángulos rectos.

    De arriba abajo si una caja está por encima de la otra; de lado a lado si
    están a la misma altura. Es la misma regla que ``rutaDeConexion`` del JS. Se
    devuelven puntos y no una ruta SVG para que el PDF, que no habla SVG, dibuje
    exactamente el mismo trazo.
    """
    mitad_x_o, mitad_x_d = origen["x"] + CAJA_ANCHO / 2, destino["x"] + CAJA_ANCHO / 2
    if destino["y"] >= origen["y"] + CAJA_ALTO:
        y1, y2 = origen["y"] + CAJA_ALTO, destino["y"]
        medio = (y1 + y2) / 2
        return [(mitad_x_o, y1), (mitad_x_o, medio), (mitad_x_d, medio), (mitad_x_d, y2)]
    if origen["y"] >= destino["y"] + CAJA_ALTO:
        y1, y2 = origen["y"], destino["y"] + CAJA_ALTO
        medio = (y1 + y2) / 2
        return [(mitad_x_o, y1), (mitad_x_o, medio), (mitad_x_d, medio), (mitad_x_d, y2)]
    y1, y2 = origen["y"] + CAJA_ALTO / 2, destino["y"] + CAJA_ALTO / 2
    if destino["x"] >= origen["x"]:
        x1, x2 = origen["x"] + CAJA_ANCHO, destino["x"]
    else:
        x1, x2 = origen["x"], destino["x"] + CAJA_ANCHO
    medio = (x1 + x2) / 2
    return [(x1, y1), (medio, y1), (medio, y2), (x2, y2)]


def ruta_de_conexion(origen, destino):
    """``puntos_de_conexion`` como ruta SVG."""
    puntos = puntos_de_conexion(origen, destino)
    return "M" + "L".join(f"{x:g} {y:g}" for x, y in puntos)


def cargar_organigrama(texto):
    """El organigrama ya normalizado como ``{"nodos": [...], "enlaces": [...]}``, o ``None``."""
    limpio = limpiar_organigrama(texto)
    return json.loads(limpio) if limpio else None


def lineas_de_caja(texto):
    """Las líneas en que se parte el texto de una caja (lo usa también el PDF)."""
    return _lineas(texto)


def organigrama_svg(texto):
    """El organigrama como SVG, o ``""`` si no hay cajas.

    Todo texto del usuario pasa por ``escape``: el resultado se marca seguro para
    incrustarlo en la página, y por eso es lo único que se deja sin escapar.
    """
    grafico = cargar_organigrama(texto)
    if not grafico:
        return ""
    por_id = {caja["id"]: caja for caja in grafico["nodos"]}
    partes = [
        f'<svg class="sci-organigrama__svg" viewBox="0 0 {LIENZO_ANCHO} {LIENZO_ALTO}" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Organigrama del incidente" '
        'font-family="Arial, sans-serif">'
    ]
    for enlace in grafico["enlaces"]:
        ruta = ruta_de_conexion(por_id[enlace["de"]], por_id[enlace["a"]])
        partes.append(f'<path d="{ruta}" fill="none" stroke="#475569" stroke-width="2"/>')
    for caja in grafico["nodos"]:
        partes.append(
            f'<rect x="{caja["x"]}" y="{caja["y"]}" width="{CAJA_ANCHO}" height="{CAJA_ALTO}" '
            'rx="6" fill="#ffffff" stroke="#1f2d4a" stroke-width="2"/>'
        )
        lineas = _lineas(caja["t"])
        inicio = caja["y"] + CAJA_ALTO / 2 - (len(lineas) - 1) * 7.5 + 4.5
        for numero, linea in enumerate(lineas):
            partes.append(
                f'<text x="{caja["x"] + CAJA_ANCHO / 2:g}" y="{inicio + numero * 15:g}" '
                f'text-anchor="middle" font-size="12" fill="#0f172a">{escape(linea)}</text>'
            )
    partes.append("</svg>")
    return mark_safe("".join(partes))


def hay_organigrama(texto):
    return bool(limpiar_organigrama(texto))
