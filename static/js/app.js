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
