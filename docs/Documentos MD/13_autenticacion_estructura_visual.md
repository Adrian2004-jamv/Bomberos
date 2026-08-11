# Prompt 13: autenticación y estructura visual base

## Auditoría previa

Se confirmó que Git estaba limpio y sincronizado, no existían rutas propias de `usuarios` o `core`, la página principal no estaba protegida y las carpetas globales de plantillas y archivos estáticos estaban preparadas pero sin interfaz. La base local contenía 0 usuarios.

## Configuración de autenticación

Se configuraron nombres de ruta en `settings.py`:

```python
LOGIN_URL = "usuarios:login"
LOGIN_REDIRECT_URL = "core:inicio"
LOGOUT_REDIRECT_URL = "usuarios:login"
```

`usuarios/urls.py` utiliza `LoginView` y `LogoutView` de Django. El inicio de sesión redirige al centro de gestión y el cierre vuelve al login.

El logout solo acepta POST. El formulario incluye CSRF; un GET devuelve 405 y un POST sin token es rechazado cuando se aplica la verificación CSRF.

## Página inicial protegida

`core/urls.py` expone la ruta raíz con nombre `core:inicio`. La vista usa `login_required`, por lo que una persona no autenticada es enviada al login conservando el parámetro `next`.

La página muestra bienvenida, usuario, estación e institución cuando existen y una descripción temporal de los módulos futuros. No muestra estadísticas reales.

## Plantillas

`base.html` define los bloques `title`, `page_title`, `content`, `extra_css` y `extra_js`.

Los componentes compartidos se separaron en:

- `componentes/sidebar.html`: navegación principal y módulos futuros deshabilitados;
- `componentes/navbar.html`: usuario, estación, menú móvil y formulario POST de logout;
- `componentes/mensajes.html`: mensajes de Django con región accesible.

`usuarios/login.html` contiene etiquetas accesibles, autocompletado apropiado, CSRF, errores comprensibles y diseño adaptable sin credenciales de demostración.

## Estilos y JavaScript

- `variables.css`: colores, radios, sombras, tipografía y medidas compartidas.
- `base.css`: normalización, estructura general, accesibilidad y contenido.
- `componentes.css`: sidebar, navbar, botones, mensajes, tarjetas y responsive.
- `login.css`: composición y formulario exclusivo de acceso.
- `app.js`: apertura y cierre accesible del menú en pantallas pequeñas.

Se usó una identidad sobria azul oscuro con rojo y naranja como acentos, tipografía del sistema y focos visibles. No se añadieron frameworks ni dependencias.

## Rutas globales

`config/urls.py` incluye ordenadamente administración, usuarios y core. Los archivos multimedia continúan sirviéndose únicamente cuando `DEBUG` es verdadero.

## Pruebas

Se añadieron ocho pruebas para redirección de visitante, acceso autenticado, formulario con CSRF, credenciales incorrectas, redirección de login, logout POST, rechazo de logout GET y rechazo de POST sin CSRF.

## Archivos creados o modificados

- `config/settings.py`
- `config/urls.py`
- `core/views.py`
- `core/urls.py`
- `core/tests.py`
- `usuarios/urls.py`
- `usuarios/tests.py`
- `templates/base.html`
- `templates/core/inicio.html`
- `templates/usuarios/login.html`
- `templates/componentes/sidebar.html`
- `templates/componentes/navbar.html`
- `templates/componentes/mensajes.html`
- `static/css/variables.css`
- `static/css/base.css`
- `static/css/componentes.css`
- `static/css/login.css`
- `static/js/app.js`
- `docs/Documentos MD/README.md`
- `docs/Documentos MD/13_autenticacion_estructura_visual.md`

## Verificación

```text
System check identified no issues (0 silenced).
Found 8 test(s).
Ran 8 tests
OK
No changes detected
```

Django encontró los cinco archivos estáticos y resolvió las rutas de login, logout e inicio. No se desarrollaron pantallas funcionales de módulos.
