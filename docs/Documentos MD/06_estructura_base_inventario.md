# Prompt 6: estructura base del inventario

## Auditoría previa

Antes de modificar archivos se confirmó que:

- Todas las migraciones anteriores estaban aplicadas.
- La aplicación `inventario` no tenía migraciones ni tablas propias.
- Existían 0 cantones, 0 Cuerpos de Bomberos y 0 estaciones.
- No había datos ni conflictos que requirieran eliminación o transformación.

## Estructura creada

Se implementó un inventario unificado con tres niveles:

```text
Categoría de recurso → Tipo de recurso → Recurso
                                      ↘ Estación
```

### `CategoriaRecurso`

Representa una clasificación general, por ejemplo vehículo, equipo, herramienta, comunicación o protección personal. Contiene nombre, código único, descripción, estado activo y fechas de auditoría.

No se crearon categorías iniciales.

### `TipoRecurso`

Representa una clasificación específica dentro de una categoría. Se relaciona con `CategoriaRecurso` mediante una clave foránea protegida.

Su código es único dentro de la categoría mediante la restricción:

```text
inventario_tipo_codigo_unico_por_categoria
```

### `Recurso`

Representa un bien concreto perteneciente a una estación. Contiene código interno, nombre, descripción, marca, modelo, número de serie opcional, año de fabricación opcional, estado operativo, disponibilidad, observaciones, estado activo y fechas de auditoría.

Se relaciona con:

- `instituciones.Estacion` mediante `estacion`;
- `inventario.TipoRecurso` mediante `tipo`.

Ambas relaciones utilizan `PROTECT` para impedir la eliminación de estaciones o tipos que todavía tengan recursos asociados.

## Estado operativo y disponibilidad

`estado_operativo` utiliza `TextChoices` con:

- Operativo.
- En mantenimiento.
- Fuera de servicio.
- Dado de baja.

`disponibilidad` utiliza otro `TextChoices` independiente con:

- Disponible.
- Asignado.
- Reservado.
- No disponible.

La separación permite, por ejemplo, que un recurso esté técnicamente operativo pero asignado y no disponible para otro uso.

## Validaciones y restricciones

- `anio_fabricacion` es numérico, opcional y no admite valores negativos.
- `numero_serie` y los demás textos opcionales usan `blank=True` sin `null=True`.
- `codigo_interno` es único dentro de una estación mediante:

```text
inventario_recurso_codigo_unico_por_estacion
```

El mismo código puede repetirse en estaciones diferentes.

## Recorrido institucional

Desde un recurso se accede a toda la jerarquía con:

```python
recurso.estacion
recurso.estacion.cuerpo_bomberos
recurso.estacion.cuerpo_bomberos.canton
```

## Django Admin

Se configuraron los tres modelos con columnas, búsquedas, filtros, grupos de campos y fechas de auditoría de solo lectura.

El listado de recursos permite filtrar por categoría, estación, Cuerpo de Bomberos, cantón, estado operativo, disponibilidad y estado activo. La búsqueda incluye código, nombre, marca, modelo, serie, estación y Cuerpo de Bomberos.

Se utilizó `list_select_related` para cargar relaciones frecuentes en las consultas del listado.

## Archivos modificados o creados

- `inventario/models.py`
- `inventario/admin.py`
- `inventario/migrations/0001_initial.py`
- `docs/Documentos MD/README.md`
- `docs/Documentos MD/06_estructura_base_inventario.md`

## Migración y verificación

La migración creó únicamente los tres modelos y sus restricciones. No se eliminaron ni modificaron datos existentes.

```text
Applying inventario.0001_initial... OK
System check identified no issues (0 silenced).
No changes detected
Categorías: 0
Tipos: 0
Recursos: 0
```

No se crearon vistas, formularios, plantillas ni datos de demostración.
