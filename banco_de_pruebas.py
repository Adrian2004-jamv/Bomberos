"""Banco de pruebas de carga del rastreo GPS y del mapa operativo.

Levanta un servidor real contra una base de pruebas desechable y mide las dos
rutas que se saturarían durante un simulacro:

* ``POST /emergencias/api/despliegues/<pk>/posiciones/`` — cada unidad que
  transmite escribe por aquí.
* ``GET /mapa/datos/`` — cada pestaña con el mapa abierto la pide, tanto al
  refrescar cada diez segundos como al reconectarse.

No toca la base de desarrollo: el corredor de pruebas crea y destruye la suya.

    python banco_de_pruebas.py [--unidades 20] [--posiciones 20] [--hilos 20]
"""

import argparse
import os
import sys
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import django

if "--produccion" in sys.argv:
    # DEBUG=False es la configuración real del despliegue: sin registro de
    # consultas en memoria y con las comprobaciones de desarrollo apagadas.
    os.environ["DJANGO_DEBUG"] = "False"
    os.environ.setdefault("DJANGO_SECRET_KEY", "banco-de-pruebas-no-usar-en-produccion")
    os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "127.0.0.1,testserver")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
# La capa en memoria evita depender de Redis para medir; el envío a la capa se
# ejecuta igual, de modo que su costo sí entra en la medición.
os.environ.setdefault("CHANNEL_LAYER_BACKEND", "memory")
django.setup()

from django.test.utils import get_runner, setup_test_environment  # noqa: E402
from django.conf import settings  # noqa: E402


def percentil(valores, fraccion):
    ordenados = sorted(valores)
    indice = min(int(len(ordenados) * fraccion), len(ordenados) - 1)
    return ordenados[indice]


def formatear(titulo, tiempos, total_segundos):
    if not tiempos:
        print(f"  {titulo}: sin respuestas")
        return
    print(f"  {titulo}")
    print(f"    peticiones      {len(tiempos)}")
    print(f"    duración total  {total_segundos:.2f} s")
    print(f"    throughput      {len(tiempos) / total_segundos:.1f} req/s")
    print(f"    latencia media  {statistics.mean(tiempos) * 1000:.0f} ms")
    print(f"    mediana         {statistics.median(tiempos) * 1000:.0f} ms")
    print(f"    p95             {percentil(tiempos, 0.95) * 1000:.0f} ms")
    print(f"    máxima          {max(tiempos) * 1000:.0f} ms")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unidades", type=int, default=20,
                        help="unidades desplegadas que transmiten a la vez")
    parser.add_argument("--posiciones", type=int, default=20,
                        help="posiciones que envía cada unidad")
    parser.add_argument("--hilos", type=int, default=20, help="peticiones simultáneas")
    parser.add_argument("--mapas", type=int, default=5,
                        help="pestañas con el mapa abierto pidiendo el GeoJSON")
    parser.add_argument("--produccion", action="store_true",
                        help="mide con DEBUG=False, como corre el despliegue")
    opciones = parser.parse_args()

    if not settings.DEBUG:
        # El banco habla HTTP plano; en el despliegue real hay un proxy que
        # termina TLS antes de que la petición llegue a la aplicación.
        settings.SECURE_SSL_REDIRECT = False
        settings.SESSION_COOKIE_SECURE = False
        settings.CSRF_COOKIE_SECURE = False
    print("Configuracion: DEBUG=" + str(settings.DEBUG))
    print()

    setup_test_environment()
    # setup_test_environment agrega «testserver» a ALLOWED_HOSTS, y al dejar de
    # estar vacía Django deja de aceptar 127.0.0.1 por ser modo de desarrollo.
    if "127.0.0.1" not in settings.ALLOWED_HOSTS:
        settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, "127.0.0.1"]
    corredor = get_runner(settings)(verbosity=0, interactive=False)
    configuracion = corredor.setup_databases()
    try:
        ejecutar(opciones)
    finally:
        corredor.teardown_databases(configuracion)


