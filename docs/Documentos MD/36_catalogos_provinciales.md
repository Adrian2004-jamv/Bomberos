# Catálogos provinciales y cierre de la interfaz

## Alcance

Se llevaron a la aplicación los catálogos que hasta ahora solo se editaban desde Django Admin: categorías y tipos de recurso, y capacidades operativas con sus requisitos. Se retiró además el rótulo «Módulos en construcción» del menú lateral. No se tocaron los modelos ni las migraciones.

Los cantones quedan fuera a propósito: son la división política de Cotopaxi, son siete, no cambian, y `cargar_datos_cotopaxi` los deja creados en el despliegue.

## Quién los edita

`inventario.permissions.puede_gestionar_catalogos` equivale a tener alcance provincial: superusuario, «Administrador del sistema» o «Responsable provincial».

El motivo no es jerárquico sino de medición. Categorías, tipos de recurso y capacidades los comparten todos los Cuerpos de Bomberos, y el motor de evaluación compara el inventario de cada estación contra ese catálogo común. Una estación que inventara tipos propios alteraría el resultado de las demás. Un responsable institucional y un encargado de inventario reciben 403.

La entrada aparece en el menú lateral solo para quien puede usarla, mediante `inventario.context_processors.acceso_catalogos`.

## Categorías y tipos de recurso

El catálogo muestra cada categoría con sus tipos, cuántos recursos dependen de cada uno y si el tipo está marcado como unidad desplegable. Esa marca es la que habilita el despacho a una emergencia, así que se explica en el formulario en lugar de dejarla como una casilla suelta.

Nada se elimina: categorías y tipos se desactivan. Recursos, despliegues y evaluaciones ya registrados dependen de ellos y deben conservar su referencia. Una categoría desactivada deja de ofrecerse al crear tipos nuevos, pero sigue disponible en el formulario del tipo que ya la usaba: editar un nombre no puede mover el tipo de categoría.

Los códigos se normalizan a mayúsculas al guardar, porque son el identificador visible del catálogo.

## Capacidades operativas

La capacidad y sus requisitos se guardan juntos, dentro de una misma transacción. Los requisitos son la definición de la capacidad y no un anexo: una capacidad guardada a medias mediría mal a todas las estaciones hasta que alguien completara la otra mitad.

Los requisitos se editan como filas de un formulario anidado, con tres filas libres y la opción de retirar los existentes. Desactivar una capacidad no altera sus evaluaciones históricas, porque cada evaluación guarda su propio `detalle_recursos`.

Hubo que acotar cuándo cuenta una fila como usada. `obligatorio` nace marcado por el valor por omisión del modelo, de modo que una casilla que el usuario nunca tocó se veía como un cambio: Django daba la fila vacía por rellenada y exigía los campos que justamente habían quedado en blanco. `RequisitoRecursoCapacidadForm.has_changed` la considera usada solo si trae tipo de recurso o cantidad.

## La opción vacía de los selectores

Al revisar los formularios nuevos apareció un defecto que ya venía de antes: Django 6.1 reemplazó la línea de guiones de la opción vacía por un texto propio, y la traducción al español todavía no lo cubre, de modo que todos los selectores del sistema mostraban «- Select an option -» dentro de una interfaz en español.

`core.forms.preparar_campos` reúne ahora la clase de estilo y esa etiqueta, y lo usan los seis módulos de formularios. Solo sustituye la etiqueta cuando el formulario no eligió una propia, así que el selector de unidades del despacho conserva su «Seleccione una unidad». La alternativa era `USE_BLANK_CHOICE_DASH`, que devuelve la línea de guiones con una sola línea de configuración, pero está marcada para desaparecer en Django 7.

## Menú lateral

El pie decía «Módulos en construcción» en todas las páginas desde la primera etapa del proyecto. Ahora identifica al sistema. Se retiró también `.status-dot`, que solo servía a ese rótulo.

## Verificación

- `python manage.py check`: sin problemas.
- `python manage.py makemigrations --check`: sin cambios pendientes.
- `python manage.py test inventario.test_catalogo operaciones.test_catalogo_capacidades`: 25 pruebas correctas.
- `python manage.py test`: 344 pruebas correctas.
- Comprobación manual sobre la base local: el catálogo lista las dos categorías con sus tipos y el conteo de recursos; el formulario de capacidad presenta las tres filas de requisitos; ningún selector de cinco formularios distintos muestra ya texto en inglés, y el del despacho mantiene su etiqueta propia.
