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
                const kind = feature.properties.clase === "emergencia" ? "emergency" : "unit";
                const label = kind === "emergency" ? "!" : "U";
                const icon = L.divIcon({className:"",iconSize:[34,34],iconAnchor:[17,17],html:`<span class="incident-map-marker incident-map-marker--${kind}" aria-hidden="true">${label}</span>`});
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
