# Interfaz responsive del módulo instituciones

## Objetivo

Permitir consultar y administrar Cuerpos de Bomberos y estaciones desde una interfaz propia, con control de acceso en servidor y diseño adaptable desde 320 píxeles.

## Implementación

- Se crearon formularios `ModelForm` para Cuerpos de Bomberos y estaciones.
- La relación entre estación y Cuerpo de Bomberos se obtiene exclusivamente desde la URL.
- Los intentos de enviar `cuerpo_bomberos` manualmente son rechazados con respuesta 400.
- Se crearon rutas de listado, detalle, creación y edición.
- Se añadió paginación de diez instituciones por página.
- Se añadieron mensajes de éxito después de crear o actualizar registros.
- No se implementó eliminación.

## Reglas de acceso

- Superusuarios, `Administrador del sistema` y `Responsable provincial` pueden consultar, crear y editar todo.
- Los demás usuarios autenticados solo ven el Cuerpo de Bomberos y la estación asociados a su cuenta.
- Los usuarios sin estación ven un estado vacío y no acceden al detalle de instituciones ajenas.
- Las restricciones se aplican en las vistas, independientemente de la visibilidad de los botones.

## Interfaz

- El listado utiliza tarjetas adaptables, evitando tablas comprimidas.
- El detalle separa información institucional, contacto y estaciones.
- Los formularios emplean una columna en móvil y dos columnas desde 576 píxeles.
- Las estaciones se distribuyen en una, dos o tres columnas según el espacio.
- Las acciones ocupan todo el ancho en teléfonos para facilitar la interacción táctil.
- Se reutilizan el menú lateral, barra superior, mensajes y JavaScript compartidos.

## Archivos creados

- `instituciones/forms.py`
- `instituciones/permissions.py`
- `instituciones/urls.py`
- `templates/instituciones/lista.html`
- `templates/instituciones/detalle.html`
- `templates/instituciones/formulario_cuerpo.html`
- `templates/instituciones/formulario_estacion.html`
- `static/instituciones/css/instituciones.css`

## Archivos modificados

- `instituciones/views.py`
- `instituciones/tests.py`
- `config/urls.py`
- `templates/componentes/sidebar.html`

## Verificación visual

El navegador integrado no estuvo disponible. El CSS fue revisado estructuralmente para 320, 375, 480, 768, 1024 y 1440 píxeles. La comprobación visual manual debe confirmar ausencia de desplazamiento horizontal, apertura del menú, legibilidad, tarjetas y formularios en esos tamaños.