def ejecutar(opciones):
    import http.client
    import json as jsonlib

    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group
    from django.test.testcases import LiveServerThread
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from django.core.servers.basehttp import ThreadedWSGIServer

    class QuietHandler(StaticFilesHandler):
        """Sirve los estáticos como en desarrollo; aquí no se piden."""

    from django.contrib.sessions.backends.db import SessionStore

    from instituciones.models import Canton, CuerpoBomberos, Estacion
    from inventario.models import CategoriaRecurso, Recurso, TipoRecurso
    from emergencias.models import Emergencia, PosicionUnidad
    from emergencias.services import desplegar_unidad

    print("Preparando el escenario…")
    canton = Canton.objects.create(nombre="Latacunga", codigo="LAT-BP")
    cuerpo = CuerpoBomberos.objects.create(
        canton=canton, nombre="Bomberos Banco", sigla="CBB-BP",
        ruc="0596000000901", direccion="Centro",
    )
    estacion = Estacion.objects.create(
        cuerpo_bomberos=cuerpo, nombre="Central Banco", codigo="CB-BP",
        direccion="Centro", latitud="-0.930000", longitud="-78.610000",
    )
    categoria = CategoriaRecurso.objects.create(nombre="Vehículos", codigo="VEH-BP")
    tipo = TipoRecurso.objects.create(
        categoria=categoria, nombre="Autobomba", codigo="AUT-BP",
        es_unidad_desplegable=True,
    )
    usuario = get_user_model().objects.create_user(
        username="banco", cedula="0640000001", password="clave", estacion=estacion
    )
    usuario.groups.add(Group.objects.get(name="Responsable institucional"))

    emergencia = Emergencia.objects.create(
        codigo="BP-001", tipo_emergencia="Incendio estructural",
        prioridad=Emergencia.Prioridad.ALTA, estado=Emergencia.Estado.EN_ATENCION,
        direccion="Centro", latitud="-0.933333", longitud="-78.616667",
        estacion_responsable=estacion, registrado_por=usuario,
    )
    despliegues = []
    for indice in range(opciones.unidades):
        unidad = Recurso.objects.create(
            estacion=estacion, tipo=tipo,
            codigo_interno=f"AB-BP-{indice:03d}", nombre=f"Unidad {indice}",
        )
        despliegues.append(desplegar_unidad(emergencia, unidad, usuario))
    print(f"  {len(despliegues)} unidades desplegadas en una emergencia activa")

    sesion = SessionStore()
    sesion["_auth_user_id"] = str(usuario.pk)
    sesion["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    sesion["_auth_user_hash"] = usuario.get_session_auth_hash()
    sesion.create()

    # El servidor de pruebas atiende cada petición en su propio hilo, igual que
    # Daphne atiende varias a la vez en el sistema real.
    ThreadedWSGIServer.daemon_threads = True
    hilo = LiveServerThread("127.0.0.1", QuietHandler, connections_override={})
    hilo.daemon = True
    hilo.start()
    hilo.is_ready.wait()
    if hilo.error:
        raise hilo.error
    base = f"http://127.0.0.1:{hilo.port}"
    print(f"  servidor de pruebas en {base}\n")

    local = threading.local()

    def obtener_csrf():
        """El navegador recibe la ficha al abrir la página de transmisión."""
        enlace = http.client.HTTPConnection("127.0.0.1", hilo.port, timeout=30)
        enlace.request(
            "GET",
            f"/emergencias/despliegues/{despliegues[0].pk}/gps/",
            headers={"Cookie": f"sessionid={sesion.session_key}"},
        )
        respuesta = enlace.getresponse()
        respuesta.read()
        for clave, valor in respuesta.getheaders():
            if clave.lower() == "set-cookie" and "csrftoken=" in valor:
                enlace.close()
                return valor.split("csrftoken=", 1)[1].split(";", 1)[0]
        enlace.close()
        raise RuntimeError("La página de transmisión no entregó la ficha CSRF.")

    ficha = obtener_csrf()
    galleta = f"sessionid={sesion.session_key}; csrftoken={ficha}"

    def conexion():
        """Una conexión persistente por hilo, como la que mantiene un navegador."""
        if not hasattr(local, "http"):
            local.http = http.client.HTTPConnection("127.0.0.1", hilo.port, timeout=30)
        return local.http

    def pedir(metodo, ruta, cuerpo=None):
        cabeceras = {"Cookie": galleta, "Accept": "application/json",
                     "X-CSRFToken": ficha, "Referer": f"http://127.0.0.1:{hilo.port}/"}
        datos = None
        if cuerpo is not None:
            datos = jsonlib.dumps(cuerpo)
            cabeceras["Content-Type"] = "application/json"
        inicio = time.perf_counter()
        try:
            enlace = conexion()
            enlace.request(metodo, ruta, body=datos, headers=cabeceras)
            respuesta = enlace.getresponse()
            respuesta.read()
            return time.perf_counter() - inicio, respuesta.status
        except Exception as error:  # noqa: BLE001
            # Una conexión rota no se reutiliza: el siguiente intento la reabre.
            if hasattr(local, "http"):
                local.http.close()
                del local.http
            return time.perf_counter() - inicio, f"error: {type(error).__name__}"

    def enviar_posicion(par):
        despliegue, paso = par
        return pedir(
            "POST",
            f"/emergencias/api/despliegues/{despliegue.pk}/posiciones/",
            {
                "latitud": -0.93 - paso * 0.0001,
                "longitud": -78.61 + paso * 0.0001,
                "precision": 8.5,
                "velocidad": 12.4,
            },
        )

    def pedir_mapa(_):
        return pedir("GET", "/mapa/datos/")

    try:
        # --- 0. Una sola petición a la vez, como referencia ---------------
        print("0) Referencia en serie · una posición a la vez")
        sueltas = [enviar_posicion((despliegues[i % len(despliegues)], 900 + i))
                   for i in range(15)]
        en_serie = [tiempo for tiempo, codigo in sueltas if codigo == 201]
        if en_serie:
            print(f"    latencia media  {statistics.mean(en_serie) * 1000:.0f} ms")
            print(f"    mediana         {statistics.median(en_serie) * 1000:.0f} ms")
            print(f"    techo teórico   {1 / statistics.median(en_serie):.0f} req/s en un solo hilo")

        # --- 1. Ingesta de posiciones -------------------------------------
        trabajos = [(d, paso) for paso in range(opciones.posiciones) for d in despliegues]
        print(f"1) Ingesta GPS · {len(trabajos)} posiciones, {opciones.hilos} simultáneas")
        arranque = time.perf_counter()
        with ThreadPoolExecutor(max_workers=opciones.hilos) as pool:
            resultados = list(pool.map(enviar_posicion, trabajos))
        total = time.perf_counter() - arranque
        tiempos = [t for t, c in resultados if c == 201]
        fallos = [c for _, c in resultados if c != 201]
        formatear("POST posiciones", tiempos, total)
        print(f"    guardadas       {PosicionUnidad.objects.count()}")
        if fallos:
            print(f"    respuestas no 201: {len(fallos)} · {sorted(set(map(str, fallos)))}")

        # --- 2. El mapa con el recorrido ya cargado ------------------------

        # --- 1b. Barrido: cuanto aporta cada hilo adicional ----------------
        print()
        print("1b) Barrido de concurrencia, 60 posiciones por pasada")
        print("    hilos   throughput   mediana      p95")
        for hilos in (1, 2, 4, 8, 16):
            lote = [(despliegues[i % len(despliegues)], 500 + i) for i in range(60)]
            arranque = time.perf_counter()
            with ThreadPoolExecutor(max_workers=hilos) as pool:
                medidas = list(pool.map(enviar_posicion, lote))
            duracion = time.perf_counter() - arranque
            buenos = [x for x, c in medidas if c == 201]
            if buenos:
                print("    {:>5}   {:>8.1f}/s   {:>5.0f} ms   {:>5.0f} ms".format(
                    hilos, len(buenos) / duracion,
                    statistics.median(buenos) * 1000, percentil(buenos, 0.95) * 1000))
        print()
        solo = [pedir_mapa(0) for _ in range(8)]
        serie_mapa = [x for x, c in solo if c == 200]
        if serie_mapa:
            print("2) Mapa operativo: una pestana sola, mediana {:.0f} ms".format(
                statistics.median(serie_mapa) * 1000))
        print(f"\n2) Mapa operativo · {opciones.mapas} pestañas pidiendo el GeoJSON a la vez")
        arranque = time.perf_counter()
        with ThreadPoolExecutor(max_workers=opciones.mapas) as pool:
            resultados = list(pool.map(pedir_mapa, range(opciones.mapas * 4)))
        total = time.perf_counter() - arranque
        tiempos = [t for t, c in resultados if c == 200]
        formatear("GET /mapa/datos/", tiempos, total)

        # --- 3. Consultas por petición del mapa ----------------------------
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from mapas.services import construir_geojson

        with CaptureQueriesContext(connection) as capturadas:
            geojson = construir_geojson(usuario, {})
        print("\n3) Costo del GeoJSON")
        print(f"    consultas SQL   {len(capturadas)}")
        print(f"    elementos       {len(geojson['features'])}")
        print(f"    posiciones en base {PosicionUnidad.objects.count()}")
    finally:
        hilo.terminate()


if __name__ == "__main__":
    sys.exit(main())
