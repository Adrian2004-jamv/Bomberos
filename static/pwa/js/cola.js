"use strict";

// Cola de envíos que sobrevive a la falta de señal.
//
// El service worker guarda lecturas, no escrituras: sin esto, todo lo que el
// bombero registre fuera de cobertura se pierde al cerrar la pestaña. La cola
// vive en IndexedDB y no en memoria justamente por eso — una unidad puede pasar
// media hora en una quebrada y el teléfono bloquearse entre medio.
//
// No resuelve conflictos ni reordena por reloj: reenvía en el mismo orden en
// que se guardó y deja que el servidor decida. Las posiciones se identifican
// por la hora del aparato, así que reenviar dos veces no duplica el recorrido.
window.colaDeEnvios = (() => {
    const BASE = "bomberos-cola";
    const ALMACEN = "envios";
    // Un turno largo sin señal cabe de sobra: a una posición cada quince
    // segundos son más de veinte horas. El tope existe para no llenar el
    // teléfono si algo va mal, y descarta lo más viejo, que es lo menos útil.
    const MAXIMO = 5000;

    let conexion = null;

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
    // responde: hasta ese momento IndexedDB puede todavía abortarla.
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

    const guardar = async (envio) => {
        await enTransaccion("readwrite", (almacen) => {
            almacen.add({ ...envio, guardado: Date.now() });
        });
        await recortar();
    };

    // Vacía la cola en orden. `entregar` devuelve true si el servidor se quedó
    // con el envío —o lo rechazó por algo que reintentar no arregla— y false si
    // no hubo forma de llegar hasta él, en cuyo caso se detiene y se conserva el
    // resto: seguir intentando sin red solo gasta batería.
    const vaciar = async (entregar) => {
        const guardados = await listar();
        let entregados = 0;
        for (const envio of guardados) {
            let aceptado = false;
            try {
                aceptado = await entregar(envio);
            } catch (_error) {
                aceptado = false;
            }
            if (!aceptado) break;
            await olvidar(envio.id);
            entregados += 1;
        }
        return { entregados, restantes: guardados.length - entregados };
    };

    return { guardar, vaciar, pendientes: contar };
})();
