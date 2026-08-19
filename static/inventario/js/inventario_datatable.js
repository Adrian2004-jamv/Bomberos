(() => {
    "use strict";
    const initialise = (scope = document) => {
        const table = scope.querySelector?.("[data-inventory-table]");
        if (!table || typeof DataTable === "undefined" || DataTable.isDataTable(table)) return;
        new DataTable(table, {
            responsive: {details: {type: "column", target: 0}},
            columnDefs: [
                {className: "dtr-control", orderable: false, searchable: false, targets: 0},
                {orderable: false, searchable: false, targets: -1},
            ],
            order: [[2, "asc"], [4, "asc"], [5, "asc"], [1, "asc"]],
            pageLength: 25,
            lengthMenu: [10, 25, 50, 100],
            layout: {topStart: "search", topEnd: "pageLength", bottomStart: "info", bottomEnd: "paging"},
            language: {
                search: "Buscar en inventario:", searchPlaceholder: "Código, recurso, institución…",
                lengthMenu: "Mostrar _MENU_ recursos", info: "Mostrando _START_ a _END_ de _TOTAL_ recursos",
                infoEmpty: "No hay recursos disponibles", infoFiltered: "(filtrados de _MAX_)", zeroRecords: "No se encontraron recursos con ese criterio",
                emptyTable: "No existen recursos registrados", paginate: {first: "Primera", previous: "Anterior", next: "Siguiente", last: "Última"},
            },
        });
    };
    document.addEventListener("DOMContentLoaded", () => initialise());
    document.addEventListener("htmx:afterSwap", (event) => initialise(event.detail.target));
})();
