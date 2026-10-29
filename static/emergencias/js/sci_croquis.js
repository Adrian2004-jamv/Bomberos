/* Croquis del SCI-201: una foto o el mapa del lugar.
 *
 * Es un componente, no código de un formulario: se activa solo en cualquier
 * elemento con ``data-sci-croquis`` y no conoce el formulario que lo contiene.
 * El HTML lo da la plantilla ``fragmentos/croquis_editor.html``:
 *
 *   <div data-sci-croquis data-lat="-0.934600" data-lon="-78.615500" data-codigo="RE-24102026-001">
 *     <input type="hidden" name="croquis__dibujo" value="data:image/jpeg;base64,...">
 *   </div>
 *
 * Tuvo antes un lienzo para dibujar a mano. Los bomberos lo descartaron: en la
 * escena es más rápido fotografiar un plano o pedir el mapa que dibujarlo con el
 * dedo. Ahora ofrece dos maneras de poner la imagen, y las dos acaban igual, en un
 * JPEG dentro del campo oculto:
 *
 *   - «Subir imagen»: una foto de la galería o de la cámara del dispositivo.
 *   - «Capturar mapa»: el mapa del lugar, en las coordenadas de la emergencia.
 *
 * La imagen viaja como un campo más del formulario (``data:`` URI), de modo que el
 * envío sin conexión de la PWA —que serializa el formulario entero— la guarda en la
 * cola igual que cualquier otro campo. No usa librerías: la captura del mapa son
 * unas decenas de líneas que componen los mosaicos en un canvas, y una biblioteca
 * de mapas obligaría a descargar más de lo que esta pantalla necesita.
 *
 * Sobre la calidad para imprimir, que es lo que importa: los mosaicos de un mapa
 * tienen 256 px y una pantalla los estira. Aquí se piden los del nivel siguiente
 * —cuatro mosaicos donde la pantalla muestra uno— y se compone un lienzo del doble
 * de píxeles que el mapa de pantalla (1520 × 1600), de modo que cada píxel del papel
 * es un píxel real del mapa y no uno inventado. Lo que se dibuja encima —el
 * marcador, el norte, la escala y la atribución— se dibuja después, con vectores, ya
 * a esa resolución: sale nítido en vez de borroso.
 */
