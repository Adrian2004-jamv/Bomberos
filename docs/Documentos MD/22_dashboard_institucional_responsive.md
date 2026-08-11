# Dashboard institucional responsive

## Alcance

Se implementó exclusivamente el dashboard principal del sistema dentro de la aplicación `dashboard`. No se incorporaron mapas, emergencias, formularios SCI ni funcionalidades PWA.

## Indicadores

- Total de recursos registrados.
- Recursos operativos y fuera de servicio.
- Recursos disponibles y no disponibles.
- Estaciones visibles.
- Capacidades cumplidas y no cumplidas.
- Distribución de recursos por categoría.
- Distribución por todos los estados definidos en `Recurso.EstadoOperativo`.

El resumen de capacidades utiliza solamente la evaluación más reciente de cada combinación de estación y tipo de capacidad. Una estación sin evaluaciones se mantiene sin resultado y no se contabiliza como incumplida.

## Alcance y seguridad

Las consultas parten de `estaciones_permitidas()` y `recursos_permitidos()`:

- El alcance global consolida la provincia.
- El responsable institucional ve las estaciones de su Cuerpo de Bomberos.
- Los roles de estación, inventario y consulta quedan limitados a su estación.
- Los accesos rápidos se muestran según permisos reales de consulta y gestión.

No se aceptan identificadores de alcance mediante parámetros del dashboard.

## Consultas y presentación

La lógica se centralizó en `dashboard/services.py`. Se utilizaron agregaciones con `Count`, filtros condicionales, `select_related` y una subconsulta correlacionada para identificar evaluaciones vigentes. La actividad reciente combina los historiales existentes de recursos y evaluaciones, con un límite de ocho elementos.

La interfaz en `templates/dashboard/principal.html` utiliza CSS mobile-first sin bibliotecas externas. Incluye estados vacíos, barras accesibles con texto, tarjetas progresivas y controles táctiles.

## Navegación

- Ruta principal: `/dashboard/` (`dashboard:principal`).
- La ruta raíz anterior redirige al dashboard para conservar compatibilidad.
- El login y el logotipo dirigen al dashboard.

## Verificación

- `python manage.py check`: sin problemas.
- `python manage.py makemigrations --check`: sin cambios pendientes.
- `python manage.py test dashboard core`: 11 pruebas correctas.
- `python manage.py test`: 74 pruebas correctas.

No se generaron migraciones. La revisión visual automatizada no pudo completarse porque no existía un navegador conectado; el dashboard con datos y sin datos fue renderizado y validado mediante pruebas automatizadas.
