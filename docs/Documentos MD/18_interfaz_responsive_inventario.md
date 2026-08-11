# Interfaz responsive del módulo inventario

## Objetivo

Permitir consultar, registrar y editar recursos, actualizar su estado mediante el servicio de trazabilidad y revisar el historial según el alcance institucional del usuario.

## Alcance y permisos

- Superusuarios, `Administrador del sistema` y `Responsable provincial`: acceso global de consulta y gestión.
- `Responsable institucional`: consulta y gestión en todas las estaciones de su Cuerpo de Bomberos.
- `Responsable de estación` y `Encargado de inventario`: consulta y gestión en su estación.
- `Operador de consulta`: acceso de solo lectura en su estación.
- Usuarios sin estación o sin un grupo reconocido: sin acceso al inventario.

Los querysets, formularios, vistas y el servicio de cambio de estado validan estas reglas.

## Formularios

- `RecursoForm` administra únicamente datos descriptivos y limita las estaciones disponibles.
- Durante la edición, la estación queda bloqueada para evitar movimientos no autorizados.
- Estado operativo y disponibilidad no forman parte del formulario descriptivo.
- `CambioEstadoRecursoForm` exige estado, disponibilidad y motivo.

## Trazabilidad

La vista de cambio utiliza exclusivamente `actualizar_estado_recurso`. El servicio bloquea el recurso dentro de una transacción, comprueba el alcance del usuario, actualiza los estados y crea el historial. Si no existen diferencias no se crea un registro nuevo.

## Filtros

El listado permite buscar por código, nombre, marca, modelo o serie y filtrar por Cuerpo de Bomberos, estación, categoría, tipo, estado operativo, disponibilidad y registro activo. La paginación conserva los parámetros activos.

## Responsive Web Design

- Filtros plegables mediante `details` y `summary`.
- Tarjetas legibles para recursos e historial desde 320 píxeles.
- Formularios de una columna en teléfonos y dos columnas con mayor espacio.
- Acciones de ancho completo en teléfonos.
- Estados comunicados con texto, color e indicador visual.
- Reorganización progresiva a 576, 768 y 1024 píxeles.

## Archivos creados

- `inventario/forms.py`
- `inventario/permissions.py`
- `inventario/urls.py`
- `templates/inventario/lista.html`
- `templates/inventario/detalle.html`
- `templates/inventario/formulario_recurso.html`
- `templates/inventario/cambio_estado.html`
- `templates/inventario/historial.html`
- `static/inventario/css/inventario.css`

## Archivos modificados

- `inventario/views.py`
- `inventario/services.py`
- `inventario/tests.py`
- `config/urls.py`
- `templates/componentes/sidebar.html`

## Elementos no implementados

No se añadieron eliminación, mantenimiento, movimientos entre estaciones ni pantallas públicas para categorías o tipos de recursos.
