/**
 * Tour interactivo del Sistema de Gestión Bomberos Cotopaxi
 * Usa Driver.js 1.3.1 — se activa con el botón "Ayuda" del navbar.
 * Los pasos se adaptan automáticamente a la página actual.
 */
(() => {
    "use strict";

    if (typeof window.driver === "undefined") return;

    // ------------------------------------------------------------------
    // Pasos por módulo (detectados por la URL actual)
    // ------------------------------------------------------------------

    const PASOS = {

        // ── EMERGENCIAS / ACCIÓN ─────────────────────────────────────
        emergencias: [
            {
                element: "[data-nav]",
                popover: {
                    title: "🚒 Menú de navegación",
                    description: "Desde aquí accedes a todos los módulos del sistema: emergencias, inventario, mapas y más. El ítem activo se resalta en rojo.",
                    side: "right", align: "start",
                },
            },
            {
                element: ".incident-map-panel",
                popover: {
                    title: "🗺️ Mapa operativo en tiempo real",
                    description: "El mapa muestra la ubicación de todas las emergencias activas y las unidades desplegadas. Se actualiza automáticamente cada 30 segundos.",
                    side: "bottom", align: "center",
                },
            },
            {
                element: ".incident-map-legend",
                popover: {
                    title: "📍 Simbología del mapa",
                    description: "Cada color e ícono representa un tipo de emergencia diferente. Las unidades operativas aparecen en azul marino.",
                    side: "left", align: "start",
                },
            },
            {
                element: ".incident-actions",
                popover: {
                    title: "⚡ Acciones principales",
                    description: "<b>Formularios</b>: consulta los formularios SCI de las emergencias.<br><b>Nuevo</b>: registra una emergencia nueva en el sistema.",
                    side: "bottom", align: "center",
                },
            },
            {
                element: ".incident-register",
                popover: {
                    title: "📋 Registro dinámico",
                    description: "Lista de todas las emergencias reportadas. Puedes filtrar por estado, tipo, fecha y texto libre.",
                    side: "top", align: "start",
                },
            },
            {
                element: ".incident-phase-filters",
                popover: {
                    title: "🔍 Filtros de fase",
                    description: "Filtra por <b>Todos</b>, <b>En curso</b> o <b>Terminadas</b>. El número dentro de cada botón muestra cuántas emergencias hay en ese estado.",
                    side: "bottom", align: "start",
                },
            },
            {
                element: ".incident-filter-submit",
                popover: {
                    title: "▶ Aplicar filtros",
                    description: "Después de seleccionar los criterios de búsqueda (tipo, fechas, texto), presiona este botón para filtrar el listado.",
                    side: "bottom", align: "start",
                },
            },
            {
                element: ".incident-filter-export",
                popover: {
                    title: "📥 Exportar CSV",
                    description: "Descarga el listado filtrado como archivo CSV para procesarlo en Excel u otras herramientas.",
                    side: "bottom", align: "end",
                },
            },
            {
                element: ".incident-register-table tbody tr:first-child .incident-row-actions",
                popover: {
                    title: "⚙️ Acciones por emergencia",
                    description: "<b>Formularios</b>: abre el panel de formularios SCI de esa emergencia.<br><b>Borrar</b>: elimina la emergencia (solo gestores).",
                    side: "left", align: "start",
                },
            },
        ],

        // ── DETALLE DE EMERGENCIA ─────────────────────────────────────
        detalle: [
            {
                element: ".panel",
                popover: {
                    title: "📄 Ficha de la emergencia",
                    description: "Aquí ves todos los datos del incidente: tipo, prioridad, estación responsable, dirección y descripción.",
                    side: "bottom", align: "start",
                },
            },
            {
                element: "#formularios-sci",
                popover: {
                    title: "📁 Formularios SCI",
                    description: "Panel de documentación operativa. Muestra el estado de los 12 formularios SCI del incidente y te indica cuál es el siguiente a completar.",
                    side: "top", align: "start",
                },
            },
            {
                element: ".sci-next-step",
                popover: {
                    title: "➡️ Siguiente formulario",
                    description: "Este banner te indica cuál es el siguiente formulario pendiente. Haz clic en <b>Llenar ahora</b> para completarlo directamente.",
                    side: "bottom", align: "start",
                },
            },
            {
                element: ".sci-form-tabs",
                popover: {
                    title: "🗂️ Estado de los 12 formularios",
                    description: "Verde = Finalizado ✓ · Amarillo = Incompleto · Gris = No iniciado · 🔒 = Bloqueado (debe finalizar el anterior primero).",
                    side: "top", align: "start",
                },
            },
            {
                element: ".sci-status-legend",
                popover: {
                    title: "🟢 Leyenda de estados",
                    description: "Referencia visual para interpretar el estado de cada formulario SCI en el panel.",
                    side: "bottom", align: "start",
                },
            },
        ],

        // ── INVENTARIO ────────────────────────────────────────────────
        inventario: [
            {
                element: ".inventory-toolbar",
                popover: {
                    title: "📦 Inventario de recursos",
                    description: "Gestión de todos los recursos institucionales: vehículos, equipos de protección, herramientas y más.",
                    side: "bottom", align: "start",
                },
            },
            {
                element: ".inventory-action--primary",
                popover: {
                    title: "➕ Registrar recurso",
                    description: "Agrega un nuevo recurso al inventario institucional. Solo los gestores tienen acceso a esta función.",
                    side: "bottom", align: "end",
                },
            },
            {
                element: "div.dt-buttons",
                popover: {
                    title: "📊 Exportar inventario",
                    description: "Descarga el inventario en <b>Excel</b>, <b>CSV</b>, cópialo al portapapeles o imprímelo directamente.",
                    side: "bottom", align: "start",
                },
            },
            {
                element: "#inventory-datatable thead tr:first-child",
                popover: {
                    title: "📋 Columnas de la tabla",
                    description: "La tabla muestra: Recurso, Institución, Estado operativo, Disponibilidad y el semáforo de Foco (si la disponibilidad fue confirmada hoy).",
                    side: "bottom", align: "start",
                },
            },
            {
                element: ".inventory-filter-row",
                popover: {
                    title: "🔍 Filtros por columna",
                    description: "Filtra por institución, estado o disponibilidad usando los selectores de cada columna. El buscador de texto busca en todo el inventario.",
                    side: "bottom", align: "start",
                },
            },
            {
                element: ".inventory-datatable tbody tr:first-child .availability-light",
                popover: {
                    title: "💡 Foco de disponibilidad",
                    description: "<b>Verde</b>: la disponibilidad fue confirmada en las últimas 24 horas.<br><b>Gris (Pendiente)</b>: requiere confirmación. Usa el botón <b>Confirmar</b>.",
                    side: "left", align: "start",
                },
            },
            {
                element: ".inventory-datatable tbody tr:first-child .inventory-row-actions",
                popover: {
                    title: "⚙️ Acciones del recurso",
                    description: "<b>Ver</b>: ficha completa del recurso.<br><b>Editar</b>: modificar los datos.<br><b>Confirmar</b>: marcar como operativo y disponible hoy.",
                    side: "left", align: "start",
                },
            },
        ],

        // ── DASHBOARD ─────────────────────────────────────────────────
        dashboard: [
            {
                element: ".welcome-card, .dashboard-welcome, [class*='welcome']",
                popover: {
                    title: "🏠 Panel de control",
                    description: "Resumen institucional con tu rol, estación asignada y la situación operativa actual de toda la provincia.",
                    side: "bottom", align: "start",
                },
            },
            {
                element: "[class*='stat'], [class*='kpi'], [class*='counter'], [class*='metric']",
                popover: {
                    title: "📊 Indicadores operativos",
                    description: "Emergencias en curso, unidades desplegadas, emergencias terminadas y expedientes sin SCI-211.",
                    side: "bottom", align: "start",
                },
            },
        ],

        // ── MAPA OPERATIVO ────────────────────────────────────────────
        mapas: [
            {
                element: "#mapa-operativo, [id*='map'], .leaflet-container",
                popover: {
                    title: "🗺️ Mapa operativo provincial",
                    description: "Vista en tiempo real de todas las unidades y emergencias activas en la provincia de Cotopaxi.",
                    side: "bottom", align: "center",
                },
            },
        ],

        // ── FORMULARIOS SCI ───────────────────────────────────────────
        sci: [
            {
                popover: {
                    title: "📋 Formularios SCI",
                    description: "El Sistema de Comando de Incidentes (SCI) organiza la documentación operativa en 12 formularios que deben completarse en orden.",
                    side: "bottom", align: "start",
                },
            },
            {
                element: ".sci-form-tabs, .sci-expedition-list, table",
                popover: {
                    title: "🗂️ Expedientes por incidente",
                    description: "Cada emergencia tiene su propio expediente con los formularios SCI generados. Haz clic en una emergencia para ver sus documentos.",
                    side: "top", align: "start",
                },
            },
        ],

        // ── GENERAL (fallback para cualquier página) ──────────────────
        general: [
            {
                popover: {
                    title: "👋 Bienvenido al sistema",
                    description: "Sistema de gestión operativa de los Cuerpos de Bomberos de Cotopaxi. Usa el menú lateral para navegar entre módulos.",
                    side: "bottom", align: "center",
                },
            },
            {
                element: ".sidebar",
                popover: {
                    title: "📌 Menú lateral",
                    description: "Accede a: <b>Acción</b> (emergencias), <b>Panel de control</b>, <b>Inventario</b>, <b>Formularios SCI</b> y <b>Mapa operativo</b>.",
                    side: "right", align: "start",
                },
            },
            {
                element: ".sidebar-user",
                popover: {
                    title: "👤 Tu sesión",
                    description: "Muestra tu nombre, estación asignada y accesos rápidos para cambiar contraseña o cerrar sesión.",
                    side: "right", align: "end",
                },
            },
            {
                element: ".sidebar-collapse",
                popover: {
                    title: "◀ Contraer menú",
                    description: "Puedes contraer el menú lateral para ganar más espacio en pantalla. El sistema recuerda tu preferencia.",
                    side: "right", align: "start",
                },
            },
        ],
    };

    // ------------------------------------------------------------------
    // Detectar el módulo activo según la URL
    // ------------------------------------------------------------------
    function detectarModulo() {
        const path = window.location.pathname;
        if (path.includes("/emergencias/") && path.match(/\/\d+\//)) return "detalle";
        if (path.includes("/emergencias/")) return "emergencias";
        if (path.includes("/inventario/")) return "inventario";
        if (path.includes("/dashboard/")) return "dashboard";
        if (path.includes("/mapas/")) return "mapas";
        if (path.includes("/formularios-sci") || path.includes("/sci")) return "sci";
        return "general";
    }

    // ------------------------------------------------------------------
    // Filtrar pasos cuyo elemento no existe en el DOM actual
    // ------------------------------------------------------------------
    function filtrarPasos(pasos) {
        return pasos.filter((paso) => {
            if (!paso.element) return true; // pasos sin elemento siempre se muestran
            return document.querySelector(paso.element) !== null;
        });
    }

    // ------------------------------------------------------------------
    // Inicializar Driver.js
    // ------------------------------------------------------------------
    function iniciarTour() {
        const modulo = detectarModulo();
        const pasosModulo = filtrarPasos(PASOS[modulo] || PASOS.general);
        const pasosGenerales = modulo !== "general"
            ? filtrarPasos(PASOS.general.slice(1)) // agrega sidebar/usuario al final
            : [];
        const pasos = [...pasosModulo, ...pasosGenerales];

        if (pasos.length === 0) {
            alert("No hay pasos de guía disponibles para esta página.");
            return;
        }

        const driverObj = window.driver.js.driver({
            showProgress: true,
            animate: true,
            overlayColor: "rgb(7 27 61)",
            overlayOpacity: 0.72,
            smoothScroll: true,
            allowClose: true,
            stagePadding: 6,
            stageRadius: 8,
            progressText: "Paso {{current}} de {{total}}",
            nextBtnText: "Siguiente →",
            prevBtnText: "← Anterior",
            doneBtnText: "✓ Listo",
            steps: pasos,
            onDestroyStarted: () => {
                driverObj.destroy();
                // Guarda que el usuario ya vio el tour en esta sesión
                try { sessionStorage.setItem("bomberos:tour-visto", "1"); } catch (_) {}
            },
        });

        driverObj.drive();
    }

    // ------------------------------------------------------------------
    // Exponer función globalmente para el botón del navbar
    // ------------------------------------------------------------------
    window.bomberosTour = { iniciar: iniciarTour };

    // ------------------------------------------------------------------
    // Tour automático solo la primera vez (primera sesión del usuario)
    // ------------------------------------------------------------------
    try {
        const yaVisto = sessionStorage.getItem("bomberos:tour-visto");
        const primerIngreso = !localStorage.getItem("bomberos:tour-completado");
        if (!yaVisto && primerIngreso) {
            // Espera a que el DOM esté listo para que los elementos existan
            window.addEventListener("load", () => {
                setTimeout(() => {
                    iniciarTour();
                    localStorage.setItem("bomberos:tour-completado", "1");
                }, 800);
            });
        }
    } catch (_) {}
})();
