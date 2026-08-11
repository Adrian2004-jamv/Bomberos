# Sistema Bomberos Cotopaxi

Proyecto académico desarrollado con Django para una tesis sobre la gestión de inventarios y capacidades operativas de los Cuerpos de Bomberos de Cotopaxi.

## Módulos actuales

- Usuarios autorizados vinculados a estaciones, grupos y permisos básicos.
- Cantones, Cuerpos de Bomberos y estaciones.
- Categorías, tipos y recursos de inventario.
- Historial de estado operativo y disponibilidad de recursos.
- Catálogo y evaluación histórica de capacidades basada en recursos materiales.
- Registro básico de emergencias y despliegue de unidades del inventario.
- Historial y transmisión GPS de unidades desplegadas mediante PostGIS.

## Requisitos

- Python 3.14.
- Django 6.1.
- PostgreSQL 18 con PostGIS 3.6.
- Psycopg 3.
- GDAL y GEOS (disponibles en desarrollo mediante QGIS 3.44.12).
- Git, para control de versiones.

El proyecto utiliza PostgreSQL como única base de datos activa. La base SQLite utilizada durante la etapa inicial fue retirada después de verificar la migración.

## Ejecución local

Este proyecto utiliza la instalación disponible de Python. Instale las dependencias con:

```powershell
python -m pip install -r requirements.txt
```

Prepare la base de datos y compruebe la configuración:

```powershell
python manage.py migrate
python manage.py check
```

Inicie el servidor de desarrollo:

```powershell
python manage.py runserver
```

La aplicación estará disponible en `http://127.0.0.1:8000/` y Django Admin en `http://127.0.0.1:8000/admin/`.

## Configuración local

Para desarrollo, el proyecto admite estas variables de entorno:

- `DJANGO_SECRET_KEY`: clave secreta de Django.
- `DJANGO_DEBUG`: use `True` solamente en desarrollo local y `False` en producción.
- `POSTGRES_DB`: nombre de la base; por defecto `bomberos_cotopaxi`.
- `POSTGRES_USER`: usuario; por defecto `postgres`.
- `POSTGRES_PASSWORD`: contraseña de PostgreSQL.
- `POSTGRES_HOST`: servidor; por defecto `127.0.0.1`.
- `POSTGRES_PORT`: puerto; por defecto `5432`.
- `GDAL_LIBRARY_PATH`: ruta a GDAL cuando el sistema no la detecte.
- `GEOS_LIBRARY_PATH`: ruta a GEOS cuando el sistema no la detecte.

En desarrollo local, si `POSTGRES_PASSWORD` no está definida, la contraseña puede guardarse en `secrets/postgresql_password.txt`. La carpeta `secrets/` está excluida de Git.

La base debe crearse previamente y tener PostGIS habilitado:

```sql
CREATE DATABASE bomberos_cotopaxi;
\c bomberos_cotopaxi
CREATE EXTENSION IF NOT EXISTS postgis;
```

El valor de respaldo de `DJANGO_SECRET_KEY` incluido en el código es únicamente para desarrollo y no es seguro para producción.

## Protección de datos

Este repositorio es académico. No deben utilizarse ni incorporarse datos personales reales, información operativa sensible, credenciales, claves privadas, archivos `.env`, bases de datos locales ni documentos confidenciales.
