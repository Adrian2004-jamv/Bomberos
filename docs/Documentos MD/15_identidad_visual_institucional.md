# Identidad visual institucional basada en el emblema

## Objetivo

Integrar el emblema disponible en `static/img/logos/Logo.png` y construir una identidad visual inequívocamente bomberil, moderna y de alto contraste.

## Cambios realizados

- Se incorporó el emblema en la pantalla de inicio de sesión.
- Se incorporó el mismo emblema en la cabecera del menú lateral.
- Se sustituyeron las marcas de texto genéricas `BC` por la imagen institucional.
- Se adoptó una paleta de grafito profundo, blanco y rojo operativo usado de forma controlada.
- Se diseñó una composición sobria de centro de comando, evitando tanto los tonos corporativos genéricos como el exceso de rojo.
- Se incorporaron detalles geométricos discretos y una franja superior roja para reforzar la identidad sin saturar la pantalla.
- Se armonizaron el acceso y el menú interno mediante botones, navegación y estados activos de alto contraste.
- Se añadieron animaciones discretas de entrada, aparición del contenido y respiración del emblema.
- El botón presenta un destello únicamente al interactuar con él y el aviso de error aparece suavemente.
- Se reemplazaron los símbolos de texto por iconos vectoriales y se normalizó el color de los campos autocompletados por Chrome.
- Las animaciones se desactivan automáticamente cuando el sistema del usuario solicita movimiento reducido.
- Se centraron el encabezado, el indicador rojo, la acción principal y el texto de ayuda; las etiquetas y alertas se conservaron a la izquierda para facilitar la lectura.
- La flecha del botón se posicionó de forma independiente para que el texto `Ingresar` quede centrado matemáticamente.
- Se incorporaron los módulos reales y la referencia territorial sin códigos operativos inventados.
- Se incorporó el emblema como marca de agua sutil y se simplificaron todos los bordes a rojo institucional.
- Se eliminó el amarillo de señalización para trabajar exclusivamente con el rojo, negro y blanco presentes en la identidad proporcionada.
- Los textos se alinearon con el tema de tesis: gestión provincial de inventarios y capacidades operativas de los Cuerpos de Bomberos de Cotopaxi.
- Se conservó el comportamiento adaptable para pantallas pequeñas.

## Archivos modificados

- `templates/usuarios/login.html`
- `templates/componentes/sidebar.html`
- `static/css/variables.css`
- `static/css/login.css`
- `static/css/componentes.css`

## Recurso utilizado

- `static/img/logos/Logo.png`

El archivo del emblema se utiliza directamente como recurso estático y no fue modificado.

## Alcance

No se modificaron modelos, migraciones, base de datos, autenticación ni lógica de negocio.
