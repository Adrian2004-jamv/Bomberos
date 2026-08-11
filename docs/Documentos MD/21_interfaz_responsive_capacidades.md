# Interfaz responsive de capacidades operativas

## Alcance

Se implementó exclusivamente la interfaz del módulo de capacidades operativas. La evaluación continúa dependiendo solo de recursos materiales activos, operativos y disponibles; no se incorporó gestión de personal.

## Funcionalidad incorporada

- Catálogo paginado de tipos de capacidades con estado y número de requisitos.
- Detalle de cada capacidad y sus requisitos de recursos.
- Formulario de evaluación por estación que reutiliza `evaluar_capacidad_estacion`.
- Resultado con institución, estación, responsable, fecha, porcentaje y detalle legible de recursos.
- Historial inmutable con filtros por institución, estación, capacidad, resultado y fechas.
- Navegación visible solo para usuarios con acceso al módulo.

## Permisos y alcance

- Superusuarios, administradores y responsables provinciales consultan y evalúan todas las estaciones.
- Responsables institucionales consultan y evalúan las estaciones de su Cuerpo de Bomberos.
- Responsables de estación quedan limitados a su estación.
- Encargados de inventario y operadores de consulta pueden consultar, pero no ejecutar evaluaciones.
- Las consultas y opciones de formularios se limitan en el servidor para evitar accesos mediante identificadores manipulados.

## Archivos principales

- `operaciones/permissions.py`, `forms.py`, `views.py`, `urls.py` y `context_processors.py`.
- `templates/operaciones/` con las cinco pantallas y paginación compartida.
- `static/operaciones/css/capacidades.css` con estilos mobile-first.
- `operaciones/test_interfaz_capacidades.py` con pruebas de acceso, alcance, servicio e historial.

## Verificación

- `python manage.py check`: sin problemas.
- `python manage.py makemigrations --check`: sin cambios pendientes.
- `python manage.py test operaciones`: 25 pruebas correctas.
- `python manage.py test`: 65 pruebas correctas.

No se generaron migraciones porque no se modificaron modelos. La comprobación visual automatizada no pudo ejecutarse al no existir un navegador conectado en la sesión; el renderizado de las plantillas y sus rutas sí fue cubierto por pruebas automatizadas.
