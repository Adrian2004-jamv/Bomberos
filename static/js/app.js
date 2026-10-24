const body = document.body;
const toggle = document.querySelector("[data-sidebar-toggle]");
const closeButton = document.querySelector("[data-sidebar-close]");

function initializeVisualComponents(root = document) {
    if (!window.TomSelect) return;
    root.querySelectorAll("select[data-enhanced-select], select.form-control").forEach((select) => {
        if (select.tomselect || (select.options.length < 5 && !select.hasAttribute("data-enhanced-select"))) return;
        new TomSelect(select, {
            allowEmptyOption: true,
            create: false,
            maxOptions: 200,
            placeholder: select.dataset.placeholder || "Buscar o seleccionar…",
        });
    });
}

document.addEventListener("DOMContentLoaded", () => initializeVisualComponents());
document.addEventListener("htmx:afterSwap", (event) => initializeVisualComponents(event.detail.target));

function setSidebar(open) {
    body.classList.toggle("sidebar-open", open);
    if (toggle) {
        toggle.setAttribute("aria-expanded", String(open));
    }
}

if (toggle) {
    toggle.addEventListener("click", () => {
        setSidebar(!body.classList.contains("sidebar-open"));
    });
}

if (closeButton) {
    closeButton.addEventListener("click", () => setSidebar(false));
}

// Menú contraído: deja solo la franja de iconos y devuelve el ancho a la
// pantalla. La elección se recuerda porque es una preferencia de sitio de
// trabajo, no algo que apetezca repetir en cada página.
const CLAVE_MENU = "bomberos:menu-contraido";
const botonContraer = document.querySelector("[data-sidebar-collapse]");

function pintarMenuContraido(contraido) {
    body.classList.toggle("sidebar-collapsed", contraido);
    if (!botonContraer) return;
    botonContraer.setAttribute("aria-expanded", String(!contraido));
    botonContraer.title = contraido ? "Desplegar el menú" : "Contraer el menú";
}

if (botonContraer) {
    // Con el menú contraído el nombre del módulo no se ve, así que pasa al
    // título: el puntero lo muestra y los lectores de pantalla lo anuncian.
    document.querySelectorAll(".sidebar [data-nav]").forEach((enlace) => {
        const nombre = enlace.textContent.trim();
        if (nombre && !enlace.title) enlace.title = nombre;
    });

    // El guion en línea de base.html aplica la clase antes de pintar, pero no
    // toca el botón: sin esto, al recargar con el menú contraído el botón
    // seguía anunciando «Contraer» cuando lo que hace es desplegar.
    pintarMenuContraido(body.classList.contains("sidebar-collapsed"));

    botonContraer.addEventListener("click", () => {
        const contraido = !body.classList.contains("sidebar-collapsed");
        pintarMenuContraido(contraido);
        try {
            window.localStorage.setItem(CLAVE_MENU, contraido ? "1" : "0");
        } catch (_error) {
            // Navegador sin almacenamiento: el menú funciona igual, solo que
            // vuelve a abrirse en la siguiente página.
        }
    });
}

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        setSidebar(false);
    }
});

window.addEventListener("resize", () => {
    if (window.innerWidth > 960) {
        setSidebar(false);
    }
});

document.querySelectorAll("[data-password-toggle]").forEach((passwordToggle) => {
    const passwordInput = document.getElementById(passwordToggle.dataset.passwordInput);

    if (!passwordInput) {
        return;
    }

    passwordToggle.addEventListener("click", () => {
        const passwordIsVisible = passwordInput.type === "text";
        passwordInput.type = passwordIsVisible ? "password" : "text";
        passwordToggle.setAttribute("aria-pressed", String(!passwordIsVisible));
        passwordToggle.setAttribute(
            "aria-label",
            passwordIsVisible ? "Mostrar contraseña" : "Ocultar contraseña",
        );
        passwordInput.focus();
    });
});

const pwaControls = document.querySelector("[data-pwa-controls]");

