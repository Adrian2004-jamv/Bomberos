"use strict";

// Guarda en el teléfono lo que se escribe cuando no hay señal.
//
// Los formularios SCI se envían como HTML plano, de modo que sin esto el
// navegador muestra su pantalla de error y lo escrito se pierde: media hora de
// trabajo en la escena de un incendio, tirada porque el valle no tiene
// cobertura. Aquí el envío pasa por «fetch», y lo que no sale queda guardado.
//
// Guardar un formulario SCI sobrescribe sus datos, así que reenviar dos veces
// lo mismo deja el documento igual. Por eso no hace falta clave de idempotencia.
(() => {
    const cola = window.colaDeEnvios;
    if (!cola) return;

    const aviso = document.querySelector("[data-pendientes-envio]");
    const cuenta = document.querySelector("[data-pendientes-cuenta]");
    const reintentar = document.querySelector("[data-pendientes-reintentar]");
    const detalle = document.querySelector("[data-pendientes-detalle]");

    const pintar = (cuantos) => {
        if (!aviso) return;
        aviso.hidden = cuantos === 0;
        if (cuenta) cuenta.textContent = String(cuantos);
    };

    const decir = (texto) => { if (detalle) detalle.textContent = texto; };

    cola.alCambiar(pintar);
    cola.pendientes().then(pintar).catch(() => {});

    const enviar = async () => {
        const resultado = await cola.enviarPendientes();
        if (resultado.sesionCaducada) {
            decir(
                "Su sesión caducó mientras no había señal. Vuelva a iniciar sesión "
                + "y lo guardado se enviará solo; no se ha perdido nada.",
            );
        } else if (resultado.entregados) {
            decir(`Se enviaron ${resultado.entregados} registro(s) que estaban guardados.`);
        } else if (resultado.restantes) {
            decir("Todavía sin conexión con el servidor. Se reintentará al volver la señal.");
        }
        return resultado;
    };

    window.addEventListener("online", enviar);
    if (reintentar) reintentar.addEventListener("click", enviar);
    if (navigator.onLine) enviar().catch(() => {});

    // El envío pasa siempre por aquí, con o sin señal: «navigator.onLine» dice
    // que hay red, no que se llegue al servidor, y el caso que importa —señal
    // débil en el valle— se ve exactamente igual que estar en línea.
    const interceptar = (formulario) => {
        // Qué botón se pulsó importa: el SCI-211 distingue «guardar_recurso» de
        // finalizar por el valor del botón. «event.submitter» lo da en los
        // navegadores nuevos; en los que no, este rastro es la única forma de
        // saberlo, y perderlo cambiaría lo que hace el formulario.
        let ultimoBoton = null;
        formulario.addEventListener("click", (evento) => {
            const boton = evento.target.closest("button, input[type=submit]");
            if (boton && formulario.contains(boton)) ultimoBoton = boton;
        });

        formulario.addEventListener("submit", async (evento) => {
            if (!window.fetch || !window.FormData) return;  // que lo haga el navegador
            evento.preventDefault();

            const pulsado = evento.submitter || ultimoBoton;
            const datos = new FormData(formulario);
            if (pulsado && pulsado.name) datos.append(pulsado.name, pulsado.value);
            // El testigo viaja en la cabecera, tomado en el momento del envío:
            // el de la página caduca si el formulario espera horas en la cola.
            datos.delete("csrfmiddlewaretoken");
            const cuerpo = new URLSearchParams(datos).toString();
            const envio = {
                url: formulario.action || window.location.href,
                tipo: "formulario",
                cuerpo,
                titulo: formulario.dataset.guardarSinConexion || "Formulario",
            };

            const boton = pulsado;
            if (boton) boton.disabled = true;
            try {
                const respuesta = await fetch(envio.url, {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-CSRFToken": (document.cookie.split("; ")
                            .find((dato) => dato.startsWith("csrftoken="))?.split("=")[1] || ""),
                    },
                    body: cuerpo,
                });
                // El servidor responde con una redirección al guardar bien y
                // con la propia página cuando algo no valida. En los dos casos
                // lo que corresponde es mostrar lo que el servidor devolvió.
                if (respuesta.redirected) { window.location.assign(respuesta.url); return; }
                const html = await respuesta.text();
                document.open();
                document.write(html);
                document.close();
            } catch (_error) {
                await cola.guardar(envio);
                if (boton) boton.disabled = false;
                decir(
                    `«${envio.titulo}» quedó guardado en este equipo. Se enviará solo `
                    + "cuando vuelva la señal. Puede seguir trabajando.",
                );
                if (aviso) aviso.scrollIntoView({ block: "nearest", behavior: "smooth" });
            }
        });
    };

    document.querySelectorAll("[data-guardar-sin-conexion]").forEach(interceptar);
})();
