"use strict";

// Fondo cartografico compartido por los cuatro mapas del sistema.
//
// No se usan los servidores de mosaicos de openstreetmap.org: los mantienen
// voluntarios, su politica de uso no contempla aplicaciones en produccion y el
// 30/09/2026 empezaron a devolver 403 con la imagen «Access blocked» en lugar
// del mapa. Un mapa que puede apagarse sin aviso no sirve para despachar
// unidades. CARTO sirve los mismos datos de OpenStreetMap sobre infraestructura
// pensada para esto, sin clave de acceso, a cambio de citar a ambos.
//
// La atribucion es obligatoria y por eso vive aqui y no en cada mapa: antes
// estaba repetida en tres archivos y faltaba en el cuarto.
window.fondoDelMapa = function (mapa) {
    return L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        {
            subdomains: "abcd",
            maxZoom: 20,
            attribution:
                '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' +
                ' &middot; &copy; <a href="https://carto.com/attributions">CARTO</a>',
        },
    ).addTo(mapa);
};
