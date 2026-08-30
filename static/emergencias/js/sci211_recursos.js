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
})();
