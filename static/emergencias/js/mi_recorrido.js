(() => {
    "use strict";

    const contenedor = document.querySelector("[data-recorrido]");
    if (!contenedor || typeof L === "undefined") return;
    const aviso = document.querySelector("[data-recorrido-aviso]");

    const decir = (texto) => { if (aviso) aviso.textContent = texto; };

    const mapa = L.map(contenedor, { scrollWheelZoom: false });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: "© OpenStreetMap",
    }).addTo(mapa);
    mapa.setView([-0.933, -78.616], 13);

    fetch(contenedor.dataset.recorridoUrl, { credentials: "same-origin" })
        .then((respuesta) => {
            if (!respuesta.ok) throw new Error(respuesta.status);
            return respuesta.json();
        })
        .then((recorrido) => {
            const geometria = recorrido.geometry;
            if (!geometria) { decir("No se registraron posiciones."); return; }
            // El GeoJSON viene en orden longitud/latitud y Leaflet los espera al revés.
            const capa = L.geoJSON(recorrido, {
                style: { color: "#b5121b", weight: 4 },
                pointToLayer: (_, punto) => L.circleMarker(punto, { radius: 6, color: "#b5121b" }),
            }).addTo(mapa);
            mapa.fitBounds(capa.getBounds(), { padding: [30, 30], maxZoom: 17 });
            const total = recorrido.properties.cantidad_puntos;
            decir(`Recorrido con ${total} punto${total === 1 ? "" : "s"} registrado${total === 1 ? "" : "s"}.`);
        })
        .catch(() => decir("No fue posible cargar el recorrido."));
})();
