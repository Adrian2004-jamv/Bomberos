# Exportación de datos

## Alcance

Se habilitó la exportación del inventario y del registro de incidentes. El inventario usa los botones de DataTables; los incidentes se exportan desde el servidor. No se tocaron los modelos ni las migraciones.

Hasta ahora ningún módulo permitía llevarse los datos: la única salida era imprimir desde el navegador.

## Por qué dos mecanismos

DataTables exporta lo que el navegador tiene cargado. Eso determina dónde sirve:

| Listado | Filas en el navegador | Exportación |
| --- | --- | --- |
| `inventario/lista` | todas, sin `Paginator` | DataTables |
| `emergencias/lista` | doce por página | Servidor |
| `inventario/historial` | veinte por página | Pendiente |
| `operaciones/evaluaciones` | quince por página | Pendiente |

En el inventario la tabla llega completa y DataTables la pagina en el navegador, de modo que sus botones alcanzan todas las filas. En los listados paginados en el servidor, en cambio, la tabla solo tiene la página visible: un botón de DataTables produciría un archivo incompleto **sin avisar de que lo es**, que es peor que no tener exportación. Por eso el registro de incidentes se exporta desde una vista propia.

## Inventario

Se incorporaron `Buttons 3.2.4`, sus módulos HTML5 e impresión, y `JSZip 3.10.1`, que es lo que habilita el archivo de Excel. Todo queda en `static/vendor/`, junto a la copia de DataTables que el proyecto ya traía; nada se carga desde una red externa.

La configuración tiene tres decisiones que conviene no perder:

1. `modifier.page` vale `"all"`. Es el valor por omisión, pero se declara de forma explícita porque es justo lo que distingue un archivo completo de uno recortado a la página visible.
2. La exportación omite la primera columna, que despliega el detalle en pantallas angostas, y la última, que trae los botones de acción. Ninguna es información del recurso.
3. `format.body` lee `data-export` o `data-search` de cada celda antes de recurrir a su texto. Sin eso, la columna del recurso concatena código, nombre y marca sin separación; con eso sale «ERA-01 · Equipo ERA 01».

El CSV se emite con separador `;` y marca de orden de bytes: sin ella, Excel abre el archivo con la codificación del sistema y rompe los acentos.

Los botones respetan la búsqueda y los filtros de columna que el usuario tenga aplicados, de modo que se exporta lo que se está viendo, no siempre el padrón entero.

## Incidentes

`exportar` reutiliza `_consulta_filtrada` y `_aplicar_fase`, los mismos ayudantes que arma el listado, para que el archivo contenga exactamente lo que la pantalla dice estar mostrando. Ignora `pagina` a propósito: el listado se pagina, el archivo no.

Se transmite con `StreamingHttpResponse` sobre `.iterator()`, de modo que el padrón no se arma entero en memoria. Las diecisiete columnas incluyen identificación, prioridad, estado, fase, fechas, institución, estación, dirección, coordenadas, unidades desplegadas y activas, avance de formularios, estado del SCI-211 y responsable del registro.

El alcance es el de siempre: `_emergencias_permitidas` acota por estación responsable, así que la exportación nunca alcanza a otra institución. Un perfil de consulta puede exportar su ámbito, porque exportar es leer.

## Verificación

- `python manage.py check`: sin problemas.
- `python manage.py makemigrations --check`: sin cambios pendientes.
- `python manage.py test emergencias.test_exportacion`: 18 pruebas correctas.
- `python manage.py test`: 319 pruebas correctas.
- Comprobación manual en el navegador: JSZip y Buttons cargan, aparecen los cuatro botones y `exportData` con la configuración del proyecto devuelve las 21 filas del inventario —no las 10 de la página— con la columna del recurso legible; al buscar «autobomba» el archivo baja a 7. La respuesta de `/emergencias/exportar/` llega con `text/csv`, adjunta y con la marca de orden de bytes (`EF BB BF`) al inicio.
