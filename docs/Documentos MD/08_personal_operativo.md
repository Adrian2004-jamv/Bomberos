# Prompt 8: registro básico del personal operativo

## Auditoría previa

Se confirmó que las migraciones de `usuarios` e `instituciones` estaban aplicadas, que `operaciones` no tenía migraciones propias y que existían 0 estaciones y 0 usuarios. No había conflictos de datos.

## Modelo `PersonalOperativo`

Se creó un registro operativo independiente de la cuenta de acceso al sistema. Incluye:

- estación;
- cuenta de usuario opcional;
- código institucional;
- cédula opcional;
- nombres y apellidos;
- rango y cargo operativo;
- teléfono y fecha de ingreso;
- disponibilidad;
- observaciones y estado activo;
- fechas automáticas de creación y actualización.

No almacena contraseñas ni datos de autenticación.

## Diferencia entre usuario y personal

`Usuario` representa una cuenta que puede autenticarse y recibir grupos y permisos. `PersonalOperativo` representa a una persona que forma parte de la capacidad humana de una estación, independientemente de que tenga acceso al sistema.

La cuenta es opcional mediante un `OneToOneField` con `null=True`, `blank=True` y `SET_NULL`. Si se elimina la cuenta, el registro operativo permanece. Una cuenta solo puede relacionarse con un miembro del personal.

La validación de que la estación de la cuenta coincida con la estación del personal quedó documentada mediante `help_text` para una etapa posterior.

## Relación institucional

La estación utiliza `ForeignKey` con `PROTECT`. No puede eliminarse mientras tenga personal operativo asociado.

El Cuerpo de Bomberos no se almacena nuevamente. La propiedad `institucion` lo obtiene con:

```python
personal.estacion.cuerpo_bomberos
```

Así se evita duplicar información y generar inconsistencias.

## Disponibilidad

Se creó un `TextChoices` con:

- Disponible.
- Asignado.
- Descanso.
- Licencia.
- No disponible.

## Validaciones y restricciones

- El código institucional es único dentro de cada estación mediante `operaciones_personal_codigo_unico_por_estacion`.
- El mismo código puede utilizarse en estaciones diferentes.
- La cédula admite temporalmente `NULL` y es única cuando tiene valor.
- La fecha de ingreso se valida para impedir fechas futuras.
- `nombre_completo` combina nombres y apellidos de manera legible.

## Django Admin

El listado muestra nombre completo, código, estación, Cuerpo de Bomberos, rango, cargo, disponibilidad y estado activo.

Incluye búsqueda por datos personales, código, estación, institución y usuario; filtros institucionales y operativos; campos organizados; fechas de auditoría de solo lectura y `list_select_related` para optimizar relaciones.

## Pruebas

Se añadieron seis pruebas:

- creación sin cuenta;
- creación con cuenta;
- rechazo del código repetido en una estación;
- aceptación del mismo código en estaciones distintas;
- rechazo de una fecha futura;
- funcionamiento de `nombre_completo`.

## Archivos creados o modificados

- `operaciones/models.py`
- `operaciones/admin.py`
- `operaciones/tests.py`
- `operaciones/migrations/0001_initial.py`
- `docs/Documentos MD/README.md`
- `docs/Documentos MD/08_personal_operativo.md`

## Verificación

```text
Applying operaciones.0001_initial... OK
System check identified no issues (0 silenced).
Found 6 test(s).
Ran 6 tests
OK
No changes detected
```

No se crearon vistas, formularios, API, datos iniciales, especialidades ni capacidades.
