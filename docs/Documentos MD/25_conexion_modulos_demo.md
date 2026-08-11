# Conexión de módulos y datos locales de demostración

## Objetivo

Hacer visibles desde la interfaz los módulos ya implementados y permitir revisar el sistema después de migrar a PostgreSQL, cuya base solo contenía cuentas de acceso.

## Diagnóstico

El inicio de sesión y el dashboard funcionaban, pero PostgreSQL tenía cero registros institucionales, recursos, capacidades, evaluaciones y emergencias. Por esa razón el superusuario encontraba pantallas vacías.

## Cambios

- Se incorporaron las rutas web de `emergencias` al enrutador principal.
- Se agregó un listado y un detalle de emergencias respetando el ámbito institucional del usuario.
- El enlace Emergencias dejó de aparecer deshabilitado en la barra lateral.
- El superusuario puede saltar desde el listado a la administración existente de emergencias.
- Se añadió el comando idempotente `python manage.py cargar_demo_desarrollo`.
- El comando crea únicamente registros marcados con `[DEMO]`: una institución, una estación, categorías, tipos, tres recursos, una capacidad con requisitos, una evaluación y una emergencia.
- Los datos son ficticios y no deben interpretarse como información oficial ni real.

## Comprobaciones

- `python manage.py check`: sin errores.
- `python manage.py makemigrations --check`: sin cambios pendientes.
- Suite completa: 92 pruebas superadas antes de agregar las comprobaciones web de emergencias.
- Se añadieron pruebas de visibilidad por ámbito para el listado y el detalle de emergencias.
