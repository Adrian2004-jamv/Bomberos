# Emergencias y despliegue inicial de unidades

## Alcance

Se implementaron los modelos, servicios, permisos, administración y pruebas necesarios para registrar emergencias y despachar unidades del inventario. No se incorporaron GPS, mapas, WebSockets, formularios SCI, PWA ni gestión de personal.

## Modelos

### TipoRecurso

Se agregó `es_unidad_desplegable`, que permite identificar qué tipos representan vehículos o unidades móviles sin crear un inventario separado.

### Emergencia

Registra código único, tipo, descripción, prioridad, estado, fechas, dirección, coordenadas opcionales, estación responsable, usuario y auditoría. Valida rangos geográficos y que el cierre no sea anterior al reporte.

### DespliegueUnidad

Relaciona la emergencia con un `Recurso`, conserva la estación de procedencia y registra responsable, estado, asignación, salida, llegada, retorno y observaciones. Una restricción única parcial impide dos despliegues activos para la misma unidad.

## Servicios

- `desplegar_unidad`: valida emergencia, unidad, disponibilidad, tipo y alcance; cambia la disponibilidad a asignada usando el servicio de inventario.
- `cambiar_estado_despliegue`: aplica transiciones permitidas y registra fechas sin sobrescribir las anteriores.
- `finalizar_despliegue` y `cancelar_despliegue`: cierran el despliegue y liberan la unidad si continúa activa y operativa.

Todas las operaciones críticas usan `transaction.atomic`. Si falla la creación del despliegue, también se revierten el cambio de disponibilidad y su historial.

## Permisos

- Superusuario, administrador y responsable provincial: alcance general.
- Responsable institucional: estaciones de su institución.
- Responsable de estación: su estación.
- Encargado de inventario y operador de consulta: consulta, sin despacho.

## Concurrencia

Se utiliza `select_for_update`, validación de despliegue activo y restricción parcial de base de datos. SQLite no implementa bloqueo de filas como PostgreSQL, aunque serializa escrituras; al migrar de motor, el mismo servicio aprovechará el bloqueo real sin cambiar su API.

## Migraciones

- `inventario.0003_tiporecurso_es_unidad_desplegable`.
- `emergencias.0001_initial`.

Ambas fueron aplicadas sin eliminar la base ni migraciones históricas.

## Verificación

- `python manage.py check`: sin problemas.
- `python manage.py makemigrations --check`: sin cambios pendientes.
- `python manage.py test emergencias`: 18 pruebas correctas.
- `python manage.py test inventario`: 20 pruebas correctas.
- `python manage.py test`: 92 pruebas correctas.
