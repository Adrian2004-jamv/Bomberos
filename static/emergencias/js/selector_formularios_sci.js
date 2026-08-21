(() => {
    "use strict";
    const root = document.querySelector("[data-sci-form-selector]");
    if (!root) return;
    const select = root.querySelector("[data-sci-form-select]");
    const open = root.querySelector("[data-sci-form-open]");
    if (!select || !open) return;
    const update = () => { open.href = select.value; };
    select.addEventListener("change", update);
    update();
})();
