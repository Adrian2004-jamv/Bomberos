"use strict";

// Fondo cartográfico compartido por los cuatro mapas del sistema.
//
// Historia corta de por qué está aquí y no repetido en cada mapa, que es como
// estaba: uno de los cuatro pedía los mosaicos sin declarar su procedencia, y
// la atribución es obligatoria en todos los proveedores. Repetida en tres
// sitios, era cuestión de tiempo que faltara en el cuarto.
//
// Sobre el proveedor, dos intentos y lo que se aprendió de cada uno:
//
//   - openstreetmap.org sirve los mosaicos con servidores de voluntarios. Su
//     politica no contempla una aplicacion en produccion y bloquea las
//     direcciones de centros de datos, que es por donde sale cualquier VPN. El
//     mapa se apagaba segun quien mirara y desde donde.
//   - basemaps.cartocdn.com responde 200 con una marca de agua de 2 KB que dice
//     «API KEY REQUIRED». Ya no es gratuito sin registro.
//
// Esri sirve estos mosaicos sin clave y sin depender de voluntarios. Aun asi es
// un tercero: la unica forma de que el mapa no dependa de nadie es servir los
// mosaicos desde este mismo sistema, que es lo que hace falta para trabajar sin
// conexion. Cuando eso exista, se cambia esta sola linea.
window.fondoDelMapa = function (mapa) {
    return L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        {
            maxZoom: 19,
            attribution:
                'Mosaicos &copy; <a href="https://www.esri.com/">Esri</a>' +
                ' &middot; datos de <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> y otros',
        },
    ).addTo(mapa);
};
