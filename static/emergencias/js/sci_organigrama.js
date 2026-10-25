/* Editor de organigrama (arrastrar y soltar) para los formularios SCI.
 *
 * Como el croquis, es un componente autónomo: se activa en cualquier elemento con
 * ``data-sci-organigrama`` y guarda su resultado en el campo oculto que lleva
 * dentro, como JSON:
 *
 *   {"nodos":[{"id":"a1","x":300,"y":20,"t":"Comandante del Incidente"}],
 *    "enlaces":[{"de":"a1","a":"b2"}]}
 *
 * Está escrito sin librerías (jsPlumb, Interact.js, React Flow) por dos razones: la
 * aplicación es una PWA que debe abrirse sin red y sin depender de una CDN, y lo
 * que se necesita —mover cajas y unirlas con líneas— cabe en trescientas líneas.
 *
 * Las coordenadas son las de un lienzo fijo de 760 × 700 (``viewBox``), no píxeles,
 * y las mismas constantes y la misma regla de trazado viven en
 * ``emergencias/graficos_sci.py``, que dibuja el organigrama para la hoja impresa.
 * Si se cambia una cifra aquí hay que cambiarla allí.
 */
(function () {
    "use strict";

    var NS = "http://www.w3.org/2000/svg";
    var ANCHO = 760, ALTO = 700;
    var CAJA_ANCHO = 150, CAJA_ALTO = 56;
    var CARACTERES = 20, LINEAS = 3, MAX_TEXTO = 60, MAX_CAJAS = 40;

    var PUESTOS = [
        "Comandante del Incidente", "Oficial de Seguridad", "Oficial de Información Pública",
        "Oficial de Enlace", "Sección de Operaciones", "Sección de Planificación",
        "Sección de Logística", "Sección de Administración y Finanzas"
    ];

    // La estructura mínima del SCI: el Comandante, su staff y las cuatro secciones.
    // El staff va a los lados del Comandante y no en una fila intermedia: las líneas
    // hacia las secciones bajan por el centro y atravesarían esas cajas.
    function estructuraBasica() {
        var cajas = [
            ["ci", 305, 20, "Comandante del Incidente"],
            ["seg", 60, 20, "Oficial de Seguridad"],
            ["pio", 550, 20, "Oficial de Información Pública"],
            ["enl", 550, 100, "Oficial de Enlace"],
            ["ops", 20, 300, "Sección de Operaciones"],
            ["pla", 215, 300, "Sección de Planificación"],
            ["log", 410, 300, "Sección de Logística"],
            ["adm", 590, 300, "Sección de Administración y Finanzas"]
        ];
        var nodos = cajas.map(function (c) { return { id: c[0], x: c[1], y: c[2], t: c[3] }; });
        var enlaces = ["seg", "pio", "enl", "ops", "pla", "log", "adm"].map(function (a) { return { de: "ci", a: a }; });
        return { nodos: nodos, enlaces: enlaces };
    }

    function svg(etiqueta, atributos) {
        var nodo = document.createElementNS(NS, etiqueta);
        Object.keys(atributos || {}).forEach(function (k) { nodo.setAttribute(k, atributos[k]); });
        return nodo;
    }
    function el(etiqueta, atributos, hijos) {
        var nodo = document.createElement(etiqueta);
        Object.keys(atributos || {}).forEach(function (k) {
            if (k === "texto") { nodo.textContent = atributos[k]; } else { nodo.setAttribute(k, atributos[k]); }
        });
        (hijos || []).forEach(function (h) { nodo.appendChild(h); });
        return nodo;
    }
    function boton(texto, icono, atributos) {
        var b = el("button", Object.assign({ type: "button", "class": "sci-grafico__boton" }, atributos));
        if (icono) { b.appendChild(el("i", { "class": "ti " + icono, "aria-hidden": "true" })); }
        b.appendChild(el("span", { texto: texto }));
        return b;
    }

    // El mismo corte de texto que ``_lineas`` de graficos_sci.py.
    function lineasDe(texto) {
        var lineas = [], actual = "";
        texto.split(/\s+/).filter(Boolean).forEach(function (palabra) {
            while (palabra.length > CARACTERES) {
                if (actual) { lineas.push(actual); actual = ""; }
                lineas.push(palabra.slice(0, CARACTERES));
                palabra = palabra.slice(CARACTERES);
            }
            var candidata = (actual + " " + palabra).trim();
            if (candidata.length <= CARACTERES) { actual = candidata; }
            else { lineas.push(actual); actual = palabra; }
        });
        if (actual) { lineas.push(actual); }
        if (lineas.length > LINEAS) {
            lineas = lineas.slice(0, LINEAS);
            lineas[LINEAS - 1] = lineas[LINEAS - 1].slice(0, CARACTERES - 1) + "…";
        }
        return lineas;
    }

    // La misma regla que ``ruta_de_conexion`` de graficos_sci.py.
    function rutaDeConexion(o, d) {
        var xo = o.x + CAJA_ANCHO / 2, xd = d.x + CAJA_ANCHO / 2, y1, y2, medio;
        if (d.y >= o.y + CAJA_ALTO) {
            y1 = o.y + CAJA_ALTO; y2 = d.y; medio = (y1 + y2) / 2;
            return "M" + xo + " " + y1 + "V" + medio + "H" + xd + "V" + y2;
        }
        if (o.y >= d.y + CAJA_ALTO) {
            y1 = o.y; y2 = d.y + CAJA_ALTO; medio = (y1 + y2) / 2;
            return "M" + xo + " " + y1 + "V" + medio + "H" + xd + "V" + y2;
        }
        y1 = o.y + CAJA_ALTO / 2; y2 = d.y + CAJA_ALTO / 2;
        var x1, x2;
        if (d.x >= o.x) { x1 = o.x + CAJA_ANCHO; x2 = d.x; } else { x1 = o.x; x2 = d.x + CAJA_ANCHO; }
        medio = (x1 + x2) / 2;
        return "M" + x1 + " " + y1 + "H" + medio + "V" + y2 + "H" + x2;
    }

    function acotar(v, min, max) { return Math.max(min, Math.min(max, v)); }
    function identificador() { return "n" + Math.random().toString(36).slice(2, 8); }

    function iniciar(raiz) {
        if (raiz.dataset.listo) { return; }
        raiz.dataset.listo = "1";
        var campo = raiz.querySelector("input[type=hidden]");
        if (!campo) { return; }

        var cajas = [], conexiones = [];
        try {
            var guardado = campo.value ? JSON.parse(campo.value) : null;
            if (guardado && Array.isArray(guardado.nodos)) {
                cajas = guardado.nodos; conexiones = Array.isArray(guardado.enlaces) ? guardado.enlaces : [];
            }
        } catch (e) { cajas = []; conexiones = []; }

        var seleccion = null;     // {tipo:"caja"|"conexion", id | de/a}
        var conectandoDesde = null;
        var arrastre = null;

        // --- estructura de la interfaz ---------------------------------------------
        var chips = PUESTOS.map(function (puesto) {
            return boton(puesto, "ti-plus", { "class": "sci-grafico__boton sci-grafico__boton--chip", "data-puesto": puesto });
        });
        var botonOtra = boton("Otra caja", "ti-square-plus", { "data-accion": "otra" });
        var botonBasica = boton("Estructura básica", "ti-sitemap", { "data-accion": "basica" });
        var botonLimpiar = boton("Limpiar", "ti-trash", { "data-accion": "limpiar" });

        var barra = el("div", { "class": "sci-grafico__barra sci-grafico__barra--puestos", role: "toolbar", "aria-label": "Agregar cajas al organigrama" }, [
            el("div", { "class": "sci-grafico__grupo", role: "group", "aria-label": "Puestos del SCI" }, chips),
            el("div", { "class": "sci-grafico__grupo", role: "group", "aria-label": "Acciones" }, [botonOtra, botonBasica, botonLimpiar])
        ]);

        var lienzo = svg("svg", {
            "class": "sci-organigrama__lienzo", viewBox: "0 0 " + ANCHO + " " + ALTO, role: "group",
            "aria-label": "Lienzo del organigrama. Arrastre las cajas para moverlas."
        });

        var entradaTexto = el("input", { type: "text", maxlength: MAX_TEXTO, "class": "sci-organigrama__texto", id: "org-texto-" + Math.random().toString(36).slice(2, 7) });
        var etiquetaTexto = el("label", { "for": entradaTexto.id, texto: "Texto de la caja" });
        var botonConectar = boton("Conectar con otra caja", "ti-line", { "data-accion": "conectar" });
        var botonQuitarCaja = boton("Eliminar caja", "ti-trash", { "data-accion": "quitar-caja" });
        var botonQuitarConexion = boton("Eliminar conexión", "ti-unlink", { "data-accion": "quitar-conexion" });
        var mensaje = el("p", { "class": "sci-organigrama__mensaje", "aria-live": "polite" });
        var panel = el("div", { "class": "sci-organigrama__panel" }, [
            el("div", { "class": "sci-organigrama__campo" }, [etiquetaTexto, entradaTexto]),
            el("div", { "class": "sci-grafico__grupo" }, [botonConectar, botonQuitarCaja, botonQuitarConexion]),
            mensaje
        ]);

        raiz.appendChild(barra);
        raiz.appendChild(el("div", { "class": "sci-organigrama__marco" }, [lienzo]));
        raiz.appendChild(panel);

        // --- dibujo ----------------------------------------------------------------
        function porId(id) { return cajas.filter(function (c) { return c.id === id; })[0]; }

        function dibujar() {
            while (lienzo.firstChild) { lienzo.removeChild(lienzo.firstChild); }
            conexiones.forEach(function (c) {
                var o = porId(c.de), d = porId(c.a);
                if (!o || !d) { return; }
                var ruta = rutaDeConexion(o, d);
                var esta = seleccion && seleccion.tipo === "conexion" && seleccion.de === c.de && seleccion.a === c.a;
                lienzo.appendChild(svg("path", { d: ruta, fill: "none", stroke: esta ? "#c70012" : "#475569", "stroke-width": esta ? 3 : 2, "pointer-events": "none" }));
                // Un trazo ancho e invisible para poder tocar una línea fina con el dedo.
                lienzo.appendChild(svg("path", { d: ruta, fill: "none", stroke: "transparent", "stroke-width": 16, "data-de": c.de, "data-a": c.a, "class": "sci-organigrama__toque" }));
            });
            cajas.forEach(function (c) {
                var elegida = seleccion && seleccion.tipo === "caja" && seleccion.id === c.id;
                var origen = conectandoDesde === c.id;
                var g = svg("g", {
                    "data-id": c.id, tabindex: 0, role: "button", "class": "sci-organigrama__caja",
                    "aria-label": "Caja: " + (c.t || "sin texto") + ". Flechas para mover, Supr para eliminar."
                });
                g.appendChild(svg("rect", {
                    x: c.x, y: c.y, width: CAJA_ANCHO, height: CAJA_ALTO, rx: 6, fill: "#ffffff",
                    stroke: elegida ? "#c70012" : "#1f2d4a", "stroke-width": elegida ? 3 : 2,
                    "stroke-dasharray": origen ? "6 4" : "none"
                }));
                var lineas = lineasDe(c.t || "");
                if (!lineas.length) {
                    var vacio = svg("text", { x: c.x + CAJA_ANCHO / 2, y: c.y + CAJA_ALTO / 2 + 4, "text-anchor": "middle", "font-size": 12, fill: "#94a3b8", "font-style": "italic" });
                    vacio.textContent = "Sin texto";
                    g.appendChild(vacio);
                }
                var inicio = c.y + CAJA_ALTO / 2 - (lineas.length - 1) * 7.5 + 4.5;
                lineas.forEach(function (linea, i) {
                    var t = svg("text", { x: c.x + CAJA_ANCHO / 2, y: inicio + i * 15, "text-anchor": "middle", "font-size": 12, fill: "#0f172a", "pointer-events": "none" });
                    t.textContent = linea;
                    g.appendChild(t);
                });
                lienzo.appendChild(g);
            });
            actualizarPanel();
        }

        function guardar() {
            campo.value = cajas.length ? JSON.stringify({ nodos: cajas, enlaces: conexiones }) : "";
        }

        function actualizarPanel() {
            var caja = seleccion && seleccion.tipo === "caja" ? porId(seleccion.id) : null;
            var conexion = seleccion && seleccion.tipo === "conexion";
            panel.hidden = !caja && !conexion && !conectandoDesde && !cajas.length;
            etiquetaTexto.parentNode.hidden = !caja;
            botonConectar.hidden = !caja;
            botonQuitarCaja.hidden = !caja;
            botonQuitarConexion.hidden = !conexion;
            if (caja && document.activeElement !== entradaTexto) { entradaTexto.value = caja.t || ""; }
            botonConectar.querySelector("span").textContent = conectandoDesde ? "Cancelar conexión" : "Conectar con otra caja";
            if (conectandoDesde) { mensaje.textContent = "Toque la caja que depende de «" + ((porId(conectandoDesde) || {}).t || "esta caja") + "»."; }
            else if (caja) { mensaje.textContent = "Arrastre la caja para moverla. Use «Conectar» para unirla con otra."; }
            else if (conexion) { mensaje.textContent = "Conexión seleccionada."; }
            else if (cajas.length) { mensaje.textContent = "Toque una caja para editarla, o una línea para quitarla."; }
            else { mensaje.textContent = ""; }
            botonLimpiar.disabled = !cajas.length;
        }

        function punto(e) {
            var p = lienzo.createSVGPoint();
            p.x = e.clientX; p.y = e.clientY;
            var r = p.matrixTransform(lienzo.getScreenCTM().inverse());
            return { x: r.x, y: r.y };
        }

        // --- agregar cajas -----------------------------------------------------------
        function posicionLibre() {
            for (var y = 20; y <= ALTO - CAJA_ALTO; y += 90) {
                for (var x = 20; x <= ANCHO - CAJA_ANCHO; x += 170) {
                    var ocupada = cajas.some(function (c) { return Math.abs(c.x - x) < CAJA_ANCHO && Math.abs(c.y - y) < CAJA_ALTO; });
                    if (!ocupada) { return { x: x, y: y }; }
                }
            }
            return { x: 20, y: 20 };
        }
        function agregar(texto) {
            if (cajas.length >= MAX_CAJAS) { mensaje.textContent = "Se llegó al máximo de " + MAX_CAJAS + " cajas."; return; }
            var libre = posicionLibre();
            var caja = { id: identificador(), x: libre.x, y: libre.y, t: texto || "" };
            cajas.push(caja);
            seleccion = { tipo: "caja", id: caja.id };
            dibujar(); guardar();
            if (!texto) { entradaTexto.focus(); }
        }
        chips.forEach(function (b) { b.addEventListener("click", function () { agregar(b.dataset.puesto); }); });
        botonOtra.addEventListener("click", function () { agregar(""); });

        // Dos pulsaciones para lo que descarta trabajo, sin cuadros de confirmación.
        function conConfirmacion(b, textoInicial, accion) {
            var t = null;
            b.addEventListener("click", function () {
                var etiqueta = b.querySelector("span");
                if (b.dataset.confirmar !== "1") {
                    b.dataset.confirmar = "1"; etiqueta.textContent = "¿Seguro? Pulse otra vez";
                    t = setTimeout(restablecer, 3500); return;
                }
                restablecer(); accion();
            });
            function restablecer() { clearTimeout(t); b.dataset.confirmar = ""; b.querySelector("span").textContent = textoInicial; }
        }
        conConfirmacion(botonLimpiar, "Limpiar", function () {
            cajas = []; conexiones = []; seleccion = null; conectandoDesde = null; dibujar(); guardar();
        });
        var textoBasica = "Estructura básica", confirmandoBasica = null;
        botonBasica.addEventListener("click", function () {
            var etiqueta = botonBasica.querySelector("span");
            if (cajas.length && botonBasica.dataset.confirmar !== "1") {
                botonBasica.dataset.confirmar = "1"; etiqueta.textContent = "Reemplaza lo actual: pulse otra vez";
                confirmandoBasica = setTimeout(function () { botonBasica.dataset.confirmar = ""; etiqueta.textContent = textoBasica; }, 3500);
                return;
            }
            clearTimeout(confirmandoBasica); botonBasica.dataset.confirmar = ""; etiqueta.textContent = textoBasica;
            var base = estructuraBasica();
            cajas = base.nodos; conexiones = base.enlaces; seleccion = null; conectandoDesde = null;
            dibujar(); guardar();
        });

        // --- editar la caja elegida --------------------------------------------------
        entradaTexto.addEventListener("input", function () {
            var caja = seleccion && seleccion.tipo === "caja" ? porId(seleccion.id) : null;
            if (!caja) { return; }
            caja.t = entradaTexto.value.slice(0, MAX_TEXTO);
            dibujar(); guardar();
        });
        // Enter en el texto no debe enviar el formulario entero.
        entradaTexto.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); } });

        botonConectar.addEventListener("click", function () {
            conectandoDesde = conectandoDesde ? null : (seleccion && seleccion.tipo === "caja" ? seleccion.id : null);
            dibujar();
        });
        function quitarCaja(id) {
            cajas = cajas.filter(function (c) { return c.id !== id; });
            conexiones = conexiones.filter(function (c) { return c.de !== id && c.a !== id; });
            seleccion = null; conectandoDesde = null; dibujar(); guardar();
        }
        botonQuitarCaja.addEventListener("click", function () { if (seleccion && seleccion.tipo === "caja") { quitarCaja(seleccion.id); } });
        botonQuitarConexion.addEventListener("click", function () {
            if (!seleccion || seleccion.tipo !== "conexion") { return; }
            conexiones = conexiones.filter(function (c) { return !(c.de === seleccion.de && c.a === seleccion.a); });
            seleccion = null; dibujar(); guardar();
        });

        // --- arrastrar y soltar --------------------------------------------------------
        lienzo.addEventListener("pointerdown", function (e) {
            if (e.pointerType === "mouse" && e.button !== 0) { return; }
            var destino = e.target.closest ? e.target.closest("[data-id], [data-de]") : null;
            if (!destino) { seleccion = null; conectandoDesde = null; dibujar(); return; }
            if (destino.dataset.de) {
                seleccion = { tipo: "conexion", de: destino.dataset.de, a: destino.dataset.a };
                dibujar(); return;
            }
            var id = destino.dataset.id;
            if (conectandoDesde && conectandoDesde !== id) {
                var existe = conexiones.some(function (c) { return c.de === conectandoDesde && c.a === id; });
                if (!existe) { conexiones.push({ de: conectandoDesde, a: id }); }
                conectandoDesde = null; seleccion = { tipo: "caja", id: id };
                dibujar(); guardar(); return;
            }
            conectandoDesde = null;
            seleccion = { tipo: "caja", id: id };
            var caja = porId(id), p = punto(e);
            arrastre = { id: id, dx: p.x - caja.x, dy: p.y - caja.y, movido: false };
            lienzo.setPointerCapture(e.pointerId);
            e.preventDefault();
            dibujar();
        });
        lienzo.addEventListener("pointermove", function (e) {
            if (!arrastre) { return; }
            var caja = porId(arrastre.id), p = punto(e);
            caja.x = Math.round(acotar(p.x - arrastre.dx, 0, ANCHO - CAJA_ANCHO));
            caja.y = Math.round(acotar(p.y - arrastre.dy, 0, ALTO - CAJA_ALTO));
            arrastre.movido = true;
            dibujar();
        });
        function soltar(e) {
            if (!arrastre) { return; }
            var movido = arrastre.movido;
            arrastre = null;
            if (lienzo.hasPointerCapture && lienzo.hasPointerCapture(e.pointerId)) { lienzo.releasePointerCapture(e.pointerId); }
            if (movido) { guardar(); }
        }
        lienzo.addEventListener("pointerup", soltar);
        lienzo.addEventListener("pointercancel", soltar);

        // Con el teclado: flechas para mover la caja enfocada, Supr para eliminarla.
        lienzo.addEventListener("keydown", function (e) {
            var g = e.target.closest ? e.target.closest("[data-id]") : null;
            if (!g) { return; }
            var caja = porId(g.dataset.id), paso = e.shiftKey ? 30 : 10;
            var movimientos = { ArrowLeft: [-paso, 0], ArrowRight: [paso, 0], ArrowUp: [0, -paso], ArrowDown: [0, paso] };
            if (movimientos[e.key]) {
                e.preventDefault();
                caja.x = acotar(caja.x + movimientos[e.key][0], 0, ANCHO - CAJA_ANCHO);
                caja.y = acotar(caja.y + movimientos[e.key][1], 0, ALTO - CAJA_ALTO);
                seleccion = { tipo: "caja", id: caja.id };
                dibujar(); guardar();
                var otra = lienzo.querySelector('[data-id="' + caja.id + '"]'); if (otra) { otra.focus(); }
            } else if (e.key === "Delete" || e.key === "Backspace") {
                e.preventDefault(); quitarCaja(caja.id);
            } else if (e.key === "Enter" || e.key === " ") {
                e.preventDefault(); seleccion = { tipo: "caja", id: caja.id }; dibujar(); entradaTexto.focus();
            }
        });

        dibujar();
    }

    function iniciarTodos(contexto) {
        (contexto || document).querySelectorAll("[data-sci-organigrama]").forEach(iniciar);
    }
    window.SciGraficos = window.SciGraficos || {};
    window.SciGraficos.organigrama = iniciarTodos;
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () { iniciarTodos(); });
    } else {
        iniciarTodos();
    }
})();
