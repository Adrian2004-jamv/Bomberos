# Prompt 4: estructura institucional

## Alcance

Se implementó exclusivamente la jerarquía:

```text
Cantón → Cuerpo de Bomberos → Estaciones
```

No se crearon vistas, formularios, plantillas ni datos iniciales.

## Modelos

### `Canton`

Incluye nombre, código único, estado activo y fechas automáticas de creación y actualización.

### `CuerpoBomberos`

Se relaciona con `Canton` mediante `ForeignKey`. Incluye nombre, sigla única, RUC único, dirección, teléfono, correo, sitio web, estado y fechas de auditoría.

### `Estacion`

Se relaciona con `CuerpoBomberos` mediante `ForeignKey`. Incluye nombre, código, dirección, teléfono, latitud, longitud, estado y fechas de auditoría.

La latitud utiliza seis decimales y se valida entre -90 y 90. La longitud utiliza seis decimales y se valida entre -180 y 180. No se utilizó GeoDjango ni PostGIS.

El código de una estación es único dentro de cada Cuerpo de Bomberos mediante una restricción compuesta.

## Integridad de las relaciones

Ambas claves foráneas utilizan `on_delete=models.PROTECT`:

- Un cantón no puede eliminarse mientras tenga Cuerpos de Bomberos.
- Un Cuerpo de Bomberos no puede eliminarse mientras tenga estaciones.

## Django Admin

Los tres modelos se registraron con:

- columnas relevantes;
- búsqueda por identificadores y nombres;
- filtros por estado y relaciones;
- selección relacionada para evitar consultas innecesarias;
- campos agrupados por identificación, contacto, ubicación y auditoría;
- fechas automáticas de solo lectura.

## Archivos modificados o creados

- `instituciones/models.py`
- `instituciones/admin.py`
- `instituciones/migrations/0001_initial.py`

## Migraciones y verificación

Se revisó el plan y se aplicó únicamente la migración inicial de `instituciones`.

```text
System check identified no issues (0 silenced).
No changes detected
instituciones
 [X] 0001_initial
```
