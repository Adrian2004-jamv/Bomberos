# Despacho de unidades y ciclo operativo del incidente

## Alcance

Se expuso en la aplicación web el despacho de unidades y el cambio de estado de la emergencia, que hasta ahora solo existían como servicios. No se tocaron los modelos, las migraciones, los formularios SCI, el mapa ni la aplicación web progresiva.

El punto de partida era una asimetría: `emergencias/services.py` ya contenía `desplegar_unidad`, `cambiar_estado_despliegue`, `finalizar_despliegue` y `cancelar_despliegue`, probados y con bloqueo de fila, pero ninguna vista los llamaba. En el panel de administración `DespliegueUnidad` es de solo lectura y `Emergencia` bloquea `estado` y `fecha_cierre` al editar, de modo que el único código capaz de crear un despliegue era `cargar_escenarios_sci`. En consecuencia, un incidente registrado por un usuario no podía recibir unidades, se quedaba en «Reportada» de forma permanente y el rastreo GPS, el mapa operativo y el autocompletado del SCI-211 solo funcionaban sobre los datos de demostración.

## Servicios agregados

### `cambiar_estado_emergencia`

Aplica el ciclo `reportada → en atención → controlada → cerrada`, con `cancelada` disponible mientras el incidente no esté controlado y el regreso de `controlada` a `en atención` cuando la situación se reactiva. Los estados terminales no admiten salida.

Cerrar o cancelar exige que ningún despliegue siga activo. Sin esa condición la unidad quedaría marcada como asignada a un incidente terminado y el inventario dejaría de reflejar la realidad; el mensaje de error nombra las unidades pendientes. Al terminar se escribe `fecha_cierre` con la hora del sistema.

La restricción `emergencias_cierre_no_anterior_reporte` obliga a que ese sello no sea anterior al reporte. Una emergencia registrada con fecha futura no podría cerrarse nunca, así que el servicio lo detecta y `EmergenciaForm` rechaza fechas futuras con un minuto de tolerancia, porque el navegador envía la hora con precisión de minuto.

### `unidades_desplegables`

Reproduce en una consulta las condiciones que `desplegar_unidad` comprueba fila a fila: tipo desplegable, recurso activo, operativo, disponible, dentro del ámbito del usuario y sin despliegue activo. Sirve para que el formulario ofrezca solo lo que se puede despachar; la decisión sigue siendo del servicio, porque entre que se dibuja la lista y se envía el formulario otra estación puede tomar la unidad.

### `transiciones_disponibles`

Traduce cualquiera de los dos mapas de transiciones a pares valor/etiqueta. La interfaz dibuja únicamente los botones que el servicio aceptaría, en lugar de ofrecer todos los estados y fallar después.

## Vistas y rutas

| Ruta | Vista | Función |
| --- | --- | --- |
| `<pk>/editar/` | `editar` | Corrige tipo, descripción, prioridad, dirección y coordenadas de un incidente en curso. |
| `<pk>/estado/` | `cambiar_estado` | Avanza el ciclo operativo. Solo POST. |
| `<pk>/despachar/` | `despachar` | Envía una unidad disponible al incidente. |
| `despliegues/<pk>/estado/` | `actualizar_despliegue` | Mueve el despliegue por sus estados. Solo POST. |

`editar` deja fuera código, estación responsable, fecha de reporte y estado: son la identidad y la trazabilidad del registro, y el estado tiene su propio servicio. Una emergencia terminada no se edita.

Las cuatro vistas resuelven el alcance con `estacion_autorizada`, que ya combina el rol y las estaciones permitidas. Los despliegues se filtran por su estación de procedencia, así que un despliegue de otra institución devuelve 404 en lugar de 403: el usuario no debe saber que existe.

## Interfaz

El detalle de la emergencia incorpora un panel de ciclo operativo con el estado actual, los botones de transición disponibles y el aviso de cuántas unidades siguen en el incidente. La tabla de despliegues pasó de una sola acción de GPS a mostrar estado con color, tiempos de asignación, salida, llegada y cierre, y los botones de transición de cada fila.

`templates/emergencias/formulario.html` ahora sirve tanto el registro como la edición: el título, la introducción, el texto del botón y la ruta de cancelación llegan por contexto, y la navegación de acciones aparece solo al crear.

El selector de unidades identifica cada recurso por su estación, porque el código interno solo es único dentro de una estación y un usuario provincial vería varias «AB-01» indistinguibles. Cuando no queda ninguna unidad disponible, la pantalla explica las condiciones del despacho en lugar de mostrar un desplegable vacío.

## Panel de administración

`DespliegueUnidad` sigue siendo de solo lectura. Crearlo desde el administrador saltaría las validaciones y el bloqueo de fila del servicio, y dejaría el inventario sin el cambio de disponibilidad correspondiente.

## Verificación

- `python manage.py check`: sin problemas.
- `python manage.py makemigrations --check`: sin cambios pendientes.
- `python manage.py test emergencias.test_despacho`: 32 pruebas correctas.
- `python manage.py test`: 233 pruebas correctas.
- Comprobación manual sobre la base local: el panel de ciclo operativo ofrece «En atención» y «Cancelada» a un incidente reportado y no «Cerrada»; con una unidad asignada advierte que debe cerrarse el despliegue primero; la fila de despliegue muestra «En ruta», «Cancelada» y «GPS».