(function () {
    "use strict";

    // Duplicadas con emergencias/graficos_sci.py: un test comprueba que coinciden.
    var ANCHO = 760;
    var ALTO = 800;
    var DENSIDAD = 2;
    var LADO_MAX = 1600;
    // Por debajo del tope del servidor (MAX_CROQUIS) para que el envío quepa con el
    // resto del formulario.
    var OBJETIVO_CARACTERES = 1300000;

    // El mismo proveedor y la misma dirección que ``static/mapas/js/fondo.js``, que
    // es el fondo de los mapas del sistema: un test comprueba que no se separan. El
    // servicio permite leer los mosaicos desde otro origen, que es lo que deja
    // convertir el lienzo en imagen sin «contaminarlo».
    var MOSAICOS = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}";
    var ATRIBUCION = "Mosaicos © Esri · datos de OpenStreetMap y otros";
    var LADO_MOSAICO = 256;
    var ZOOM_MAXIMO = 19;           // más allá, el proveedor responde «Map data not yet available»
    var SIMULTANEOS = 8;            // mosaicos que se piden a la vez
    var PLAZO_MOSAICO = 15000;      // ms por mosaico, y un reintento
    var FALLOS_ADMITIDOS = 2;       // más huecos que esto y el mapa no sirve como croquis

    // Alcance: el nivel de zoom del mapa de pantalla (760 × 800 px) y lo que abarca.
    var ALCANCES = [
        [16, "Amplio", "≈ 1,8 km"],
        [17, "Medio", "≈ 900 m"],
        [18, "Cercano", "≈ 450 m"]
    ];
    var ALCANCE_INICIAL = 17;

    function el(etiqueta, atributos, hijos) {
        var nodo = document.createElement(etiqueta);
        Object.keys(atributos || {}).forEach(function (clave) {
            if (clave === "texto") { nodo.textContent = atributos[clave]; }
            else { nodo.setAttribute(clave, atributos[clave]); }
        });
        (hijos || []).forEach(function (hijo) { nodo.appendChild(hijo); });
        return nodo;
    }

    function boton(texto, icono, atributos) {
        var b = el("button", Object.assign({ type: "button", "class": "sci-grafico__boton" }, atributos));
        if (icono) { b.appendChild(el("i", { "class": "ti " + icono, "aria-hidden": "true" })); }
        b.appendChild(el("span", { texto: texto }));
        return b;
    }

    function lienzoDe(ancho, alto) {
        var c = document.createElement("canvas");
        c.width = ancho;
        c.height = alto;
        return c;
    }

    // --- geometría del mapa ------------------------------------------------------

    // Posición de un punto en el «mundo» de píxeles de un nivel de zoom (proyección
    // Web Mercator, la de todos los mapas de mosaicos).
    function aPixeles(lat, lon, zoom) {
        var mundo = LADO_MOSAICO * Math.pow(2, zoom);
        var seno = Math.sin(lat * Math.PI / 180);
        return {
            x: (lon + 180) / 360 * mundo,
            y: (0.5 - Math.log((1 + seno) / (1 - seno)) / (4 * Math.PI)) * mundo
        };
    }

    function metrosPorPixel(lat, zoom) {
        return 156543.03392 * Math.cos(lat * Math.PI / 180) / Math.pow(2, zoom);
    }

    function cargarImagen(url, plazo) {
        return new Promise(function (listo, fallo) {
            var imagen = new Image();
            imagen.crossOrigin = "anonymous";
            var temporizador = setTimeout(function () {
                imagen.onload = imagen.onerror = null;
                fallo(new Error("tiempo agotado"));
            }, plazo);
            imagen.onload = function () { clearTimeout(temporizador); listo(imagen); };
            imagen.onerror = function () { clearTimeout(temporizador); fallo(new Error("no se pudo leer")); };
            imagen.src = url;
        });
    }

    async function cargarMosaico(z, x, y) {
        var url = MOSAICOS.replace("{z}", z).replace("{y}", y).replace("{x}", x);
        for (var intento = 0; intento < 2; intento++) {
            try { return await cargarImagen(url, PLAZO_MOSAICO); } catch (error) { /* se reintenta una vez */ }
        }
        return null;
    }

    // --- lo que se dibuja encima del mapa -----------------------------------------

    function cajaConTexto(ctx, texto, x, y, k, opciones) {
        // ``x``, ``y``: esquina superior izquierda de la caja.
        var relleno = 5 * k;
        ctx.font = opciones.fuente;
        var ancho = ctx.measureText(texto).width + relleno * 2;
        var alto = opciones.alto;
        ctx.fillStyle = opciones.fondo;
        ctx.fillRect(x, y, ancho, alto);
        if (opciones.borde) {
            ctx.strokeStyle = opciones.borde;
            ctx.lineWidth = 1.5 * k;
            ctx.strokeRect(x, y, ancho, alto);
        }
        ctx.fillStyle = opciones.color;
        ctx.textBaseline = "middle";
        ctx.textAlign = "left";
        ctx.fillText(texto, x + relleno, y + alto / 2);
        return ancho;
    }

    function dibujarMarcador(ctx, x, y, k, etiqueta) {
        var radio = 13 * k;
        var alto = 40 * k;     // de la punta al centro de la cabeza
        ctx.save();
        ctx.translate(x, y);
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.bezierCurveTo(-radio * 0.2, -alto * 0.5, -radio, -alto + radio * 1.2, -radio, -alto);
        ctx.arc(0, -alto, radio, Math.PI, 0);
        ctx.bezierCurveTo(radio, -alto + radio * 1.2, radio * 0.2, -alto * 0.5, 0, 0);
        ctx.closePath();
        ctx.fillStyle = "#c70012";
        ctx.fill();
        ctx.lineWidth = 2.5 * k;
        ctx.strokeStyle = "#ffffff";
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(0, -alto, radio * 0.42, 0, Math.PI * 2);
        ctx.fillStyle = "#ffffff";
        ctx.fill();
        ctx.restore();
        if (etiqueta) {
            cajaConTexto(ctx, etiqueta, x + radio + 6 * k, y - alto - 11 * k, k, {
                fuente: "700 " + (12 * k) + "px Arial, sans-serif", alto: 22 * k,
                fondo: "rgba(255,255,255,0.95)", borde: "#1f2d4a", color: "#0f172a"
            });
        }
    }

    function dibujarNorte(ctx, ancho, k) {
        var cx = ancho - 40 * k;
        var cy = 58 * k;
        ctx.beginPath();
        ctx.arc(cx, cy, 24 * k, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255,255,255,0.92)";
        ctx.fill();
        ctx.lineWidth = 1.5 * k;
        ctx.strokeStyle = "#475569";
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(cx, cy - 17 * k);
        ctx.lineTo(cx - 9 * k, cy + 12 * k);
        ctx.lineTo(cx, cy + 5 * k);
        ctx.lineTo(cx + 9 * k, cy + 12 * k);
        ctx.closePath();
        ctx.fillStyle = "#0f172a";
        ctx.fill();
        ctx.font = "800 " + (13 * k) + "px Arial, sans-serif";
        ctx.fillStyle = "#0f172a";
        ctx.textAlign = "center";
        ctx.textBaseline = "bottom";
        ctx.fillText("N", cx, cy - 27 * k);
    }

    function dibujarEscala(ctx, x, y, k, metrosPorPixelDeImagen) {
        var candidatas = [10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000];
        var metros = candidatas[0];
        candidatas.forEach(function (m) {
            if (m / metrosPorPixelDeImagen <= 200 * k) { metros = m; }
        });
        var largo = metros / metrosPorPixelDeImagen;
        var etiqueta = metros >= 1000 ? (metros / 1000) + " km" : metros + " m";
        ctx.fillStyle = "rgba(255,255,255,0.92)";
        ctx.fillRect(x, y - 34 * k, largo + 20 * k, 34 * k);
        ctx.strokeStyle = "#0f172a";
        ctx.lineWidth = 3 * k;
        ctx.beginPath();
        ctx.moveTo(x + 10 * k, y - 10 * k - 6 * k);
        ctx.lineTo(x + 10 * k, y - 10 * k);
        ctx.lineTo(x + 10 * k + largo, y - 10 * k);
        ctx.lineTo(x + 10 * k + largo, y - 10 * k - 6 * k);
        ctx.stroke();
        ctx.font = "700 " + (11 * k) + "px Arial, sans-serif";
        ctx.fillStyle = "#0f172a";
        ctx.textAlign = "left";
        ctx.textBaseline = "alphabetic";
        ctx.fillText(etiqueta, x + 10 * k, y - 20 * k);
    }

    function fechaCorta(fecha) {
        function dos(n) { return (n < 10 ? "0" : "") + n; }
        return dos(fecha.getDate()) + "/" + dos(fecha.getMonth() + 1) + "/" + fecha.getFullYear()
            + " " + dos(fecha.getHours()) + ":" + dos(fecha.getMinutes());
    }

    function dibujarPie(ctx, ancho, alto, k, lat, lon) {
        var franja = 24 * k;
        ctx.fillStyle = "rgba(255,255,255,0.92)";
        ctx.fillRect(0, alto - franja, ancho, franja);
        ctx.font = "400 " + (10 * k) + "px Arial, sans-serif";
        ctx.fillStyle = "#1e293b";
        ctx.textBaseline = "middle";
        ctx.textAlign = "left";
        ctx.fillText("Lat " + lat.toFixed(5) + " · Lon " + lon.toFixed(5) + " · capturado " + fechaCorta(new Date()),
            8 * k, alto - franja / 2);
        // La atribución es obligatoria en cualquier proveedor de mosaicos, y una imagen
        // que sale impresa y se archiva en un expediente debe llevarla dentro.
        ctx.textAlign = "right";
        ctx.fillText(ATRIBUCION, ancho - 8 * k, alto - franja / 2);
    }

    // --- captura del mapa -----------------------------------------------------------

    // Compone el mapa del lugar en un canvas. ``progreso(hechos, total)`` informa de
    // cuántos mosaicos van. Falla si no se pudo descargar lo suficiente.
    async function capturarMapa(opciones) {
        var zoom = opciones.zoom;
        var zoomMosaicos = Math.min(zoom + Math.log(DENSIDAD) / Math.LN2, ZOOM_MAXIMO);
        var factor = Math.pow(2, zoomMosaicos - zoom);          // píxeles de imagen por píxel de pantalla
        var ancho = Math.round(ANCHO * factor);
        var alto = Math.round(ALTO * factor);
        var centro = aPixeles(opciones.lat, opciones.lon, zoomMosaicos);
        var izquierda = centro.x - ancho / 2;
        var arriba = centro.y - alto / 2;
        var indiceMaximo = Math.pow(2, zoomMosaicos) - 1;

        var x0 = Math.floor(izquierda / LADO_MOSAICO);
        var x1 = Math.floor((izquierda + ancho - 1) / LADO_MOSAICO);
        var y0 = Math.max(0, Math.floor(arriba / LADO_MOSAICO));
        var y1 = Math.min(indiceMaximo, Math.floor((arriba + alto - 1) / LADO_MOSAICO));
        var lista = [];
        for (var y = y0; y <= y1; y++) {
            for (var x = x0; x <= x1; x++) { lista.push({ x: x, y: y }); }
        }

        var lienzo = lienzoDe(ancho, alto);
        var ctx = lienzo.getContext("2d");
        ctx.fillStyle = "#e5e7eb";
        ctx.fillRect(0, 0, ancho, alto);

        var siguiente = 0;
        var hechos = 0;
        var fallos = 0;
        var vuelta = indiceMaximo + 1;
        async function trabajador() {
            while (siguiente < lista.length) {
                var pieza = lista[siguiente++];
                var imagen = await cargarMosaico(zoomMosaicos, ((pieza.x % vuelta) + vuelta) % vuelta, pieza.y);
                if (imagen) {
                    ctx.drawImage(imagen, Math.round(pieza.x * LADO_MOSAICO - izquierda),
                        Math.round(pieza.y * LADO_MOSAICO - arriba));
                } else {
                    fallos++;
                }
                hechos++;
                if (opciones.progreso) { opciones.progreso(hechos, lista.length); }
            }
        }
        var trabajadores = [];
        for (var i = 0; i < Math.min(SIMULTANEOS, lista.length); i++) { trabajadores.push(trabajador()); }
        await Promise.all(trabajadores);
        if (fallos > FALLOS_ADMITIDOS) { throw new Error("mosaicos"); }

        ctx.imageSmoothingQuality = "high";
        var k = factor;
        dibujarMarcador(ctx, ancho / 2, alto / 2, k, opciones.codigo);
        dibujarNorte(ctx, ancho, k);
        dibujarEscala(ctx, 10 * k, alto - 24 * k - 8 * k, k, metrosPorPixel(opciones.lat, zoomMosaicos));
        dibujarPie(ctx, ancho, alto, k, opciones.lat, opciones.lon);
        return lienzo;
    }

    // --- foto subida ----------------------------------------------------------------

    function cargarArchivo(archivo) {
        var direccion = URL.createObjectURL(archivo);
        return cargarImagen(direccion, 30000).then(function (imagen) {
            URL.revokeObjectURL(direccion);
            return imagen;
        }, function (error) {
            URL.revokeObjectURL(direccion);
            throw error;
        });
    }

    // El navegador aplica la orientación de la foto (EXIF) al dibujarla, de modo que
    // una foto tomada con el teléfono de lado no sale girada.
    async function lienzoDeArchivo(archivo) {
        var imagen = await cargarArchivo(archivo);
        var ancho = imagen.naturalWidth;
        var alto = imagen.naturalHeight;
        var escala = Math.min(1, LADO_MAX / Math.max(ancho, alto));
        var lienzo = lienzoDe(Math.max(1, Math.round(ancho * escala)), Math.max(1, Math.round(alto * escala)));
        var ctx = lienzo.getContext("2d");
        ctx.fillStyle = "#ffffff";       // un PNG transparente no debe salir negro en el JPEG
        ctx.fillRect(0, 0, lienzo.width, lienzo.height);
        ctx.imageSmoothingQuality = "high";
        ctx.drawImage(imagen, 0, 0, lienzo.width, lienzo.height);
        return lienzo;
    }

    // JPEG con la mejor calidad que quepa bajo el tope. Una foto muy detallada puede no
    // caber ni a calidad baja: entonces se reduce el tamaño y se vuelve a intentar.
    function comprimir(lienzo) {
        var calidad = 0.92;
        var url = "";
        for (var vuelta = 0; vuelta < 14; vuelta++) {
            url = lienzo.toDataURL("image/jpeg", calidad);
            if (url.length <= OBJETIVO_CARACTERES) { return url; }
            calidad -= 0.07;
            if (calidad < 0.55) {
                var menor = lienzoDe(Math.round(lienzo.width * 0.85), Math.round(lienzo.height * 0.85));
                menor.getContext("2d").drawImage(lienzo, 0, 0, menor.width, menor.height);
                lienzo = menor;
                calidad = 0.85;
            }
        }
        return url;
    }

    // --- el componente ----------------------------------------------------------------

    function iniciar(raiz) {
        if (raiz.dataset.listo) { return; }
        raiz.dataset.listo = "1";
        var campo = raiz.querySelector("input[type=hidden]");
        if (!campo) { return; }
        var lat = parseFloat(raiz.dataset.lat);
        var lon = parseFloat(raiz.dataset.lon);
        var hayCoordenadas = isFinite(lat) && isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180;
        var codigo = raiz.dataset.codigo || "";
        var alcance = ALCANCE_INICIAL;
        var ocupado = false;

        var archivo = el("input", { type: "file", accept: "image/*", "class": "sci-croquis__archivo", hidden: "hidden", "aria-label": "Elegir una imagen para el croquis" });
        var botonSubir = boton("Subir imagen", "ti-photo-plus", { title: "Una foto de la galería o de la cámara, o un plano" });
        var botonMapa = boton("Capturar mapa", "ti-map-pin", { title: "El mapa del lugar de la emergencia" });
        var botonQuitar = boton("Quitar", "ti-trash");
        var chips = ALCANCES.map(function (a) {
            var chip = boton(a[1] + " · " + a[2], "", { "class": "sci-grafico__boton sci-grafico__boton--chip", "aria-pressed": a[0] === alcance ? "true" : "false" });
            chip.dataset.alcance = a[0];
            return chip;
        });
        var grupoAlcance = el("div", { "class": "sci-grafico__grupo", role: "group", "aria-label": "Alcance del mapa" }, chips);

        var barra = el("div", { "class": "sci-grafico__barra" }, [
            el("div", { "class": "sci-grafico__grupo" }, [botonSubir, botonMapa]),
            grupoAlcance,
            el("div", { "class": "sci-grafico__grupo" }, [botonQuitar])
        ]);
        var vista = el("img", { "class": "sci-croquis__vista", alt: "Croquis del incidente" });
        var vacio = el("p", { "class": "sci-croquis__vacio", texto: "Aún no hay croquis. Suba una foto o un plano, o capture el mapa del lugar." });
        var marco = el("div", { "class": "sci-croquis__marco" }, [vista, vacio]);
        var mensaje = el("p", { "class": "sci-grafico__ayuda sci-croquis__estado", role: "status", "aria-live": "polite" });
        raiz.appendChild(archivo);
        raiz.appendChild(barra);
        raiz.appendChild(marco);
        raiz.appendChild(mensaje);

        function decir(texto, error) {
            mensaje.textContent = texto || "";
            mensaje.classList.toggle("sci-croquis__estado--error", Boolean(error));
        }

        function mostrar() {
            var hay = Boolean(campo.value);
            vista.hidden = !hay;
            vacio.hidden = hay;
            botonQuitar.hidden = !hay;
            if (hay) { vista.src = campo.value; } else { vista.removeAttribute("src"); }
        }

        function ponerImagen(url) {
            campo.value = url;
            campo.dispatchEvent(new Event("change", { bubbles: true }));
            mostrar();
        }

        function bloquear(si) {
            ocupado = si;
            [botonSubir, botonMapa, botonQuitar].concat(chips).forEach(function (b) { b.disabled = si; });
            if (!si && !hayCoordenadas) { botonMapa.disabled = true; }
        }

        // Reemplazar una imagen que ya está pide una segunda pulsación en vez de abrir un
        // cuadro de confirmación: una foto no siempre se puede volver a tomar.
        var pendiente = null;
        function confirmarReemplazo(b, textoOriginal, accion) {
            if (!campo.value || b.dataset.confirmar === "1") {
                olvidar();
                accion();
                return;
            }
            olvidar();
            b.dataset.confirmar = "1";
            b.querySelector("span").textContent = "¿Reemplazar? Pulse otra vez";
            pendiente = { boton: b, texto: textoOriginal, plazo: setTimeout(olvidar, 3500) };
        }
        function olvidar() {
            if (!pendiente) { return; }
            clearTimeout(pendiente.plazo);
            pendiente.boton.dataset.confirmar = "";
            pendiente.boton.querySelector("span").textContent = pendiente.texto;
            pendiente = null;
        }

        botonSubir.addEventListener("click", function () {
            confirmarReemplazo(botonSubir, "Subir imagen", function () { archivo.click(); });
        });

        archivo.addEventListener("change", async function () {
            var elegido = archivo.files && archivo.files[0];
            archivo.value = "";
            if (!elegido) { return; }
            if (elegido.size > 40 * 1024 * 1024) {
                decir("Esa imagen pesa demasiado. Elija una de menos de 40 MB.", true);
                return;
            }
            bloquear(true);
            decir("Preparando la imagen…");
            try {
                ponerImagen(comprimir(await lienzoDeArchivo(elegido)));
                decir("Imagen lista. Se guarda con el formulario.");
            } catch (error) {
                decir("No se pudo leer esa imagen. Use una foto en formato JPG o PNG.", true);
            }
            bloquear(false);
        });

        chips.forEach(function (chip) {
            chip.addEventListener("click", function () {
                alcance = parseInt(chip.dataset.alcance, 10);
                chips.forEach(function (c) { c.setAttribute("aria-pressed", c === chip ? "true" : "false"); });
            });
        });

        async function capturar() {
            if (!hayCoordenadas) { return; }
            if (navigator.onLine === false) {
                decir("Sin conexión: el mapa se descarga de internet. Suba una foto o un plano, o vuelva a intentarlo con señal.", true);
                return;
            }
            bloquear(true);
            decir("Descargando el mapa…");
            try {
                var lienzo = await capturarMapa({
                    lat: lat, lon: lon, zoom: alcance, codigo: codigo,
                    progreso: function (hechos, total) { decir("Descargando el mapa… " + hechos + " de " + total); }
                });
                ponerImagen(comprimir(lienzo));
                decir("Mapa capturado. Se guarda con el formulario.");
            } catch (error) {
                decir("No se pudo descargar el mapa. Revise la señal e intente otra vez, o suba una foto.", true);
            }
            bloquear(false);
        }
        botonMapa.addEventListener("click", function () {
            confirmarReemplazo(botonMapa, "Capturar mapa", capturar);
        });

        // «Quitar» también pide una segunda pulsación.
        botonQuitar.addEventListener("click", function () {
            if (botonQuitar.dataset.confirmar !== "1") {
                olvidar();
                botonQuitar.dataset.confirmar = "1";
                botonQuitar.querySelector("span").textContent = "¿Seguro? Pulse otra vez";
                pendiente = { boton: botonQuitar, texto: "Quitar", plazo: setTimeout(olvidar, 3500) };
                return;
            }
            olvidar();
            ponerImagen("");
            decir("Croquis quitado.");
        });

        if (!hayCoordenadas) {
            botonMapa.disabled = true;
            grupoAlcance.hidden = true;
            decir("Esta emergencia no tiene coordenadas registradas, así que no se puede capturar el mapa. Suba una foto o un plano.");
        }
        mostrar();
    }

    function iniciarTodos(contexto) {
        (contexto || document).querySelectorAll("[data-sci-croquis]").forEach(iniciar);
    }
    window.SciGraficos = window.SciGraficos || {};
    window.SciGraficos.croquis = iniciarTodos;
    window.SciGraficos.capturarMapa = capturarMapa;
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () { iniciarTodos(); });
    } else {
        iniciarTodos();
    }
})();