if (pwaControls) {
    const connectionState = pwaControls.querySelector("[data-connection-state]");
    const connectionLabel = connectionState.querySelector("strong");
    const installButton = pwaControls.querySelector("[data-install-app]");
    const updateNotice = pwaControls.querySelector("[data-update-notice]");
    const updateButton = pwaControls.querySelector("[data-update-app]");
    let installPrompt = null;
    let waitingWorker = null;
    let reloadingForUpdate = false;
    let restoredTimer = null;

    const setConnectionState = (state, label) => {
        connectionState.dataset.state = state;
        connectionLabel.textContent = label;
    };

    const showUpdate = (worker) => {
        waitingWorker = worker;
        updateNotice.hidden = false;
    };

    window.addEventListener("offline", () => {
        clearTimeout(restoredTimer);
        setConnectionState("offline", "Sin conexión");
    });
    window.addEventListener("online", () => {
        setConnectionState("restored", "Conexión restablecida");
        restoredTimer = setTimeout(() => setConnectionState("online", "En línea"), 4000);
    });
    if (!navigator.onLine) setConnectionState("offline", "Sin conexión");

    window.addEventListener("beforeinstallprompt", (event) => {
        event.preventDefault();
        installPrompt = event;
        installButton.hidden = false;
    });
    installButton.addEventListener("click", async () => {
        if (!installPrompt) return;
        installButton.hidden = true;
        await installPrompt.prompt();
        await installPrompt.userChoice;
        installPrompt = null;
    });
    window.addEventListener("appinstalled", () => {
        installPrompt = null;
        installButton.hidden = true;
    });

    if ("serviceWorker" in navigator) {
        window.addEventListener("load", async () => {
            try {
                const registration = await navigator.serviceWorker.register(
                    pwaControls.dataset.serviceWorkerUrl,
                    { scope: "/" },
                );
                if (registration.waiting) showUpdate(registration.waiting);
                registration.addEventListener("updatefound", () => {
                    const worker = registration.installing;
                    if (!worker) return;
                    worker.addEventListener("statechange", () => {
                        if (worker.state === "installed" && navigator.serviceWorker.controller) showUpdate(worker);
                    });
                });
            } catch (error) {
                console.error("No fue posible registrar la funcionalidad PWA.", error.name);
            }
        }, { once: true });

        navigator.serviceWorker.addEventListener("controllerchange", () => {
            if (reloadingForUpdate) return;
            reloadingForUpdate = true;
            window.location.reload();
        });
        document.querySelectorAll('form[action$="/usuarios/cerrar-sesion/"]').forEach((form) => {
            form.addEventListener("submit", () => navigator.serviceWorker.controller?.postMessage({ type: "CLEAR_SESSION_CACHE" }));
        });
    }

    updateButton.addEventListener("click", () => {
        updateNotice.hidden = true;
        waitingWorker?.postMessage({ type: "SKIP_WAITING" });
    });
}

