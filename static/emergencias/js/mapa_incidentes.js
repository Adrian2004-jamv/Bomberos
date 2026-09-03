(() => {
    "use strict";
    const root = document.querySelector("[data-incident-map]");
    if (!root || typeof L === "undefined") return;
    const status = document.querySelector("[data-incident-map-status]");
    const map = L.map(root.id, {zoomControl: true, attributionControl: false}).setView([-0.93, -78.62], 10);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
    }).addTo(map);
    const layer = L.layerGroup().addTo(map);
    let fitted = false;

    // El servidor entrega los incidentes que pasan el filtro del registro. El
    // mapa sigue dibujandolos todos, pero apaga los que quedan fuera para que
    // se vea el contexto sin confundirlo con el resultado de la consulta.
    const hayFiltros = root.dataset.incidentMapFiltered === "1";
    let idsEnFiltro = new Set();
    try {
        idsEnFiltro = new Set(JSON.parse(root.dataset.incidentMapIds || "[]"));
    } catch (_error) {
        idsEnFiltro = new Set();
    }
    const dentroDelFiltro = (properties) => {
        if (!hayFiltros) return true;
        const id = properties.clase === "emergencia" ? properties.id : properties.emergencia_id;
        return id != null && idsEnFiltro.has(id);
    };
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
    const listaUnidades = document.querySelector("[data-map-units]");

    // La leyenda decia «Unidad operativa» y nada mas. Con varias unidades en
    // escena eso no dice cual esta donde: se enumeran las que hay dibujadas,
    // con su tipo, su emergencia y si esta transmitiendo.
    const listarUnidades = (features) => {
        if (!listaUnidades) return;
        const unidades = features.filter((f) => f.properties.clase === "unidad");
        if (!unidades.length) {
            listaUnidades.innerHTML = '<li class="map-units__empty">Ninguna unidad desplegada.</li>';
            return;
        }
        listaUnidades.innerHTML = unidades.map((feature) => {
            const p = feature.properties;
            const transmite = feature.geometry
                ? '<em class="map-units__live">transmitiendo</em>'
                : '<em class="map-units__idle">sin ubicación en vivo</em>';
            return `<li><i class="incident-legend-icon incident-legend-icon--unit ti ti-firetruck" aria-hidden="true"></i>`
                + `<span><strong>${escapeHtml(p.unidad)}</strong>`
                + `<small>${escapeHtml(p.tipo_recurso)} · ${escapeHtml(p.emergencia)}</small>`
                + `${transmite}</span></li>`;
        }).join("");
    };

    const refresh = async () => {
        status.textContent = "Actualizando mapa…";
        try {
            const response = await fetch(root.dataset.dataUrl, {credentials: "same-origin"});
            if (!response.ok) throw new Error("map-data");
            const data = await response.json();
            const bounds = [];
            let totalDibujado = 0;
            layer.clearLayers();
            data.features.filter((feature) => feature.geometry?.type === "Point").forEach((feature) => {
                const [longitude, latitude] = feature.geometry.coordinates;
                const marker = feature.properties.clase === "emergencia"
                    ? emergencyIcon(feature.properties.tipo)
                    : {kind: "unit", icon: "ti-firetruck", label: "Unidad operativa"};
                const activo = dentroDelFiltro(feature.properties);
                const apagado = activo ? "" : " incident-map-marker--muted";
                const nota = activo ? "" : " (fuera del filtro)";
                const etiqueta = escapeHtml(marker.label + nota);
                const icon = L.divIcon({className:"",iconSize:[38,38],iconAnchor:[19,19],html:`<span class="incident-map-marker incident-map-marker--${marker.kind}${apagado}" role="img" aria-label="${etiqueta}" title="${etiqueta}"><i class="ti ${marker.icon}" aria-hidden="true"></i></span>`});
                L.marker([latitude, longitude], {icon, zIndexOffset: activo ? 500 : 0})
                    .bindPopup(popup(feature)).addTo(layer);
                // El encuadre automatico solo considera lo que pasa el filtro:
                // de lo contrario un incidente lejano y apagado alejaria el mapa.
                if (activo) bounds.push([latitude, longitude]);
                totalDibujado += 1;
            });
            listarUnidades(data.features);
            if (!fitted && bounds.length) { map.fitBounds(bounds, {padding:[35,35],maxZoom:13}); fitted = true; }
            status.dataset.state = "ready";
            status.textContent = hayFiltros
                ? `${bounds.length} de ${totalDibujado} ubicación(es) dentro del filtro`
                : `${totalDibujado} ubicación(es) visible(s)`;
        } catch (_error) {
            status.dataset.state = "error";
            status.textContent = "No fue posible actualizar el mapa";
        }
    };
    refresh();
    const timer = window.setInterval(refresh, 30000);
    window.addEventListener("pagehide", () => window.clearInterval(timer), {once:true});
})();
