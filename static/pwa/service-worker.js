"use strict";

const CACHE_PREFIX = "bomberos-cotopaxi-pwa-";
// Subir este numero descarta todo lo guardado por la version anterior: el
// detector de «activate» borra las caches cuyo nombre no coincide con esta.
const STATIC_CACHE = `${CACHE_PREFIX}static-v7`;
const OFFLINE_URL = "/sin-conexion/";
const SAFE_ASSETS = [
    OFFLINE_URL,
    "/static/css/variables.css",
    "/static/css/base.css",
    "/static/css/componentes.css",
    "/static/css/login.css",
    "/static/pwa/css/pwa.css",
    "/static/js/app.js",
    "/static/vendor/tabler-icons/tabler-icons.min.css",
    "/static/vendor/tabler-icons/fonts/tabler-icons.woff2",
    "/static/vendor/tom-select-2.6.2.min.js",
    "/static/vendor/tom-select-2.6.2.css",
    "/static/img/logos/Logo.png",
    "/static/pwa/icons/icon-192.png",
    "/static/pwa/icons/icon-512.png",
    "/static/pwa/icons/icon-maskable-512.png",
];
const SENSITIVE_PATHS = [
    "/api/",
    "/emergencias/api/",
    "/mapa/datos/",
    "/mapa/recorridos/",
    "/ws/",
];

const clearSessionCaches = () => caches.keys().then((keys) => Promise.all(
    keys.filter((key) => key.startsWith(`${CACHE_PREFIX}session-`)).map((key) => caches.delete(key)),
));

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(STATIC_CACHE).then((cache) => cache.addAll(SAFE_ASSETS)));
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(keys.filter((key) => key.startsWith(CACHE_PREFIX) && key !== STATIC_CACHE).map((key) => caches.delete(key))))
            .then(() => self.clients.claim()),
    );
});

self.addEventListener("message", (event) => {
    if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
    if (event.data?.type === "CLEAR_SESSION_CACHE") event.waitUntil(clearSessionCaches());
});

self.addEventListener("fetch", (event) => {
    const request = event.request;
    const url = new URL(request.url);

    if (request.method !== "GET") {
        if (url.origin === self.location.origin && url.pathname === "/usuarios/cerrar-sesion/") {
            event.respondWith(fetch(request).then(async (response) => {
                if (response.ok || response.redirected) await clearSessionCaches();
                return response;
            }));
        }
        return;
    }

    if (url.origin !== self.location.origin) return;
    if (SENSITIVE_PATHS.some((prefix) => url.pathname.startsWith(prefix))) return;

    if (request.mode === "navigate") {
        event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_URL)));
        return;
    }

    const safeStaticRequest = url.pathname.startsWith("/static/")
        && ["style", "script", "image", "font"].includes(request.destination);
    if (safeStaticRequest) {
        // Se responde con la copia guardada para no perder el arranque sin
        // conexion, pero se pide igualmente la version del servidor y se
        // reemplaza la copia. Antes se devolvia la del cache y ya: un archivo
        // corregido no volvia a pedirse nunca, y la pantalla seguia mostrando
        // la version anterior aunque el servidor tuviera la nueva.
        event.respondWith(caches.match(request).then((cached) => {
            const desdeLaRed = fetch(request).then((response) => {
                if (response.ok && response.type === "basic") {
                    const copia = response.clone();
                    caches.open(STATIC_CACHE).then((cache) => cache.put(request, copia));
                }
                return response;
            });
            if (!cached) return desdeLaRed;
            // La actualizacion sigue en segundo plano; se retiene el evento para
            // que el navegador no detenga el proceso antes de guardarla, y se
            // absorbe el fallo de red para no dejar un rechazo sin capturar.
            event.waitUntil(desdeLaRed.catch(() => {}));
            return cached;
        }));
    }
});
