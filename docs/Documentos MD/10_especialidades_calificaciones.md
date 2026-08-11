# Prompt 10: especialidades y calificaciones del personal

## Auditoría previa

Se confirmó que el árbol Git estaba limpio, `main` seguía a `origin/main`, la migración inicial de `operaciones` estaba aplicada y existían 0 registros de personal operativo. No había conflictos de datos.

## Especialidad operativa

`EspecialidadOperativa` representa un área general de competencia, como rescate vehicular o atención prehospitalaria. Incluye nombre, código único, descripción, estado activo y fechas de auditoría.

No se crearon datos iniciales.

## Calificación del personal

`CalificacionPersonal` representa la acreditación concreta que vincula una persona con una especialidad. Registra:

- nivel;
- número de certificado;
- entidad emisora;
- emisión y vencimiento opcional;
- usuario verificador opcional;
- observaciones, estado activo y fechas de auditoría.

Los niveles disponibles son básico, intermedio, avanzado e instructor.

El usuario verificador utiliza `PROTECT`, por lo que no puede eliminarse mientras respalde una calificación.

## Relación intermedia

`PersonalOperativo.especialidades` es una relación `ManyToManyField` que utiliza `CalificacionPersonal` mediante `through`. El modelo intermedio permite almacenar información que no pertenece únicamente a la persona ni únicamente a la especialidad, como nivel, certificado, vigencia y verificación.

La restricción `operaciones_calificacion_especialidad_unica_por_personal` impide duplicar la misma especialidad para una persona, pero permite asignarla a personas diferentes.

## Vigencia

La propiedad `vigente` devuelve:

- `False` si la calificación está inactiva;
- `True` si está activa y no caduca;
- `True` si el vencimiento es hoy o una fecha futura;
- `False` si el vencimiento ya pasó.

La fecha de vencimiento no puede ser anterior a la emisión. La regla se protege con validación del modelo y con la restricción de base `operaciones_calificacion_vencimiento_valido`.

## Django Admin

Se registraron especialidades y calificaciones con columnas, búsqueda, filtros, vigencia y consultas optimizadas mediante `list_select_related`. Las calificaciones también aparecen como `TabularInline` dentro del personal operativo.

## Pruebas

Se añadieron siete pruebas para vigencia sin vencimiento, vigencia futura, vencimiento, inactividad, fechas inválidas, duplicados y reutilización de una especialidad entre distintas personas.

Junto con las seis pruebas previas de personal se ejecutaron 13 pruebas.

## Archivos creados o modificados

- `operaciones/models.py`
- `operaciones/admin.py`
- `operaciones/tests.py`
- `operaciones/test_calificaciones.py`
- `operaciones/migrations/0002_especialidadoperativa_calificacionpersonal_and_more.py`
- `docs/Documentos MD/README.md`
- `docs/Documentos MD/10_especialidades_calificaciones.md`

## Verificación

```text
Applying operaciones.0002_especialidadoperativa_calificacionpersonal_and_more... OK
System check identified no issues (0 silenced).
Found 13 test(s).
Ran 13 tests
OK
No changes detected
```

No se crearon interfaces, capacidades institucionales ni datos de demostración.
