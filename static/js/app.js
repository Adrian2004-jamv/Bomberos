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
