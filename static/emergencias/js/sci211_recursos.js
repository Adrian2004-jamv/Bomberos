/* Cuadrícula de recursos del SCI-211.

   Hace dos cosas: completar los datos que se derivan del recurso elegido en
   cuanto se elige, y agregar filas sin recargar la página.

   El servidor vuelve a derivar esos datos al guardar, de modo que lo que se
   escribe aquí es una ayuda visual y no la fuente del dato: sin JavaScript el
   formulario sigue funcionando igual. */
(() => {
    "use strict";

    const contenedor = document.querySelector("[data-resource-cards]");
    const plantilla = document.querySelector("[data-resource-template]");
    const boton = document.querySelector("[data-add-resource]");
    const totalDeFormularios = document.querySelector("#id_registros-TOTAL_FORMS")
        || document.querySelector('input[name$="-TOTAL_FORMS"]');
    if (!contenedor || !plantilla || !boton || !totalDeFormularios) return;

    const DERIVADOS = {clase: "clase", tipo: "tipo", institucion: "institucion", matricula: "matricula"};

    const completarDerivados = (select) => {
        const tarjeta = select.closest("[data-resource-card]");
        if (!tarjeta) return;
        const opcion = select.selectedOptions[0];
        Object.values(DERIVADOS).forEach((marca) => {
            const campo = tarjeta.querySelector(`[data-derivado="${marca}"]`);
            if (!campo) return;
            const valor = opcion ? opcion.dataset[marca] : "";
            if (valor) {
                campo.value = valor;
                // El servidor los vuelve a derivar; se muestran solo de lectura
                // para que nadie los contradiga a mano sin darse cuenta.
                campo.readOnly = true;
                campo.classList.add("is-derived");
            } else {
                campo.readOnly = false;
                campo.classList.remove("is-derived");
            }
        });
    };

    const renumerar = () => {
        contenedor.querySelectorAll("[data-resource-card]").forEach((tarjeta, indice) => {
            const numero = tarjeta.querySelector("[data-resource-number]");
            if (numero) numero.textContent = indice + 1;
        });
    };

    boton.addEventListener("click", () => {
        const indice = Number.parseInt(totalDeFormularios.value, 10);
        const copia = plantilla.content.cloneNode(true);
        const tarjeta = copia.querySelector("[data-resource-card]");
        // El formulario vacío del formset usa __prefix__ donde va el número.
        tarjeta.innerHTML = tarjeta.innerHTML.replace(/__prefix__/g, indice);
        contenedor.appendChild(tarjeta);
        totalDeFormularios.value = indice + 1;
        renumerar();
        const select = tarjeta.querySelector("[data-recurso-inventario]");
        if (select) select.focus();
    });

    contenedor.addEventListener("change", (evento) => {
        if (evento.target.matches("[data-recurso-inventario]")) {
            completarDerivados(evento.target);
        }
    });

    // Al abrir un borrador ya guardado, los campos derivados vienen llenos: se
    // marcan igual para que se lean como lo que son.
    contenedor.querySelectorAll("[data-recurso-inventario]").forEach((select) => {
        if (select.value) completarDerivados(select);
    });

    // ---------------------------------------------------------------
    // Plegado de cada recurso
    //
    // «Guardar» no envía nada por su cuenta: la cuadrícula viaja entera
    // al pulsar «Guardar borrador». Lo que hace es dar por terminada esa
    // tarjeta y minimizarla, para que con cinco recursos anotados la
    // pantalla siga siendo legible.
    // ---------------------------------------------------------------

    const resumirTarjeta = (tarjeta) => {
        const select = tarjeta.querySelector("[data-recurso-inventario]");
        const elegido = select && select.selectedIndex > 0
            ? select.options[select.selectedIndex].textContent.trim()
            : "";
        const matricula = tarjeta.querySelector("[data-derivado='matricula']");
        const escrito = matricula ? matricula.value.trim() : "";
        return elegido || escrito || "Recurso sin identificar";
    };

    const plegar = (tarjeta, plegada) => {
        const campos = tarjeta.querySelector("[data-resource-fields]");
        const resumen = tarjeta.querySelector("[data-resource-summary]");
        const guardar = tarjeta.querySelector("[data-resource-save]");
        const editar = tarjeta.querySelector("[data-resource-edit]");
        if (!campos || !resumen) return;
        resumen.textContent = resumirTarjeta(tarjeta);
        campos.hidden = plegada;
        resumen.hidden = !plegada;
        if (guardar) guardar.hidden = plegada;
        if (editar) editar.hidden = !plegada;
    };

    const casillaDeBorrado = (tarjeta) =>
        tarjeta.querySelector("input[type='checkbox'][name$='-DELETE']");

    // Al volver de guardar, lo ya anotado se muestra plegado: la pantalla queda
    // lista para el siguiente recurso en vez de repetir seis campos llenos.
    if (contenedor.hasAttribute("data-plegar-guardados")) {
        contenedor.querySelectorAll("[data-resource-card]").forEach((tarjeta) => {
            const select = tarjeta.querySelector("[data-recurso-inventario]");
            if (select && select.value) plegar(tarjeta, true);
        });
    }

    contenedor.addEventListener("click", (evento) => {
        const tarjeta = evento.target.closest("[data-resource-card]");
        if (!tarjeta) return;

        if (evento.target.closest("[data-resource-edit]")) {
            plegar(tarjeta, false);
            return;
        }
        if (evento.target.closest("[data-resource-delete]")) {
            const casilla = casillaDeBorrado(tarjeta);
            if (casilla) casilla.checked = true;
            // Nunca se quita la tarjeta del documento. Los formularios del
            // formset van numerados de corrido, y borrar uno del medio dejaría
            // un hueco: Django leería hasta el hueco y perdería los siguientes.
            // Una tarjeta nueva se vacía —un formulario en blanco se ignora— y
            // una ya guardada lleva marcada su casilla DELETE.
            tarjeta.querySelectorAll("input, select, textarea").forEach((campo) => {
                if (campo.name.endsWith("-DELETE") || campo.name.endsWith("-id")) return;
                if (campo.type === "checkbox" || campo.type === "radio") {
                    campo.checked = false;
                } else {
                    campo.value = "";
                }
            });
            tarjeta.classList.add("resource-card--removed");
            plegar(tarjeta, true);
            tarjeta.querySelector("[data-resource-summary]").textContent = "Recurso eliminado";
            tarjeta.querySelectorAll("[data-resource-save], [data-resource-edit], [data-resource-delete]")
                .forEach((boton) => { boton.hidden = true; });
        }
    });
})();
