(() => {
    "use strict";

    // La columna 0 despliega el detalle en pantallas angostas y la ultima trae
    // los botones de accion: ninguna de las dos es informacion del recurso.
    const COLUMNAS_EXPORTABLES = [1, 2, 3, 4, 5, 6, 7, 8];
    const TITULO = "Inventario de recursos";

    /* Cada celda lleva su valor limpio en data-search o data-export; sin eso, el
       texto de la celda concatena codigo, nombre y marca sin separacion. */
    const valorDeCelda = (data, fila, columna, nodo) => {
        const crudo = nodo?.dataset?.export ?? nodo?.dataset?.search ?? nodo?.textContent ?? data;
        return String(crudo ?? "").replace(/\s+/g, " ").trim();
    };

    /* modifier.page vale "all" por omision, pero se declara: la tabla se pagina
       en el navegador y el archivo debe traer las filas de todas las paginas,
       no solo las visibles. */
    const opcionesDeExportacion = {
        columns: COLUMNAS_EXPORTABLES,
        modifier: {search: "applied", order: "applied", page: "all"},
        format: {body: valorDeCelda},
    };

    const botonesDeExportacion = () => [
        {
            extend: "excelHtml5",
            text: '<i class="ti ti-file-spreadsheet" aria-hidden="true"></i> Excel',
            titleAttr: "Descargar el inventario filtrado en formato Excel",
            title: TITULO,
            filename: () => `inventario-${new Date().toISOString().slice(0, 10)}`,
            exportOptions: opcionesDeExportacion,
        },
        {
            extend: "csvHtml5",
            text: '<i class="ti ti-file-typography" aria-hidden="true"></i> CSV',
            titleAttr: "Descargar el inventario filtrado en CSV",
            filename: () => `inventario-${new Date().toISOString().slice(0, 10)}`,
            // Sin la marca de orden de bytes, Excel abre el CSV con la
            // codificacion del sistema y rompe los acentos.
            charset: "utf-8",
            bom: true,
            fieldSeparator: ";",
            exportOptions: opcionesDeExportacion,
        },
        {
            extend: "copyHtml5",
            text: '<i class="ti ti-clipboard" aria-hidden="true"></i> Copiar',
            titleAttr: "Copiar el inventario filtrado al portapapeles",
            title: TITULO,
            exportOptions: opcionesDeExportacion,
        },
        {
            extend: "print",
            text: '<i class="ti ti-printer" aria-hidden="true"></i> Imprimir',
            titleAttr: "Imprimir el inventario filtrado",
            title: TITULO,
            exportOptions: opcionesDeExportacion,
        },
    ];

    const initialise = (scope = document) => {
        const table = scope.querySelector?.("[data-inventory-table]");
        if (!table || typeof DataTable === "undefined" || DataTable.isDataTable(table)) return;
        const dataTable = new DataTable(table, {
            responsive: {details: {type: "column", target: 0}},
            buttons: botonesDeExportacion(),
            titleRow: 0,
            columnDefs: [
                {className: "dtr-control", orderable: false, searchable: false, targets: 0},
                {orderable: false, searchable: false, targets: -1},
                {responsivePriority: 1, targets: [1, 8, 9]},
                {responsivePriority: 2, targets: [6, 7]},
                {responsivePriority: 3, targets: 2},
                {responsivePriority: 4, targets: 3},
            ],
            order: [[2, "asc"], [4, "asc"], [5, "asc"], [1, "asc"]],
            pageLength: 25,
            lengthMenu: [10, 25, 50, 100],
            layout: {topStart: "buttons", topEnd: "pageLength", bottomStart: "info", bottomEnd: "paging"},
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
