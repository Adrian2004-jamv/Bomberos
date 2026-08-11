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
