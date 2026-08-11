(() => {
    "use strict";

    const REFRESH_INTERVAL_MS = 10000;
    const COTOPAXI_CENTER = [-0.93, -78.62];
    const root = document.querySelector("[data-operational-map]");
    if (!root || typeof L === "undefined") return;

    const form = root.querySelector("[data-map-filters]");
    const unitList = root.querySelector("[data-unit-list]");
    const emergencyList = root.querySelector("[data-emergency-list]");
    const sync = root.querySelector("[data-sync-state]");
    const syncTime = root.querySelector("[data-sync-time]");
    const errorBox = root.querySelector("[data-map-error]");
    const clearRoute = root.querySelector("[data-clear-route]");
    const counts = {
        emergencies: root.querySelector("[data-emergency-count]"),
        units: root.querySelector("[data-unit-count]"),
        waiting: root.querySelector("[data-waiting-count]"),
    };
    const map = L.map("operational-map", { zoomControl: true }).setView(COTOPAXI_CENTER, 10);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    const markers = new Map();
    let routeLayer = null;
    let refreshTimer = null;
    let initialFitDone = false;

    const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
    })[character]);
    const filteredQuery = () => {
        const params = new URLSearchParams(new FormData(form));
        [...params.entries()].forEach(([key, value]) => { if (!value) params.delete(key); });
        return params.toString();
    };
    const ageText = (age) => {
        if (age.segundos == null) return age.etiqueta;
        if (age.segundos < 60) return `${age.etiqueta} · hace ${age.segundos} s`;
        return `${age.etiqueta} · hace ${Math.floor(age.segundos / 60)} min`;
    };
    const setSync = (state, label) => {
        sync.dataset.state = state;
        sync.querySelector("strong").textContent = label;
        if (state === "updated") syncTime.textContent = `Última sincronización: ${new Date().toLocaleTimeString()}`;
    };
    const iconFor = (feature) => {
        const p = feature.properties;
        const ageClass = p.clase === "unidad" ? ` map-marker--${p.antiguedad.codigo}` : "";
        return L.divIcon({
            className: "", iconSize: [34, 34], iconAnchor: [17, 17],
            html: `<span class="map-marker map-marker--${p.clase}${ageClass}" aria-hidden="true">${p.clase === "emergencia" ? "!" : "U"}</span>`,
        });
    };
    const popupFor = (feature) => {
        const p = feature.properties;
        if (p.clase === "emergencia") return `<strong>${escapeHtml(p.codigo)} · ${escapeHtml(p.tipo)}</strong><br>${escapeHtml(p.prioridad_etiqueta)} · ${escapeHtml(p.estado_etiqueta)}<br>${escapeHtml(p.direccion)}<br>${escapeHtml(p.institucion)} · ${p.unidades} unidad(es)<br><a href="${escapeHtml(p.detalle_url)}">Ver detalle</a>`;
        return `<strong>${escapeHtml(p.unidad)} · ${escapeHtml(p.tipo_recurso)}</strong><br>Emergencia ${escapeHtml(p.emergencia)}<br>${escapeHtml(p.estado_etiqueta)} · ${escapeHtml(p.estacion)}<br>${escapeHtml(ageText(p.antiguedad))}<br><a href="${escapeHtml(p.detalle_url)}">Ver emergencia</a>`;
    };
    const updateMarkers = (features) => {
        const visible = new Set();
        const bounds = [];
        features.filter((feature) => feature.geometry?.type === "Point").forEach((feature) => {
            const id = feature.id;
            const [lon, lat] = feature.geometry.coordinates;
            visible.add(id); bounds.push([lat, lon]);
            let marker = markers.get(id);
            if (!marker) {
                marker = L.marker([lat, lon], { icon: iconFor(feature), keyboard: true }).addTo(map);
                markers.set(id, marker);
            } else {
                marker.setLatLng([lat, lon]); marker.setIcon(iconFor(feature));
            }
            marker.bindPopup(popupFor(feature));
        });
        markers.forEach((marker, id) => { if (!visible.has(id)) { map.removeLayer(marker); markers.delete(id); } });
        if (!initialFitDone && bounds.length) { map.fitBounds(bounds, { padding: [35, 35], maxZoom: 13 }); initialFitDone = true; }
    };
    const element = (tag, text, className) => {
        const node = document.createElement(tag); if (text != null) node.textContent = text; if (className) node.className = className; return node;
    };
    const actionButton = (label, action, disabled = false) => {
        const button = element("button", label); button.type = "button"; button.disabled = disabled; button.addEventListener("click", action); return button;
    };
    const renderUnits = (features) => {
        unitList.replaceChildren();
        if (!features.length) { unitList.append(element("p", "No hay unidades desplegadas con los filtros seleccionados.")); return; }
        features.forEach((feature) => {
            const p = feature.properties;
            const card = element("article", null, "map-card");
            card.append(element("h3", `${p.unidad} · ${p.tipo_recurso}`));
            card.append(element("p", `Emergencia ${p.emergencia} · ${p.estado_etiqueta}`));
            card.append(element("p", `${p.institucion} · ${p.estacion}`, "map-card__meta"));
            const gps = element("span", ageText(p.antiguedad), `gps-label gps-label--${p.antiguedad.codigo}`); card.append(gps);
            if (p.precision != null) card.append(element("p", `Precisión: ± ${Math.round(p.precision)} m`, "map-card__meta"));
            const actions = element("div", null, "card-actions");
            actions.append(actionButton("Centrar unidad", () => { const marker = markers.get(feature.id); if (marker) { map.setView(marker.getLatLng(), Math.max(map.getZoom(), 14)); marker.openPopup(); } }, !feature.geometry));
            actions.append(actionButton("Mostrar recorrido", () => showRoute(p.recorrido_url)));
            card.append(actions); unitList.append(card);
        });
    };
    const renderEmergencies = (features) => {
        emergencyList.replaceChildren();
        if (!features.length) { emergencyList.append(element("p", "No existen emergencias activas en su ámbito.")); return; }
        features.forEach((feature) => {
            const p = feature.properties;
            const card = element("article", null, "map-card");
            card.append(element("h3", `${p.codigo} · ${p.tipo}`));
            card.append(element("p", `${p.prioridad_etiqueta} · ${p.estado_etiqueta}`));
            card.append(element("p", `${p.direccion} · ${p.estacion}`, "map-card__meta"));
            card.append(element("p", feature.geometry ? `${p.unidades} unidad(es) desplegada(s)` : "Sin ubicación geográfica registrada", "gps-label"));
            emergencyList.append(card);
        });
    };
    const showRoute = async (url) => {
        setSync("updating", "Consultando recorrido");
        try {
            const response = await fetch(url, { credentials: "same-origin" });
            if (response.status === 401) { clearInterval(refreshTimer); setSync("error", "La sesión expiró"); return; }
            if (response.status === 403) { clearInterval(refreshTimer); setSync("error", "Autorización revocada"); return; }
            if (!response.ok) throw new Error("route");
            const feature = await response.json();
            if (routeLayer) map.removeLayer(routeLayer);
            routeLayer = feature.geometry ? L.geoJSON(feature, { style: { color: "#a15c00", weight: 5 } }).addTo(map) : null;
            clearRoute.hidden = !routeLayer;
            if (routeLayer) map.fitBounds(routeLayer.getBounds(), { padding: [30, 30], maxZoom: 15 });
            setSync("updated", feature.properties.cantidad_puntos ? `Recorrido: ${feature.properties.cantidad_puntos} puntos` : "Sin recorrido disponible");
        } catch (_error) { setSync("error", "No fue posible cargar el recorrido"); }
    };
    const refresh = async () => {
        setSync("updating", "Actualizando"); errorBox.hidden = true;
        try {
            const query = filteredQuery();
            const response = await fetch(`${root.dataset.dataUrl}${query ? `?${query}` : ""}`, { credentials: "same-origin" });
            if (response.status === 401) { clearInterval(refreshTimer); setSync("error", "La sesión expiró"); errorBox.hidden = false; return; }
            if (response.status === 403) { clearInterval(refreshTimer); setSync("error", "Autorización revocada"); errorBox.hidden = false; return; }
            if (!response.ok) throw new Error("data");
            const data = await response.json();
            const emergencies = data.features.filter((feature) => feature.properties.clase === "emergencia");
            const units = data.features.filter((feature) => feature.properties.clase === "unidad");
            updateMarkers(data.features); renderUnits(units); renderEmergencies(emergencies);
            counts.emergencies.textContent = String(emergencies.length); counts.units.textContent = String(units.length);
            counts.waiting.textContent = String(units.filter((item) => !item.geometry).length);
            setSync("updated", "Actualizado");
        } catch (_error) { setSync("error", "Error de conexión"); errorBox.hidden = false; }
    };
    const schedule = () => { clearInterval(refreshTimer); if (!document.hidden) refreshTimer = setInterval(refresh, REFRESH_INTERVAL_MS); };
    form.addEventListener("submit", (event) => { event.preventDefault(); initialFitDone = false; refresh(); });
    form.addEventListener("reset", () => setTimeout(() => { initialFitDone = false; refresh(); }, 0));
    root.querySelector("[data-map-retry]").addEventListener("click", refresh);
    clearRoute.addEventListener("click", () => { if (routeLayer) map.removeLayer(routeLayer); routeLayer = null; clearRoute.hidden = true; });
    document.addEventListener("visibilitychange", () => { schedule(); if (!document.hidden) refresh(); });
    refresh(); schedule();
})();
