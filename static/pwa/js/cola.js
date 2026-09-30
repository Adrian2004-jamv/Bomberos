"use strict";

// Cola de envíos que sobrevive a la falta de señal.
//
// El service worker guarda lecturas, no escrituras: sin esto, todo lo que el
// bombero registre fuera de cobertura se pierde al cerrar la pestaña. Vive en
// IndexedDB y no en memoria justamente por eso — una unidad puede pasar media
// hora en una quebrada y el teléfono bloquearse entre medio.
//
// Cada entrada lleva su propia dirección y su forma de envío. Es deliberado: si
// cada pantalla vaciara la cola a su manera, la consola del GPS acabaría
// mandando un formulario SCI a la dirección de las posiciones.
window.colaDeEnvios = (() => {
    const BASE = "bomberos-cola";
    const ALMACEN = "envios";
    // Un turno largo sin señal cabe de sobra: a una posición cada quince
    // segundos son más de veinte horas. El tope existe para no llenar el
    // teléfono si algo va mal, y descarta lo más viejo, que es lo menos útil.
    const MAXIMO = 5000;
    const ACCESO = "/usuarios/iniciar-sesion/";

    let conexion = null;
    let vaciando = false;

    const abrir = () => {
        if (conexion) return conexion;
        conexion = new Promise((resolver, rechazar) => {
            if (!("indexedDB" in window)) {
                rechazar(new Error("Este navegador no guarda envíos sin conexión."));
                return;
            }
            const solicitud = indexedDB.open(BASE, 1);
            solicitud.onupgradeneeded = () => {
                const base = solicitud.result;
                if (!base.objectStoreNames.contains(ALMACEN)) {
                    base.createObjectStore(ALMACEN, { keyPath: "id", autoIncrement: true });
                }
            };
            solicitud.onsuccess = () => resolver(solicitud.result);
            solicitud.onerror = () => rechazar(solicitud.error);
        });
        return conexion;
    };

    // Se resuelve cuando la transacción termina, no cuando la petición
    // responde: hasta ese momento IndexedDB todavía puede abortarla.
    const enTransaccion = async (modo, operacion) => {
        const base = await abrir();
        return new Promise((resolver, rechazar) => {
            const transaccion = base.transaction(ALMACEN, modo);
            let solicitud;
            try {
                solicitud = operacion(transaccion.objectStore(ALMACEN));
            } catch (error) {
                rechazar(error);
                return;
            }
            transaccion.oncomplete = () => resolver(
                solicitud && "result" in solicitud ? solicitud.result : undefined
            );
            transaccion.onerror = () => rechazar(transaccion.error);
            transaccion.onabort = () => rechazar(transaccion.error);
        });
    };

    const listar = () => enTransaccion("readonly", (almacen) => almacen.getAll());
    const contar = () => enTransaccion("readonly", (almacen) => almacen.count());
    const olvidar = (identificador) =>
        enTransaccion("readwrite", (almacen) => { almacen.delete(identificador); });

    const recortar = async () => {
        const cuantos = await contar();
        if (cuantos <= MAXIMO) return;
        let porBorrar = cuantos - MAXIMO;
        await enTransaccion("readwrite", (almacen) => {
            const cursor = almacen.openCursor();
            cursor.onsuccess = () => {
                const actual = cursor.result;
                if (!actual || porBorrar <= 0) return;
                actual.delete();
                porBorrar -= 1;
                actual.continue();
            };
        });
    };

    // `envio` es {url, tipo, cuerpo, titulo}. `tipo` vale "json" para las
    // posiciones del GPS y "formulario" para lo que se escribe en pantalla.
    const guardar = async (envio) => {
        await enTransaccion("readwrite", (almacen) => {
            almacen.add({ ...envio, guardado: Date.now() });
        });
        await recortar();
        avisar();
    };

    const testigoCsrf = () => document.cookie.split("; ")
        .find((dato) => dato.startsWith("csrftoken="))?.split("=")[1] || "";

    // El testigo se toma en el momento del envío y no del guardado: el que se
    // escribió en la página puede llevar horas ahí, y Django acepta el de la
    // cabecera. Así un formulario guardado por la mañana se envía por la tarde.
    const entregar = (envio) => fetch(envio.url, {
        method: "POST",
        credentials: "same-origin",
        headers: envio.tipo === "json"
            ? { "Content-Type": "application/json", "X-CSRFToken": testigoCsrf() }
            : { "Content-Type": "application/x-www-form-urlencoded", "X-CSRFToken": testigoCsrf() },
        body: envio.tipo === "json" ? JSON.stringify(envio.cuerpo) : envio.cuerpo,
    });

    const CONSERVAR = "conservar";
    const DESCARTAR = "descartar";
    const DETENER = "detener";

    const veredicto = (respuesta) => {
        // Acabar en la pantalla de acceso significa que la sesión caducó
        // mientras no había señal. Lo guardado no se toca: descartarlo sería
        // perder en silencio el trabajo de alguien que hizo todo bien.
        if (respuesta.redirected && respuesta.url.includes(ACCESO)) return DETENER;
        if (respuesta.status === 403) return DETENER;
        if (respuesta.ok) return DESCARTAR;
        // Un rechazo por el contenido no mejora con el tiempo. Reintentarlo
        // para siempre atasca todo lo que venga detrás.
        if ([400, 409, 413, 422].includes(respuesta.status)) return DESCARTAR;
        return CONSERVAR;
    };

    const enviarPendientes = async () => {
        if (vaciando) return { entregados: 0, restantes: await contar(), sesionCaducada: false };
        vaciando = true;
        let entregados = 0;
        let sesionCaducada = false;
        try {
            for (const envio of await listar()) {
                let decision = CONSERVAR;
                try {
                    decision = veredicto(await entregar(envio));
                } catch (_error) {
                    decision = CONSERVAR;  // sigue sin haber red
                }
                if (decision === DETENER) { sesionCaducada = true; break; }
                if (decision === CONSERVAR) break;
                await olvidar(envio.id);
                entregados += 1;
            }
        } finally {
            vaciando = false;
        }
        avisar();
        return { entregados, restantes: await contar(), sesionCaducada };
    };

    const oyentes = [];
    const alCambiar = (oyente) => { oyentes.push(oyente); };
    const avisar = async () => {
        let cuantos = 0;
        try { cuantos = await contar(); } catch (_error) { return; }
        oyentes.forEach((oyente) => oyente(cuantos));
    };

    return { guardar, enviarPendientes, pendientes: contar, alCambiar };
})();
