(() => {
    "use strict";

    // Un campo de fecha y hora obliga a teclear día, mes, año, hora y minuto
    // con el formato exacto. En una emergencia, y con un teléfono en la mano,
    // eso se equivoca o se deja en blanco. Casi siempre el dato que se quiere
    // es «ahora», así que se ofrece de un toque.
    const dosDigitos = (numero) => String(numero).padStart(2, "0");

    const valorLocal = (campo) => {
        const momento = new Date();
        const fecha = `${momento.getFullYear()}-${dosDigitos(momento.getMonth() + 1)}`
            + `-${dosDigitos(momento.getDate())}`;
        const hora = `${dosDigitos(momento.getHours())}:${dosDigitos(momento.getMinutes())}`;
        return campo.type === "time" ? hora : `${fecha}T${hora}`;
    };

    const ponerAhora = (campo) => {
        campo.value = valorLocal(campo);
        // Los guiones que rellenan otros campos a partir de este deben enterarse.
        campo.dispatchEvent(new Event("input", {bubbles: true}));
        campo.dispatchEvent(new Event("change", {bubbles: true}));
    };

    const crearBoton = (campo) => {
        const boton = document.createElement("button");
        boton.type = "button";
        boton.className = "campo-ahora";
        boton.textContent = "Ahora";
        boton.title = "Poner la fecha y la hora de este momento";
        boton.setAttribute("aria-label", "Poner la fecha y hora actuales");
        boton.addEventListener("click", () => ponerAhora(campo));
        return boton;
    };

    const equipar = (raiz) => {
        raiz.querySelectorAll(
            'input[type="datetime-local"]:not([data-con-ahora]), input[type="time"]:not([data-con-ahora])'
        ).forEach((campo) => {
            if (campo.disabled || campo.readOnly) return;
            campo.dataset.conAhora = "1";
            const envoltura = document.createElement("span");
            envoltura.className = "campo-con-ahora";
            campo.parentNode.insertBefore(envoltura, campo);
            envoltura.appendChild(campo);
            envoltura.appendChild(crearBoton(campo));
        });
    };

    equipar(document);

    // Las filas que se agregan después —otro recurso, otra actividad— también
    // lo llevan, sin tener que avisar a este guion desde cada pantalla.
    new MutationObserver((cambios) => {
        cambios.forEach((cambio) => cambio.addedNodes.forEach((nodo) => {
            if (nodo.nodeType === 1) equipar(nodo);
        }));
    }).observe(document.body, {childList: true, subtree: true});
})();
