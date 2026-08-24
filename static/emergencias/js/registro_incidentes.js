/* Los filtros del registro se resuelven en el servidor. Este guion solo evita
   que haya que pulsar «Filtrar» al elegir una etapa documental. */
(() => {
    "use strict";
    const form = document.querySelector("[data-incident-register-tools]");
    if (!form) return;
    const stage = form.querySelector("[data-incident-document-stage]");
    stage?.addEventListener("change", () => form.submit());
})();
