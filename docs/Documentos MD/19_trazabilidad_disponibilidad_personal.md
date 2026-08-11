# Trazabilidad de disponibilidad del personal operativo

## Objetivo

Registrar de forma inmutable cada cambio de disponibilidad del personal operativo, incluyendo valores anterior y nuevo, motivo, observaciones, responsable y fecha.

## Modelo histórico

Se creó `HistorialDisponibilidadPersonal` con:

- relación `CASCADE` con `PersonalOperativo`;
- relación `PROTECT` con el usuario responsable;
- opciones reutilizadas desde `PersonalOperativo.Disponibilidad`;
- orden descendente por fecha y clave primaria;
- nombres inversos claros y representación legible.

## Servicio

`actualizar_disponibilidad_personal` valida personal, usuario activo, disponibilidad y motivo. La actualización y el historial se ejecutan mediante `transaction.atomic`.

El personal se consulta con `select_for_update`, bloqueando su fila hasta finalizar la transacción. Esto evita que dos solicitudes simultáneas utilicen el mismo valor anterior.

Si la disponibilidad no cambia, el servicio devuelve el personal y `None` sin crear historial.

## Inmutabilidad en Admin

El historial está registrado con todos sus campos como solo lectura. Django Admin no permite crear, editar ni eliminar registros históricos manualmente. Incluye filtros, buscador y relaciones optimizadas con `list_select_related`.

## Capacidades operativas

El cambio de disponibilidad no ejecuta evaluaciones automáticamente. Puede afectar una evaluación futura, pero las evaluaciones ya almacenadas representan una instantánea histórica y no se modifican.

## Archivos creados

- `operaciones/migrations/0005_historialdisponibilidadpersonal.py`
- `operaciones/test_historial_disponibilidad.py`

## Archivos modificados

- `operaciones/models.py`
- `operaciones/services.py`
- `operaciones/admin.py`

## Comprobaciones

- Migración aditiva revisada y aplicada.
- Pruebas de operaciones ejecutadas.
- No se añadieron señales, vistas ni interfaz pública de personal.
