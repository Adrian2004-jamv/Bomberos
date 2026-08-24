# Filtros y paginación del registro de incidentes

## Alcance

Los tres filtros del registro de incidentes —fase operativa, búsqueda y etapa documental— pasaron de JavaScript a la base de datos, y el listado se paginó. No se tocaron los modelos, las migraciones ni el mapa que encabeza la página.

`lista` hacía `list(_emergencias_permitidas(request.user))`: traía a memoria todas las emergencias del ámbito y las dibujaba en una sola tabla. `registro_incidentes.js` ocultaba después las filas que no coincidían. Con pocos incidentes funciona; con el padrón de una provincia, la página crece sin límite y cada filtro sigue costando el listado completo.

Ese diseño además es incompatible con paginar: un filtro que actúa sobre las filas ya dibujadas solo puede filtrar la página visible, de modo que buscar un incidente devolvería «sin coincidencias» cuando está en la página siguiente.

## Consulta

`_emergencias_permitidas` gana una segunda anotación, `formularios_registrados`, que suma los formularios genéricos y el SCI-211. Antes ese total se calculaba en Python al preparar cada fila; ahora la etapa documental es un filtro, y resolverlo en Python obligaría a traer el padrón completo para descartar casi todo.

Agrupar por la anotación hace que Django deje de aplicar el orden declarado en el modelo, y paginar sin orden explícito devuelve resultados inestables entre páginas. Por eso la consulta ordena de forma explícita por fecha de reporte y clave.

| Filtro | Resolución |
| --- | --- |
| Fase | Incluye o excluye los estados cerrada y cancelada. |
| Búsqueda | `icontains` sobre código, tipo, estación y dirección. |
| Etapa SCI | Compara `formularios_registrados` contra cero, doce o el intervalo intermedio. |

La búsqueda cubre además la etiqueta del estado. El estado se guarda como clave —`en_atencion`—, así que el término se traduce primero a las claves cuyas etiquetas lo contienen y se agrega esa condición a la consulta.

**Limitación conocida:** la búsqueda distingue acentos. El filtro anterior normalizaba en JavaScript, de modo que «estacion» encontraba «Estación»; ahora no. Resolverlo requiere la extensión `unaccent` de PostgreSQL y una migración que la cree, y se prefirió no añadir esa dependencia al despliegue en el mismo cambio.

## Conteos

Los números que rotulan los botones de fase se calculan sobre la consulta ya filtrada por texto y etapa, pero antes de aplicar la fase. Son una promesa de lo que se verá al pulsarlos: si mostraran el total del ámbito, buscar «forestal» dejaría botones que anuncian veinte incidentes y entregan tres.

## Interfaz

Las fases pasaron de botones a enlaces, porque ahora cambian la dirección de la página. Cada uno conserva los demás filtros mediante `querystring_sin_fase`, y la fase activa viaja en un campo oculto del formulario para que buscar no la pierda.

`registro_incidentes.js` se redujo a una sola función: enviar el formulario al cambiar la etapa documental, para no obligar a pulsar «Filtrar». El resto del guion desapareció junto con los atributos `data-phase`, `data-document-stage` y `data-search` de cada fila, que ya no lee nadie.

Cuando una combinación de filtros no devuelve nada, la página lo dice y ofrece limpiarlos; el mensaje de «no existen emergencias registradas» queda reservado para un ámbito realmente vacío. La paginación reutiliza la convención de `operaciones`: parámetro `pagina`, contexto `querystring` y un fragmento propio que apunta al ancla del registro.

## Verificación

- `python manage.py check`: sin problemas.
- `python manage.py makemigrations --check`: sin cambios pendientes.
- `python manage.py test emergencias.test_registro_incidentes`: 29 pruebas correctas.
- `python manage.py test`: 300 pruebas correctas.
- Comprobación manual sobre la base local: `?q=incendio&fase=curso` devuelve los dos incidentes con los conteos correspondientes y ofrece «Limpiar»; `?q=terremoto` muestra «Sin coincidencias» y no el mensaje de ámbito vacío.
