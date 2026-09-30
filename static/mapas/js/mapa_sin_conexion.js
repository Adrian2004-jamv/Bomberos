"use strict";

// Descarga por adelantado los mosaicos de la zona para que el mapa funcione sin
// señal.
//
// El service worker ya guarda los que se van viendo, pero eso solo sirve para lo
// que alguien miró antes de perder cobertura. En un incidente el mapa se lleva a
// donde no se ha estado nunca, así que hay que traerlos mientras hay red.
//
// No se descarga la provincia entera a propósito: son miles de imágenes y varios
// cientos de megabytes. Se acota al área de Latacunga, que es donde el sistema
// está en piloto, y se le dice al usuario cuántas son antes de empezar.
(() => {
    const control = document.querySelector("[data-mapa-sin-conexion]");
    if (!control) return;

    const boton = control.querySelector("[data-descargar-mapa]");
    const borrar = control.querySelector("[data-borrar-mapa]");
    const estado = control.querySelector("[data-estado-mapa]");
    const barra = control.querySelector("[data-avance-mapa]");

    // Recuadro que cubre Latacunga y sus alrededores con holgura: unos 20 km de
    // lado, centrado en las tres estaciones del cantón.
    const ZONA = { norte: -0.84, sur: -1.02, oeste: -78.70, este: -78.52 };
    const ZOOM_MINIMO = 12;
    const ZOOM_MAXIMO = 16;
    const A_LA_VEZ = 6;

    const aMosaicoX = (longitud, zoom) =>
        Math.floor((longitud + 180) / 360 * Math.pow(2, zoom));

    const aMosaicoY = (latitud, zoom) => {
        const radianes = latitud * Math.PI / 180;
        return Math.floor(
            (1 - Math.asinh(Math.tan(radianes)) / Math.PI) / 2 * Math.pow(2, zoom)
        );
    };

    const direccionDe = (zoom, x, y) =>
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/"
        + `${zoom}/${y}/${x}`;

    const listaDeMosaicos = () => {
        const lista = [];
        for (let zoom = ZOOM_MINIMO; zoom <= ZOOM_MAXIMO; zoom += 1) {
            const desdeX = aMosaicoX(ZONA.oeste, zoom);
            const hastaX = aMosaicoX(ZONA.este, zoom);
            const desdeY = aMosaicoY(ZONA.norte, zoom);
            const hastaY = aMosaicoY(ZONA.sur, zoom);
            for (let x = desdeX; x <= hastaX; x += 1) {
                for (let y = desdeY; y <= hastaY; y += 1) lista.push(direccionDe(zoom, x, y));
            }
        }
        return lista;
    };

    const decir = (texto) => { if (estado) estado.textContent = texto; };

    const avanzar = (hechos, total) => {
        if (barra) {
            barra.value = hechos;
            barra.max = total;
            barra.hidden = false;
        }
    };

    const descargar = async () => {
        const mosaicos = listaDeMosaicos();
        const megas = Math.round(mosaicos.length * 25 / 1024);
        const sigue = window.confirm(
            `Se van a descargar ${mosaicos.length} imágenes del mapa de Latacunga, `
            + `alrededor de ${megas} MB. Quedan guardadas en este equipo y el mapa `
            + "funcionará sin internet. Conviene hacerlo con wifi. ¿Continuar?"
        );
        if (!sigue) return;

        boton.disabled = true;
        let hechos = 0;
        let fallidos = 0;
        decir("Descargando el mapa de la zona…");

        const pendientes = mosaicos.slice();
        const obrero = async () => {
            while (pendientes.length) {
                const direccion = pendientes.shift();
                try {
                    // «no-cors» porque los mosaicos vienen de otro origen: no se
                    // puede leer la respuesta, pero el service worker la guarda
                    // y el mapa la dibuja igual.
                    await fetch(direccion, { mode: "no-cors", cache: "default" });
                } catch (_error) {
                    fallidos += 1;
                }
                hechos += 1;
                if (hechos % 10 === 0 || !pendientes.length) avanzar(hechos, mosaicos.length);
            }
        };

        await Promise.all(Array.from({ length: A_LA_VEZ }, obrero));

        boton.disabled = false;
        decir(
            fallidos
                ? `Mapa descargado con ${fallidos} imagen(es) que no llegaron. `
                  + "Repita la descarga con mejor señal para completarlo."
                : "Mapa de Latacunga descargado. Ya funciona sin internet.",
        );
    };

    const olvidar = () => {
        if (!navigator.serviceWorker?.controller) {
            decir("No hay nada guardado todavía.");
            return;
        }
        navigator.serviceWorker.controller.postMessage({ type: "CLEAR_MAP_CACHE" });
        if (barra) barra.hidden = true;
        decir("Se borró el mapa guardado en este equipo.");
    };

    if (boton) boton.addEventListener("click", descargar);
    if (borrar) borrar.addEventListener("click", olvidar);
})();
