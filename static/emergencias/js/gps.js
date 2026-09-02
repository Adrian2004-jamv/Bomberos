(() => {
    "use strict";

    const MIN_INTERVAL_MS = 15000;
    const MIN_DISTANCE_METERS = 10;
    const MAX_PENDING_POSITIONS = 5;
    const GEOLOCATION_OPTIONS = { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 };
    const root = document.querySelector("[data-gps-console]");
    if (!root) return;

    const ui = {
        start: root.querySelector("[data-gps-start]"), stop: root.querySelector("[data-gps-stop]"),
        state: root.querySelector("[data-gps-state]"), message: root.querySelector("[data-gps-message]"),
        coordinates: root.querySelector("[data-gps-coordinates]"), accuracy: root.querySelector("[data-gps-accuracy]"),
        speed: root.querySelector("[data-gps-speed]"), time: root.querySelector("[data-gps-time]"), count: root.querySelector("[data-gps-count]"),
    };
    let watchId = null;
    let lastSent = null;
    let sentCount = 0;
    let sending = false;
    const pending = [];

    const csrfToken = () => document.cookie.split("; ").find((item) => item.startsWith("csrftoken="))?.split("=")[1] || "";
    const radians = (degrees) => degrees * Math.PI / 180;
    const distanceMeters = (a, b) => {
        const radius = 6371000;
        const dLat = radians(b.latitud - a.latitud);
        const dLon = radians(b.longitud - a.longitud);
        const value = Math.sin(dLat / 2) ** 2 + Math.cos(radians(a.latitud)) * Math.cos(radians(b.latitud)) * Math.sin(dLon / 2) ** 2;
        return 2 * radius * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
    };
    const setMessage = (text, kind = "info") => { ui.message.textContent = text; ui.message.dataset.kind = kind; };
    const setState = (text, state) => { ui.state.lastChild.textContent = text; ui.state.dataset.state = state; };
    // Avisar al servidor no es opcional: mientras crea que la unidad transmite,
    // el mapa operativo sigue dibujando el último punto como si fuera actual.
    // El recorrido no se toca, solo deja de mostrarse en vivo.
    const avisarDetencion = () => {
        const url = root.dataset.stopUrl;
        if (!url) return;
        // «keepalive» permite que la petición sobreviva al cierre de la pestaña.
        // No se usa sendBeacon porque no admite cabeceras y Django rechazaría
        // la petición por falta del testigo CSRF.
        fetch(url, {
            method: "POST", credentials: "same-origin", keepalive: true,
            headers: { "X-CSRFToken": csrfToken() },
        }).catch(() => {});
    };

    const stop = (message = "Transmisión detenida.", kind = "info") => {
        const transmitia = watchId !== null;
        if (watchId !== null) navigator.geolocation.clearWatch(watchId);
        watchId = null; ui.start.disabled = false; ui.stop.disabled = true;
        if (transmitia) avisarDetencion();
        setState("Transmisión detenida", kind === "error" ? "error" : "stopped"); setMessage(message, kind);
    };

    // Cerrar la pestaña o bloquear el teléfono también apaga el seguimiento.
    window.addEventListener("pagehide", () => { if (watchId !== null) stop(); });
    const payloadFrom = (position) => ({
        latitud: position.coords.latitude, longitud: position.coords.longitude,
        precision: position.coords.accuracy, velocidad: position.coords.speed,
        rumbo: position.coords.heading, altitud: position.coords.altitude,
        fecha_dispositivo: new Date(position.timestamp).toISOString(),
    });
    const shouldSend = (payload) => !lastSent || Date.now() - lastSent.time >= MIN_INTERVAL_MS || distanceMeters(lastSent, payload) >= MIN_DISTANCE_METERS;
    const send = async (payload) => {
        if (sending) { pending.push(payload); if (pending.length > MAX_PENDING_POSITIONS) pending.shift(); return; }
        sending = true;
        try {
            const response = await fetch(root.dataset.registerUrl, {
                method: "POST", credentials: "same-origin",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
                body: JSON.stringify(payload),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                if ([401, 403, 409].includes(response.status)) stop(data.error || "La transmisión ya no está autorizada.", "error");
                else setMessage(data.error || "No fue posible enviar la posición.", "error");
                return;
            }
            lastSent = { ...payload, time: Date.now() }; sentCount += 1;
            ui.coordinates.textContent = `${Number(payload.latitud).toFixed(6)}, ${Number(payload.longitud).toFixed(6)}`;
            const accuracyLevel = payload.precision <= 20 ? "alta" : payload.precision <= 50 ? "moderada" : "baja";
            ui.accuracy.textContent = payload.precision == null ? "No disponible" : `± ${Math.round(payload.precision)} m (${accuracyLevel})`;
            ui.speed.textContent = payload.velocidad == null ? "No disponible" : `${Number(payload.velocidad).toFixed(1)} m/s`;
            ui.time.textContent = new Date(data.fecha_recepcion).toLocaleTimeString(); ui.count.textContent = String(sentCount);
            setState("Transmitiendo", "active");
            setMessage("Última ubicación enviada correctamente.", "success");
        } catch (_error) {
            pending.push(payload); if (pending.length > MAX_PENDING_POSITIONS) pending.shift();
            setState("Envío sin confirmar", "error");
            setMessage("Sin conexión con el servidor. La transmisión no se confirma.", "error");
        } finally {
            sending = false;
            if (watchId !== null && pending.length) send(pending.shift());
        }
    };
    const onPosition = (position) => { const payload = payloadFrom(position); if (shouldSend(payload)) send(payload); };
    const onGeolocationError = (error) => {
        const messages = { 1: "Permiso de ubicación rechazado.", 2: "La ubicación no está disponible.", 3: "Se agotó el tiempo de espera del GPS." };
        stop(messages[error.code] || "No fue posible obtener la ubicación.", "error");
    };
    const start = () => {
        if (!("geolocation" in navigator)) { stop("Este navegador no permite geolocalización.", "error"); return; }
        sentCount = 0; lastSent = null; pending.length = 0; ui.count.textContent = "0";
        ui.start.disabled = true; ui.stop.disabled = false; setState("Esperando ubicación", "stopped");
        setMessage("Solicitando ubicación al dispositivo…");
        watchId = navigator.geolocation.watchPosition(onPosition, onGeolocationError, GEOLOCATION_OPTIONS);
    };
    ui.start.addEventListener("click", start); ui.stop.addEventListener("click", () => stop());
    window.addEventListener("pagehide", () => { if (watchId !== null) navigator.geolocation.clearWatch(watchId); });
})();
