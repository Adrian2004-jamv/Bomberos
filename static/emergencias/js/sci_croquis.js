/* Croquis a mano alzada para los formularios SCI.
 *
 * Es un componente, no código de un formulario: se activa solo en cualquier
 * elemento con ``data-sci-croquis`` y no conoce el formulario que lo contiene.
 * El HTML lo da la plantilla ``fragmentos/croquis_editor.html``:
 *
 *   <div data-sci-croquis data-ancho="760" data-alto="800">
 *     <input type="hidden" name="croquis__dibujo" value="data:image/png;base64,...">
 *   </div>
 *
 * El dibujo viaja como un campo más del formulario (un PNG en base64), de modo que
 * el envío sin conexión de la PWA —que serializa el formulario entero— lo guarda
 * en la cola igual que cualquier otro campo. No usa librerías ni red.
 *
 * Los trazos se guardan como vectores y el lienzo se vuelve a pintar a partir de
 * ellos: así «Deshacer» no depende de guardar copias de la imagen entera.
 */
(function () {
    "use strict";

    var COLORES = [
        ["#111111", "Negro"], ["#c70012", "Rojo"], ["#0b4ea2", "Azul"],
        ["#1a7f3c", "Verde"], ["#d97706", "Naranja"]
    ];
    var GROSORES = [[2, "Fino"], [5, "Medio"], [12, "Grueso"]];
    var GROSOR_BORRADOR = 3;      // el borrador es el grosor elegido por este factor
    var LIMITE_TRAZOS = 400;      // evita que un dibujo eterno vuelva lento el repintado

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

    function iniciar(raiz) {
        if (raiz.dataset.listo) { return; }
        raiz.dataset.listo = "1";
        var campo = raiz.querySelector("input[type=hidden]");
        if (!campo) { return; }
        var ancho = parseInt(raiz.dataset.ancho, 10) || 760;
        var alto = parseInt(raiz.dataset.alto, 10) || 800;

        var lienzo = el("canvas", {
            width: ancho, height: alto, "class": "sci-croquis__lienzo", role: "img",
            "aria-label": "Lienzo para dibujar el croquis"
        });
        var ctx = lienzo.getContext("2d");

        var estado = { herramienta: "lapiz", color: COLORES[0][0], grosor: GROSORES[1][0] };
        var trazos = [];
        var base = null;          // el dibujo ya guardado, bajo los trazos nuevos
        var actual = null;

        // --- barra de herramientas -------------------------------------------------
        var botonesHerramienta = {
            lapiz: boton("Lápiz", "ti-pencil", { "data-herramienta": "lapiz", "aria-pressed": "true" }),
            borrador: boton("Borrador", "ti-eraser", { "data-herramienta": "borrador", "aria-pressed": "false" })
        };
        var grupoHerramienta = el("div", { "class": "sci-grafico__grupo", role: "group", "aria-label": "Herramienta" },
            [botonesHerramienta.lapiz, botonesHerramienta.borrador]);

        var botonesColor = COLORES.map(function (par) {
            var b = el("button", {
                type: "button", "class": "sci-grafico__color", "data-color": par[0],
                "aria-label": "Color " + par[1], title: par[1], "aria-pressed": par[0] === estado.color ? "true" : "false"
            }, [el("span", { style: "background:" + par[0] })]);
            return b;
        });
        var grupoColor = el("div", { "class": "sci-grafico__grupo", role: "group", "aria-label": "Color" }, botonesColor);

        var botonesGrosor = GROSORES.map(function (par) {
            return el("button", {
                type: "button", "class": "sci-grafico__grosor", "data-grosor": par[0],
                "aria-label": "Grosor " + par[1].toLowerCase(), title: par[1],
                "aria-pressed": par[0] === estado.grosor ? "true" : "false"
            }, [el("span", { style: "width:" + Math.min(par[0] + 4, 18) + "px;height:" + Math.min(par[0] + 4, 18) + "px" })]);
        });
        var grupoGrosor = el("div", { "class": "sci-grafico__grupo", role: "group", "aria-label": "Grosor del trazo" }, botonesGrosor);

        var botonDeshacer = boton("Deshacer", "ti-arrow-back-up", { "data-accion": "deshacer" });
        var botonLimpiar = boton("Limpiar", "ti-trash", { "data-accion": "limpiar" });
        var grupoAcciones = el("div", { "class": "sci-grafico__grupo", role: "group", "aria-label": "Acciones" },
            [botonDeshacer, botonLimpiar]);

        var barra = el("div", { "class": "sci-grafico__barra", role: "toolbar", "aria-label": "Herramientas de dibujo" },
            [grupoHerramienta, grupoColor, grupoGrosor, grupoAcciones]);
        var ayuda = el("p", {
            "class": "sci-grafico__ayuda",
            texto: "Dibuje con el dedo, el lápiz táctil o el ratón. Si usa el teléfono, desplácese por los márgenes: dentro del recuadro el dedo dibuja."
        });
        var marco = el("div", { "class": "sci-croquis__marco" }, [lienzo]);
        raiz.appendChild(barra);
        raiz.appendChild(marco);
        raiz.appendChild(ayuda);

        // --- dibujo ---------------------------------------------------------------
        function pintarTrazo(t) {
            ctx.lineCap = "round";
            ctx.lineJoin = "round";
            ctx.strokeStyle = t.e ? "#ffffff" : t.c;
            ctx.fillStyle = ctx.strokeStyle;
            ctx.lineWidth = t.w;
            if (t.p.length === 1) {   // un toque: un punto
                ctx.beginPath();
                ctx.arc(t.p[0][0], t.p[0][1], t.w / 2, 0, Math.PI * 2);
                ctx.fill();
                return;
            }
            ctx.beginPath();
            ctx.moveTo(t.p[0][0], t.p[0][1]);
            for (var i = 1; i < t.p.length; i++) { ctx.lineTo(t.p[i][0], t.p[i][1]); }
            ctx.stroke();
        }

        function repintar() {
            ctx.fillStyle = "#ffffff";
            ctx.fillRect(0, 0, ancho, alto);
            if (base) { ctx.drawImage(base, 0, 0, ancho, alto); }
            trazos.forEach(pintarTrazo);
        }

        function guardar() {
            // Sin base ni trazos el campo queda vacío: el servidor y la hoja
            // impresa distinguen «no hay croquis» de «hay un lienzo en blanco».
            campo.value = (!base && trazos.length === 0) ? "" : lienzo.toDataURL("image/png");
            actualizarBotones();
        }

        function actualizarBotones() {
            var hay = !!base || trazos.length > 0;
            botonDeshacer.disabled = trazos.length === 0;
            botonLimpiar.disabled = !hay;
        }

        function punto(e) {
            var r = lienzo.getBoundingClientRect();
            return [
                Math.round((e.clientX - r.left) * ancho / r.width * 10) / 10,
                Math.round((e.clientY - r.top) * alto / r.height * 10) / 10
            ];
        }

        lienzo.addEventListener("pointerdown", function (e) {
            if (e.pointerType === "mouse" && e.button !== 0) { return; }
            e.preventDefault();
            lienzo.setPointerCapture(e.pointerId);
            var esBorrador = estado.herramienta === "borrador";
            actual = {
                c: estado.color,
                w: esBorrador ? estado.grosor * GROSOR_BORRADOR : estado.grosor,
                e: esBorrador,
                p: [punto(e)]
            };
            trazos.push(actual);
            if (trazos.length > LIMITE_TRAZOS) { consolidar(); }
            pintarTrazo(actual);
        });
        lienzo.addEventListener("pointermove", function (e) {
            if (!actual) { return; }
            var p = punto(e), ultimo = actual.p[actual.p.length - 1];
            if (Math.abs(p[0] - ultimo[0]) + Math.abs(p[1] - ultimo[1]) < 0.6) { return; }
            actual.p.push(p);
            // Solo se pinta el segmento nuevo: repintar todo en cada movimiento
            // haría torpe el dibujo en un teléfono modesto.
            var anterior = { c: actual.c, w: actual.w, e: actual.e, p: [ultimo, p] };
            pintarTrazo(anterior);
        });
        function terminar(e) {
            if (!actual) { return; }
            actual = null;
            if (e && lienzo.hasPointerCapture && lienzo.hasPointerCapture(e.pointerId)) {
                lienzo.releasePointerCapture(e.pointerId);
            }
            guardar();
        }
        lienzo.addEventListener("pointerup", terminar);
        lienzo.addEventListener("pointercancel", terminar);
        lienzo.addEventListener("contextmenu", function (e) { e.preventDefault(); });

        // Con demasiados trazos se «hornea» lo dibujado en una imagen base; se pierde
        // poder deshacer lo anterior, pero no el dibujo. Se copia a otro lienzo y no
        // a una ``Image``: esta carga de forma asíncrona y un repintado inmediato
        // la encontraría vacía.
        function consolidar() {
            var nuevo = trazos[trazos.length - 1];
            var copia = document.createElement("canvas");
            copia.width = ancho;
            copia.height = alto;
            copia.getContext("2d").drawImage(lienzo, 0, 0);
            trazos = [nuevo];
            base = copia;
        }

        // --- herramientas ----------------------------------------------------------
        function marcar(botones, elegido) {
            botones.forEach(function (b) { b.setAttribute("aria-pressed", b === elegido ? "true" : "false"); });
        }
        Object.keys(botonesHerramienta).forEach(function (nombre) {
            botonesHerramienta[nombre].addEventListener("click", function () {
                estado.herramienta = nombre;
                marcar(Object.keys(botonesHerramienta).map(function (n) { return botonesHerramienta[n]; }), botonesHerramienta[nombre]);
                lienzo.classList.toggle("sci-croquis__lienzo--borrador", nombre === "borrador");
            });
        });
        botonesColor.forEach(function (b) {
            b.addEventListener("click", function () {
                estado.color = b.dataset.color;
                estado.herramienta = "lapiz";
                marcar(Object.keys(botonesHerramienta).map(function (n) { return botonesHerramienta[n]; }), botonesHerramienta.lapiz);
                lienzo.classList.remove("sci-croquis__lienzo--borrador");
                marcar(botonesColor, b);
            });
        });
        botonesGrosor.forEach(function (b) {
            b.addEventListener("click", function () {
                estado.grosor = parseInt(b.dataset.grosor, 10);
                marcar(botonesGrosor, b);
            });
        });
        botonDeshacer.addEventListener("click", function () {
            if (!trazos.length) { return; }
            trazos.pop();
            repintar();
            guardar();
        });

        // «Limpiar» pide una segunda pulsación en vez de abrir un cuadro de
        // confirmación: borra el trabajo de varios minutos y no hay cómo recuperarlo.
        var temporizador = null;
        botonLimpiar.addEventListener("click", function () {
            var etiqueta = botonLimpiar.querySelector("span");
            if (botonLimpiar.dataset.confirmar !== "1") {
                botonLimpiar.dataset.confirmar = "1";
                etiqueta.textContent = "¿Seguro? Pulse otra vez";
                temporizador = setTimeout(restablecer, 3500);
                return;
            }
            restablecer();
            trazos = [];
            base = null;
            repintar();
            guardar();
        });
        function restablecer() {
            clearTimeout(temporizador);
            botonLimpiar.dataset.confirmar = "";
            botonLimpiar.querySelector("span").textContent = "Limpiar";
        }

        // --- el dibujo guardado ------------------------------------------------------
        repintar();
        if (campo.value) {
            var guardado = new Image();
            guardado.onload = function () { base = guardado; repintar(); actualizarBotones(); };
            guardado.src = campo.value;
        }
        actualizarBotones();
    }

    function iniciarTodos(contexto) {
        (contexto || document).querySelectorAll("[data-sci-croquis]").forEach(iniciar);
    }
    window.SciGraficos = window.SciGraficos || {};
    window.SciGraficos.croquis = iniciarTodos;
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () { iniciarTodos(); });
    } else {
        iniciarTodos();
    }
})();
