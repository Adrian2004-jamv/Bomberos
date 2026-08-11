# Corrección de alcance: capacidades sin gestión de personal

## Objetivo

Se ajustó el sistema al alcance definitivo de la tesis: administrar usuarios autorizados, inventarios y capacidades operativas institucionales, sin administrar nóminas ni personal operativo.

Los documentos 08, 10, 11 y 19 se conservan como antecedentes cronológicos del desarrollo, pero sus componentes de personal quedaron reemplazados por esta corrección.

## Cambios realizados

- Se conservaron `usuarios.Usuario`, su relación con `Estacion` y el acceso indirecto a `CuerpoBomberos` y `Canton`.
- Se retiraron `PersonalOperativo`, `EspecialidadOperativa`, `CalificacionPersonal`, `HistorialDisponibilidadPersonal` y `RequisitoPersonalCapacidad`.
- Se eliminaron del administrador, servicios, pruebas y navegación las funciones exclusivas de personal.
- `TipoCapacidadOperativa` conserva exclusivamente requisitos materiales mediante `RequisitoRecursoCapacidad`.
- La evaluación cuenta solo recursos de la estación solicitada que estén activos, operativos y disponibles.
- El historial conserva la estación, capacidad, fecha, responsable, resultado, porcentaje y una fotografía JSON de recursos requeridos, encontrados y faltantes.

## Migración

Se generó y aplicó la migración `operaciones.0006`, sin borrar la base de datos ni alterar migraciones anteriores. La migración retira las tablas de los cinco modelos descartados y el campo `detalle_personal` de las evaluaciones.

## Verificación

Las pruebas cubren cumplimiento con recursos suficientes, incumplimiento por faltantes, aislamiento entre estaciones, exclusión de recursos inactivos, fuera de servicio o no disponibles, y persistencia del detalle histórico.
