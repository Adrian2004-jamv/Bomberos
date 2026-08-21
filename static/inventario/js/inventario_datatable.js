(() => {
    "use strict";
    const initialise = (scope = document) => {
        const table = scope.querySelector?.("[data-inventory-table]");
        if (!table || typeof DataTable === "undefined" || DataTable.isDataTable(table)) return;
        const dataTable = new DataTable(table, {
            responsive: {details: {type: "column", target: 0}},
            titleRow: 0,
            columnDefs: [
                {className: "dtr-control", orderable: false, searchable: false, targets: 0},
                {orderable: false, searchable: false, targets: -1},
                {responsivePriority: 1, targets: [1, 9]},
                {responsivePriority: 2, targets: [6, 7]},
                {responsivePriority: 3, targets: 2},
                {responsivePriority: 4, targets: 3},
            ],
            order: [[2, "asc"], [4, "asc"], [5, "asc"], [1, "asc"]],
            pageLength: 25,
            lengthMenu: [10, 25, 50, 100],
            layout: {topStart: null, topEnd: "pageLength", bottomStart: "info", bottomEnd: "paging"},
            language: {
                search: "Buscar en inventario:", searchPlaceholder: "Código, recurso, institución…",
                lengthMenu: "Mostrar _MENU_ recursos", info: "Mostrando _START_ a _END_ de _TOTAL_ recursos",
                infoEmpty: "No hay recursos disponibles", infoFiltered: "(filtrados de _MAX_)", zeroRecords: "No se encontraron recursos con ese criterio",
                emptyTable: "No existen recursos registrados", paginate: {first: "Primera", previous: "Anterior", next: "Siguiente", last: "Última"},
            },
        });
        const filters = table.querySelector("[data-inventory-column-filters]");
        if (!filters) return;
        table.dataset.datatableReady = "true";
        const search = filters.querySelector("[data-inventory-global-search]");
        search?.addEventListener("input", () => dataTable.search(search.value).draw());
        filters.querySelectorAll("[data-inventory-column-filter]").forEach((select) => {
            const columnIndex = Number(select.dataset.inventoryColumnFilter);
            const column = dataTable.column(columnIndex);
            const values = [...table.tBodies[0].rows]
                .map((row) => row.cells[columnIndex]?.dataset.search || row.cells[columnIndex]?.textContent || "")
                .map((value) => value.trim())
                .filter(Boolean);
            [...new Set(values)].sort((a, b) => a.localeCompare(b, "es", {sensitivity: "base"}))
                .forEach((value) => select.add(new Option(value, value)));
            select.addEventListener("change", () => column.search(select.value, {exact: true}).draw());
        });
        filters.querySelector("[data-clear-inventory-filters]")?.addEventListener("click", () => {
            filters.querySelectorAll("select").forEach((select) => { select.value = ""; });
            if (search) search.value = "";
            dataTable.search("").columns().search("").draw();
        });
    };
    document.addEventListener("DOMContentLoaded", () => initialise());
})();
