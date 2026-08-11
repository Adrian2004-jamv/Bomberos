# Migración local a PostgreSQL y PostGIS

## Objetivo

Se reemplazó SQLite como base predeterminada de Django por PostgreSQL. Después de verificar la transferencia, `Bomberos.db` fue eliminada por solicitud expresa y PostgreSQL quedó como única base activa.

## Entorno comprobado

- PostgreSQL 18.3 en `127.0.0.1:5432`.
- PostGIS 3.6.2.
- Psycopg 3.3.4 instalado globalmente.
- Base creada: `bomberos_cotopaxi`.
- Extensión `postgis` habilitada.

## Configuración

`config/settings.py` utiliza `django.db.backends.postgresql` como conexión `default`. Los valores no sensibles tienen valores locales predeterminados y pueden sobrescribirse con:

- `POSTGRES_DB`.
- `POSTGRES_USER`.
- `POSTGRES_HOST`.
- `POSTGRES_PORT`.

La contraseña debe proporcionarse mediante `POSTGRES_PASSWORD` o el archivo local ignorado `secrets/postgresql_password.txt`. No se escribió en ningún archivo versionado.

El alias temporal `legacy_sqlite` fue retirado para impedir que Django vuelva a crear accidentalmente una base SQLite vacía.

## Datos transferidos

La base SQLite contenía siete usuarios de desarrollo y seis grupos. Los siete usuarios fueron copiados a PostgreSQL conservando hashes de contraseña, atributos y pertenencia a grupos. No existían instituciones, estaciones, recursos, capacidades ni emergencias para transferir.

## Dependencias

Se agregó `psycopg[binary]==3.3.4` a `requirements.txt`.

## Verificación

- Todas las migraciones fueron aplicadas en PostgreSQL.
- Los siete usuarios autentican correctamente.
- `python manage.py check`: sin problemas.
- `python manage.py makemigrations --check`: sin cambios pendientes.
- `python manage.py test`: 92 pruebas correctas ejecutadas sobre PostgreSQL.

La base SQLite se conservó durante la migración y se eliminó solamente después de comprobar los usuarios, grupos, migraciones y pruebas en PostgreSQL.
