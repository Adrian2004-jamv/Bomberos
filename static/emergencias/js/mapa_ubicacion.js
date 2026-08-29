/* Selector de ubicación del formulario de emergencias.

   Los campos de latitud y longitud siguen siendo la fuente del dato: el mapa
   solo los escribe. Se mantienen visibles y editables porque a veces la
   coordenada llega por radio y se teclea, y porque sin JavaScript el formulario
   debe seguir sirviendo. */
(() => {
    "use strict";

    const contenedor = document.querySelector("[data-location-picker]");
    const lienzo = document.querySelector("[data-location-map]");
    const campoLatitud = document.querySelector("[data-ubicacion-latitud]");
    const campoLongitud = document.querySelector("[data-ubicacion-longitud]");
    if (!contenedor || !lienzo || !campoLatitud || !campoLongitud || typeof L === "undefined") return;

    const pista = contenedor.querySelector("[data-location-hint]");
    const botonQuitar = contenedor.querySelector("[data-location-clear]");

    // Centro aproximado de la provincia de Cotopaxi, para cuando aún no hay dato.
    const CENTRO_COTOPAXI = [-0.93, -78.62];
    const DECIMALES = 6;

    const leerCampos = () => {
        const latitud = Number.parseFloat(campoLatitud.value);
        const longitud = Number.parseFloat(campoLongitud.value);
        if (!Number.isFinite(latitud) || !Number.isFinite(longitud)) return null;
        if (latitud < -90 || latitud > 90 || longitud < -180 || longitud > 180) return null;
        return [latitud, longitud];
    };

    const mapa = L.map(lienzo.id, {zoomControl: true});
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(mapa);

    const icono = L.divIcon({
        className: "",
        iconSize: [38, 38],
        iconAnchor: [19, 19],
        html: '<span class="incident-map-marker incident-map-marker--emergency" role="img" aria-label="Ubicación de la emergencia"><i class="ti ti-map-pin" aria-hidden="true"></i></span>',
    });

    let marca = null;

    const escribirCampos = (posicion) => {
        campoLatitud.value = posicion.lat.toFixed(DECIMALES);
        campoLongitud.value = posicion.lng.toFixed(DECIMALES);
        // Avisa a cualquier validación que escuche los campos.
        [campoLatitud, campoLongitud].forEach((campo) => {
            campo.dispatchEvent(new Event("change", {bubbles: true}));
        });
    };

    const actualizarPista = () => {
        const posicion = leerCampos();
        if (posicion) {
            pista.textContent = `Ubicación seleccionada: ${posicion[0].toFixed(DECIMALES)}, ${posicion[1].toFixed(DECIMALES)}. Arrastre la marca para ajustarla.`;
            botonQuitar.hidden = false;
        } else {
            pista.textContent = "Pulse sobre el mapa para situar la emergencia; puede arrastrar la marca para ajustarla.";
            botonQuitar.hidden = true;
        }
    };

    const situar = (posicion, {centrar = false} = {}) => {
        if (marca) {
            marca.setLatLng(posicion);
        } else {
            marca = L.marker(posicion, {icon: icono, draggable: true}).addTo(mapa);
            marca.on("dragend", () => {
                escribirCampos(marca.getLatLng());
                actualizarPista();
            });
        }
        if (centrar) mapa.setView(posicion, Math.max(mapa.getZoom(), 14));
        actualizarPista();
    };

    const quitar = () => {
        if (marca) {
            mapa.removeLayer(marca);
            marca = null;
        }
        campoLatitud.value = "";
        campoLongitud.value = "";
        actualizarPista();
    };

    const inicial = leerCampos();
    mapa.setView(inicial || CENTRO_COTOPAXI, inicial ? 15 : 10);
    if (inicial) situar(L.latLng(inicial[0], inicial[1]));
    actualizarPista();

    mapa.on("click", (evento) => {
        // Los campos van primero: «situar» refresca la leyenda leyendolos, y si
        // se dibujara la marca antes seguiria anunciando que no hay ubicacion.
        escribirCampos(evento.latlng);
        situar(evento.latlng);
    });

    // Escribir a mano sigue funcionando: la marca sigue a los campos.
    [campoLatitud, campoLongitud].forEach((campo) => {
        campo.addEventListener("input", () => {
            const posicion = leerCampos();
            if (posicion) {
                situar(L.latLng(posicion[0], posicion[1]), {centrar: true});
            } else if (marca) {
                mapa.removeLayer(marca);
                marca = null;
                actualizarPista();
            }
        });
    });

    botonQuitar.addEventListener("click", quitar);

    // El contenedor puede medir cero al construirse si el navegador aún está
    // ajustando la rejilla del formulario; Leaflet necesita saberlo después.
    window.requestAnimationFrame(() => mapa.invalidateSize());
})();
