# Prompt 7: trazabilidad del estado de recursos

## Auditoría previa

Se comprobó que las migraciones de `inventario`, `usuarios` e `instituciones` estaban aplicadas. La base contenía 0 recursos y 0 usuarios, por lo que no existían conflictos de datos.

## Modelo histórico

Se creó `HistorialEstadoRecurso` con:

- recurso;
- estado operativo anterior y nuevo;
- disponibilidad anterior y nueva;
- motivo y observaciones;
- usuario responsable;
- fecha automática de registro.

Los estados reutilizan `Recurso.EstadoOperativo.choices` y las disponibilidades reutilizan `Recurso.Disponibilidad.choices`, evitando definiciones divergentes.

El historial se ordena desde el registro más reciente al más antiguo.

## Relaciones

La relación con `Recurso` utiliza `CASCADE`. El historial solo se elimina cuando se elimina su propio recurso.

La relación con el usuario responsable utiliza `PROTECT`. Un usuario que figure como responsable de un cambio no puede eliminarse mientras existan esos registros de auditoría.

Los nombres inversos son:

```python
recurso.historial_estados.all()
usuario.cambios_estado_recursos.all()
```

## Servicio de actualización

Se creó `inventario/services.py` con `actualizar_estado_recurso`. La función:

1. Comprueba que el usuario responsable exista.
2. Valida el estado, la disponibilidad y el motivo.
3. Comprueba que el recurso exista.
4. Bloquea el recurso mediante `select_for_update` durante la operación.
5. Obtiene sus valores anteriores.
6. Devuelve `(recurso, None)` sin crear historial cuando no existe ningún cambio.
7. Actualiza el recurso y crea su historial cuando hay cambios.
8. Devuelve el recurso actualizado y el historial creado.

Toda la operación utiliza `transaction.atomic`. Si falla el guardado del historial, la actualización del recurso se revierte automáticamente.

La lógica permanece en un servicio reutilizable y no se añadieron señales. Esto permite que un futuro Admin, formulario, API o proceso de sincronización invoque explícitamente la misma operación con usuario y motivo conocidos.

## Inmutabilidad en Django Admin

El historial puede listarse, buscarse, filtrarse y consultarse, pero Admin prohíbe:

- agregar historiales manualmente;
- modificar historiales existentes;
- eliminar historiales manualmente.

Todos sus campos son de solo lectura. Esta inmutabilidad conserva evidencia fiable de quién realizó cada cambio y cuándo ocurrió.

## Pruebas

Se añadieron cuatro pruebas unitarias:

- un cambio válido actualiza el recurso y crea historial;
- una llamada sin cambios no crea historial;
- una opción inválida genera `ValidationError`;
- un fallo simulado al crear el historial revierte la actualización del recurso.

## Archivos creados o modificados

- `inventario/models.py`
- `inventario/admin.py`
- `inventario/services.py`
- `inventario/tests.py`
- `inventario/migrations/0002_historialestadorecurso.py`
- `docs/Documentos MD/README.md`
- `docs/Documentos MD/07_trazabilidad_estado_recursos.md`

## Verificación

```text
Applying inventario.0002_historialestadorecurso... OK
System check identified no issues (0 silenced).
Found 4 test(s).
Ran 4 tests
OK
No changes detected
```

No se crearon vistas, HTML, API, señales ni datos de demostración.
