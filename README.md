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
- Mapa operativo con emergencias activas, unidades desplegadas y recorridos recientes.

## Requisitos

- Python 3.14.
- Django 6.1.
- PostgreSQL 18 con PostGIS 3.6.
- Psycopg 3.
- GDAL y GEOS (disponibles en desarrollo mediante QGIS 3.44.12).
- Django Channels 4.3 y Daphne, para HTTP y WebSockets sobre ASGI.
- Redis 5 o posterior en producción, como capa de canales compartida.
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

El servidor de desarrollo utiliza Daphne y una capa de canales en memoria. Para probar explícitamente la aplicación ASGI también puede ejecutar:

```powershell
python -m daphne -b 127.0.0.1 -p 8000 config.asgi:application
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
- `CHANNEL_LAYER_BACKEND`: `memory` para desarrollo o pruebas controladas; `redis` para producción.
- `REDIS_URL`: conexión de Redis, por ejemplo `redis://127.0.0.1:6379/0`, obligatoria cuando el backend es `redis`.

La capa en memoria no comparte mensajes entre procesos y no debe utilizarse en producción. En Windows puede ejecutar Redis dentro de WSL, iniciarlo con `sudo service redis-server start` y comprobarlo con `redis-cli ping`. Después configure:

```powershell
$env:CHANNEL_LAYER_BACKEND="redis"
$env:REDIS_URL="redis://127.0.0.1:6379/0"
python -m daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

En producción, la aplicación debe publicarse detrás de HTTPS para que el navegador utilice WebSockets seguros (`wss://`). Si el canal en tiempo real se interrumpe, el mapa intenta reconectarse con espera progresiva y conserva la consulta HTTP periódica como respaldo.

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