// Confirmación para lo que cuesta deshacer.
//
// Finalizar un formulario lo deja en solo lectura; terminar o cancelar un incidente
// deja huella en el expediente. Son botones que se pulsan con guantes y con prisa
// junto a otros, así que antes de enviar se pide confirmación con un diálogo que dice
// qué va a pasar. Cualquier botón de envío con «data-confirmar» lo activa:
//
//   data-confirmar          el texto del aviso (obligatorio)
//   data-confirmar-titulo   el título del diálogo
//   data-confirmar-boton    la etiqueta del botón de confirmar
//
// Es un <dialog> nativo y no una biblioteca: bloquea el resto de la pantalla, atrapa
// el foco, se cierra con Esc y no depende de que nada se descargue, que en una escena
// sin señal es justo lo que no se puede asumir.
//
// El oyente va en la fase de CAPTURA y detiene el evento. Es lo que lo hace funcionar
// en los formularios con guardado sin conexión: sin-conexion.js escucha en el propio
// formulario y lanza el envío al instante, de modo que un oyente normal en el documento
// llegaba tarde —cuando el envío ya había salido— y el aviso no frenaba nada.
(() => {
    "use strict";

    let dialogo = null;
    let ocupado = false;
    let alAceptar = null;
    let temporizador = null;

    const crearDialogo = () => {
        const d = document.createElement("dialog");
        d.className = "dialogo-confirmar";
        d.setAttribute("aria-labelledby", "dialogo-confirmar-titulo");
        d.setAttribute("aria-describedby", "dialogo-confirmar-texto");
        d.innerHTML = `
            <div class="dialogo-confirmar__cuerpo">
                <h2 id="dialogo-confirmar-titulo" class="dialogo-confirmar__titulo"></h2>
                <p id="dialogo-confirmar-texto" class="dialogo-confirmar__texto"></p>
                <p class="dialogo-confirmar__estado" role="status" aria-live="polite" hidden></p>
                <div class="dialogo-confirmar__acciones">
                    <button type="button" class="button" data-dialogo-cancelar autofocus>Cancelar</button>
                    <button type="button" class="button button--primary" data-dialogo-confirmar>
                        <span class="dialogo-confirmar__spinner" aria-hidden="true" hidden></span>
                        <span data-dialogo-etiqueta>Confirmar</span>
                    </button>
                </div>
            </div>`;
        document.body.appendChild(d);

        d.querySelector("[data-dialogo-cancelar]").addEventListener("click", () => d.close());
        d.querySelector("[data-dialogo-confirmar]").addEventListener("click", () => {
            if (ocupado) return;
            aceptar(d);
        });
        // Esc no cierra mientras se envía: el envío ya salió y cerrar daría a entender
        // que se canceló.
        d.addEventListener("cancel", (evento) => { if (ocupado) evento.preventDefault(); });
        d.addEventListener("close", () => descansar(d));
        return d;
    };

    const descansar = (d) => {
        ocupado = false;
        alAceptar = null;
        clearTimeout(temporizador);
        d.querySelector("[data-dialogo-confirmar]").disabled = false;
        d.querySelector("[data-dialogo-cancelar]").disabled = false;
        d.querySelector(".dialogo-confirmar__spinner").hidden = true;
        d.querySelector(".dialogo-confirmar__estado").hidden = true;
    };

    const aceptar = (d) => {
        ocupado = true;
        const confirmar = d.querySelector("[data-dialogo-confirmar]");
        const cancelar = d.querySelector("[data-dialogo-cancelar]");
        const estado = d.querySelector(".dialogo-confirmar__estado");
        confirmar.disabled = true;
        cancelar.disabled = true;
        d.querySelector(".dialogo-confirmar__spinner").hidden = false;
        d.querySelector("[data-dialogo-etiqueta]").textContent = "Guardando…";
        estado.textContent = "Guardando sus cambios y finalizando…";
        estado.hidden = false;
        // Si la respuesta tarda más de lo normal —señal débil— se devuelve el control
        // en vez de dejar el diálogo girando para siempre. Lo enviado sigue su curso:
        // si no llega, queda guardado en el equipo.
        temporizador = setTimeout(() => {
            cancelar.disabled = false;
            cancelar.textContent = "Cerrar";
            ocupado = false;
            estado.textContent = "La respuesta tarda más de lo normal. Puede esperar o cerrar "
                + "este aviso: si no hay señal, lo escrito queda guardado en este equipo.";
        }, 30000);
        if (alAceptar) alAceptar();
    };

    const pedirConfirmacion = ({ titulo, texto, confirmar }, enviar) => {
        if (!window.HTMLDialogElement) {
            // Un navegador sin <dialog>: el aviso de siempre, que también frena.
            if (window.confirm(texto)) enviar();
            return;
        }
        dialogo = dialogo || crearDialogo();
        dialogo.querySelector(".dialogo-confirmar__titulo").textContent = titulo;
        dialogo.querySelector(".dialogo-confirmar__texto").textContent = texto;
        dialogo.querySelector("[data-dialogo-etiqueta]").textContent = confirmar;
        dialogo.querySelector("[data-dialogo-cancelar]").textContent = "Cancelar";
        alAceptar = enviar;
        dialogo.showModal();
    };

    document.addEventListener("submit", (evento) => {
        const boton = evento.submitter;
        const aviso = boton?.dataset?.confirmar;
        if (!aviso) return;
        // El envío que nace de confirmar vuelve a pasar por aquí: ya está aceptado.
        if (boton.dataset.confirmado === "1") {
            delete boton.dataset.confirmado;
            return;
        }
        evento.preventDefault();
        evento.stopImmediatePropagation();
        const formulario = evento.target;
        pedirConfirmacion({
            titulo: boton.dataset.confirmarTitulo || "Confirmar acción",
            texto: aviso,
            confirmar: boton.dataset.confirmarBoton || "Confirmar",
        }, () => {
            boton.dataset.confirmado = "1";
            if (formulario.requestSubmit) {
                formulario.requestSubmit(boton);
            } else {
                // Sin requestSubmit el botón no viaja: se manda su valor a mano.
                if (boton.name) {
                    const oculto = document.createElement("input");
                    oculto.type = "hidden";
                    oculto.name = boton.name;
                    oculto.value = boton.value;
                    formulario.appendChild(oculto);
                }
                formulario.submit();
            }
        });
    }, true);

    // sin-conexion.js avisa cuando lo enviado quedó guardado en el equipo por falta de
    // señal: el diálogo ya cumplió, y su mensaje es el del aviso de la PWA.
    document.addEventListener("bomberos:envio-en-cola", () => {
        if (dialogo && dialogo.open) {
            ocupado = false;
            dialogo.close();
        }
    });
})();
