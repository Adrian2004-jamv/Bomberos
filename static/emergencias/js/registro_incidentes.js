/* Los filtros del registro se resuelven en el servidor. Este guion evita que
   haya que pulsar «Filtrar» al elegir un tipo de emergencia. */
(() => {
    "use strict";
    const form = document.querySelector("[data-incident-register-tools]");
    if (!form) return;
    const emergencyType = form.querySelector("[data-incident-emergency-type]");
    emergencyType?.addEventListener("change", () => form.submit());
})();
