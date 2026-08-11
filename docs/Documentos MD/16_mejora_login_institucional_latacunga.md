# Mejora institucional del inicio de sesión

## Objetivo

Rediseñar la pantalla de acceso del sistema con la identidad del Cuerpo de Bomberos Latacunga, manteniendo intacta la autenticación de Django y garantizando una presentación adaptable y accesible.

## Cambios realizados

- Se adoptó un panel institucional con degradado rojo `#7F0D14`, `#A80F18` y `#C51622`.
- Se actualizó la identidad textual a `Cuerpo de Bomberos Latacunga` e `Inventarios y Capacidades Operativas`.
- Se ajustaron el título, la descripción, los indicadores de módulos y el lema inferior.
- Se modernizaron campos, alertas, botón principal, estados de foco y autocompletado.
- Se añadió un control accesible para mostrar u ocultar la contraseña.
- El control de contraseña utiliza posicionamiento interno reforzado y una transición animada entre los iconos de ojo abierto y cerrado.
- Se redujeron las animaciones a una entrada breve y se respetó `prefers-reduced-motion`.
- Se agregaron puntos de adaptación para 1024, 768, 480 y 375 píxeles.

## Archivos modificados

- `templates/usuarios/login.html`
- `static/css/login.css`
- `static/js/app.js`

## Elementos preservados

- Ruta y vista de inicio de sesión.
- Nombres, identificadores y atributos de los campos.
- Token CSRF y parámetro `next`.
- Lógica de errores y autenticación de Django.
- Modelos, migraciones, permisos y base de datos.
