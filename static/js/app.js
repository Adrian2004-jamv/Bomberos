const body = document.body;
const toggle = document.querySelector("[data-sidebar-toggle]");
const closeButton = document.querySelector("[data-sidebar-close]");

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
