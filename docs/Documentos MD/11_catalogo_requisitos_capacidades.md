# Prompt 11: catálogo y requisitos de capacidades operativas

## Auditoría previa

Se confirmó que Git estaba limpio y sincronizado con `origin/main`, que las migraciones de operaciones e inventario estaban aplicadas y que existían 0 especialidades y 0 tipos de recursos. No había conflictos de datos.

## Tipo de capacidad operativa

`TipoCapacidadOperativa` define formalmente una respuesta que una institución podrá declarar, por ejemplo combate de incendios o rescate vehicular. Incluye nombre, código único, descripción, estado activo y fechas de auditoría.

No se crearon capacidades iniciales.

## Requisitos materiales

`RequisitoRecursoCapacidad` indica qué tipo de recurso y qué cantidad mínima requiere una capacidad. También permite marcar el requisito como obligatorio y añadir observaciones.

Una capacidad no puede repetir un tipo de recurso. El mismo tipo sí puede reutilizarse en capacidades diferentes.

## Requisitos de personal

`RequisitoPersonalCapacidad` indica la especialidad, el nivel mínimo y la cantidad mínima de personal requerido. Reutiliza directamente las opciones de `CalificacionPersonal.Nivel`.

Una capacidad no puede repetir la misma combinación de especialidad y nivel mínimo.

## Integridad

Las cantidades utilizan `PositiveIntegerField`, `MinValueValidator(1)` y restricciones de base de datos que exigen valores mayores o iguales a uno.

Todas las relaciones utilizan `PROTECT`. Una capacidad, especialidad o tipo de recurso utilizado no puede eliminarse mientras forme parte de un requisito.

Los requisitos se consultan mediante los nombres inversos:

```python
capacidad.requisitos_recursos.all()
capacidad.requisitos_personal.all()
```

## Relación con inventario y personal

Los requisitos materiales apuntan a `inventario.TipoRecurso`. Los requisitos humanos apuntan a `EspecialidadOperativa` y a los niveles usados por `CalificacionPersonal`.

En este paso solo se define la regla. Todavía no se compara contra recursos, disponibilidad, personal o calificaciones de una estación; esa evaluación pertenece a una etapa posterior.

## Django Admin

El catálogo puede administrarse y buscarse por nombre o código, además de filtrarse por estado activo. Los requisitos materiales y humanos aparecen como dos elementos en línea dentro de cada capacidad.

## Pruebas

Se añadieron nueve pruebas para creación, requisitos válidos, cantidades cero y negativas, duplicados, reutilización de recursos y protección de catálogos utilizados.

Junto con las pruebas anteriores se ejecutaron 22 pruebas de `operaciones`.

## Archivos creados o modificados

- `operaciones/models.py`
- `operaciones/admin.py`
- `operaciones/test_capacidades.py`
- `operaciones/migrations/0003_tipocapacidadoperativa_requisitorecursocapacidad_and_more.py`
- `docs/Documentos MD/README.md`
- `docs/Documentos MD/11_catalogo_requisitos_capacidades.md`

## Verificación

```text
Applying operaciones.0003_tipocapacidadoperativa_requisitorecursocapacidad_and_more... OK
System check identified no issues (0 silenced).
Found 22 test(s).
Ran 22 tests
OK
No changes detected
```

No se calcularon capacidades de estaciones ni se crearon datos, vistas o interfaces.
