(() => {
    "use strict";
    const root = document.querySelector("[data-incident-map]");
    if (!root || typeof L === "undefined") return;
    const status = document.querySelector("[data-incident-map-status]");
    const map = L.map(root.id, {zoomControl: true}).setView([-0.93, -78.62], 10);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    const layer = L.layerGroup().addTo(map);
    let fitted = false;
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[character]);
    const normalise = (value) => String(value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    const emergencyIcon = (type) => {
        const value = normalise(type);
        if (value.includes("forest")) return {kind: "forest", icon: "ti-trees", label: "Incendio forestal"};
        if (value.includes("incend") || value.includes("fuego")) return {kind: "fire", icon: "ti-flame", label: "Incendio"};
        if (value.includes("rescat")) return {kind: "rescue", icon: "ti-lifebuoy", label: "Rescate"};
        if (value.includes("accident") || value.includes("transit") || value.includes("choque")) return {kind: "traffic", icon: "ti-car-crash", label: "Accidente vehicular"};
        if (value.includes("inund") || value.includes("desbord") || value.includes("agua")) return {kind: "flood", icon: "ti-flood", label: "Inundación"};
        if (value.includes("material") || value.includes("quim") || value.includes("hazmat") || value.includes("gas")) return {kind: "hazmat", icon: "ti-biohazard", label: "Materiales peligrosos"};
        if (value.includes("medic") || value.includes("salud") || value.includes("prehospital")) return {kind: "medical", icon: "ti-ambulance", label: "Emergencia médica"};
        return {kind: "emergency", icon: "ti-alert-triangle", label: "Emergencia"};
    };
    const popup = (feature) => {
        const p = feature.properties;
        if (p.clase === "emergencia") return `<strong>${escapeHtml(p.codigo)} · ${escapeHtml(p.tipo)}</strong><br>${escapeHtml(p.estado_etiqueta)}<br>${escapeHtml(p.direccion)}<br><a href="${escapeHtml(p.detalle_url)}">Ver registro</a>`;
        return `<strong>${escapeHtml(p.unidad)}</strong><br>Incidente ${escapeHtml(p.emergencia)}<br>${escapeHtml(p.estado_etiqueta)} · ${escapeHtml(p.estacion)}`;
    };
    const refresh = async () => {
        status.textContent = "Actualizando mapa…";
        try {
            const response = await fetch(root.dataset.dataUrl, {credentials: "same-origin"});
            if (!response.ok) throw new Error("map-data");
            const data = await response.json();
            const bounds = [];
            layer.clearLayers();
            data.features.filter((feature) => feature.geometry?.type === "Point").forEach((feature) => {
                const [longitude, latitude] = feature.geometry.coordinates;
                const marker = feature.properties.clase === "emergencia"
                    ? emergencyIcon(feature.properties.tipo)
                    : {kind: "unit", icon: "ti-firetruck", label: "Unidad operativa"};
                const icon = L.divIcon({className:"",iconSize:[38,38],iconAnchor:[19,19],html:`<span class="incident-map-marker incident-map-marker--${marker.kind}" role="img" aria-label="${escapeHtml(marker.label)}" title="${escapeHtml(marker.label)}"><i class="ti ${marker.icon}" aria-hidden="true"></i></span>`});
                L.marker([latitude, longitude], {icon}).bindPopup(popup(feature)).addTo(layer);
                bounds.push([latitude, longitude]);
            });
            if (!fitted && bounds.length) { map.fitBounds(bounds, {padding:[35,35],maxZoom:13}); fitted = true; }
            status.dataset.state = "ready";
            status.textContent = `${bounds.length} ubicación(es) visible(s)`;
        } catch (_error) {
            status.dataset.state = "error";
            status.textContent = "No fue posible actualizar el mapa";
        }
    };
    refresh();
    const timer = window.setInterval(refresh, 30000);
    window.addEventListener("pagehide", () => window.clearInterval(timer), {once:true});
})();
