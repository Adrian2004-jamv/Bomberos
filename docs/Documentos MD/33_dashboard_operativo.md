# Dimensión operativa del dashboard

## Alcance

Se incorporaron al dashboard los indicadores de incidentes y unidades, un tablero de incidentes en curso y los accesos rápidos correspondientes. No se tocaron los modelos, las migraciones ni el cálculo de inventario y capacidades que ya existía.

`construir_dashboard` agregaba únicamente recursos y evaluaciones de capacidad. Un responsable que abría la pantalla principal no veía cuántos incidentes tenía abiertos, cuántas unidades estaban fuera ni qué documentación faltaba, siendo la respuesta a emergencias el núcleo del sistema. La actividad reciente mezclaba cambios de recurso y evaluaciones, pero ignoraba las emergencias y los despliegues.

## Indicadores

`_resumen_operativo` devuelve cuatro cifras, todas acotadas a `estaciones_permitidas`:

| Indicador | Definición |
| --- | --- |
| Incidentes en curso | Emergencias que no están cerradas ni canceladas. |
| Unidades desplegadas | Despliegues en un estado activo, no los históricos del incidente. |
| Incidentes terminados | Emergencias cerradas o canceladas. |
| En curso sin SCI-211 | Incidentes abiertos sin ese formulario. |

El último indicador merece explicación: el SCI-211 es el registro maestro de recursos del incidente y alimenta a los demás formularios, de modo que un incidente abierto sin él es documentación pendiente y no un dato neutro.

Las emergencias se acotan por `estacion_responsable` y los despliegues por `estacion_procedencia`, igual que hacen las vistas de cada módulo. Una unidad prestada a otra institución cuenta para la estación que la aporta, que es quien la tiene comprometida.

## Tablero de incidentes en curso

`_incidentes_en_curso` devuelve hasta seis incidentes abiertos, del más reciente al más antiguo, con las unidades que tienen encima y si ya existe su SCI-211. Ambos datos se anotan en la misma consulta —`Count` con filtro y `Exists`—; resolverlos por fila obligaría a una consulta por incidente al pintar la tabla.

Cada tarjeta muestra prioridad, código, tipo, estación, dirección, estado, unidades activas, aviso de documentación pendiente, hora del reporte y un enlace al detalle.

## Actividad reciente

`_actividad_operativa` suma emergencias y despliegues a la mezcla que ya ordenaba cambios de recurso y evaluaciones. El límite de ocho entradas no cambió: ahora compiten cuatro fuentes por el mismo espacio, lo que refleja mejor qué pasó de verdad en el ámbito del usuario.

## Permisos

La sección operativa completa —indicadores, tablero y acceso rápido al mapa— aparece solo con `puede_consultar_emergencias`, y el acceso para registrar un incidente exige además `puede_gestionar_emergencias`. Una cuenta sin ámbito institucional no ve nada de esto, igual que ya ocurría con inventario y capacidades.

## Verificación

- `python manage.py check`: sin problemas.
- `python manage.py makemigrations --check`: sin cambios pendientes.
- `python manage.py test dashboard`: 24 pruebas correctas.
- `python manage.py test`: 271 pruebas correctas.
- Comprobación manual sobre la base local: con dos incidentes abiertos y un despliegue activo, los indicadores muestran 2, 1, 0 y 0, el tablero lista ambos incidentes con sus unidades y la actividad reciente intercala incidentes y despliegues con los cambios de inventario.
