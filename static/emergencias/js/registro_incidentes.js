(() => {
    "use strict";
    const tools = document.querySelector("[data-incident-register-tools]");
    if (!tools) return;
    const rows = [...document.querySelectorAll("[data-incident-row]")];
    const empty = document.querySelector("[data-incident-filter-empty]");
    const search = tools.querySelector("[data-incident-search]");
    const documentStage = tools.querySelector("[data-incident-document-stage]");
    const phaseButtons = [...tools.querySelectorAll("[data-incident-phase]")];
    let phase = "all";

    const normalise = (value) => String(value || "").normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();

    const filter = () => {
        const term = normalise(search?.value);
        const stage = documentStage?.value || "all";
        let visible = 0;
        rows.forEach((row) => {
            const matchesPhase = phase === "all" || row.dataset.phase === phase;
            const matchesStage = stage === "all" || row.dataset.documentStage === stage;
            const matchesSearch = !term || normalise(row.dataset.search).includes(term);
            row.hidden = !(matchesPhase && matchesStage && matchesSearch);
            if (!row.hidden) visible += 1;
        });
        if (empty) empty.hidden = visible !== 0;
    };

    phaseButtons.forEach((button) => button.addEventListener("click", () => {
        phase = button.dataset.incidentPhase;
        phaseButtons.forEach((item) => {
            const active = item === button;
            item.classList.toggle("is-active", active);
            item.setAttribute("aria-pressed", String(active));
        });
        filter();
    }));
    search?.addEventListener("input", filter);
    documentStage?.addEventListener("change", filter);
})();
