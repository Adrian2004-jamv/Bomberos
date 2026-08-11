# Rastreo GPS geográfico con PostGIS

## Objetivo

Convertir el historial GPS inicial a almacenamiento geográfico nativo utilizando GeoDjango y PostGIS, sin incorporar todavía un mapa web.

## Configuración

- Se activó `django.contrib.gis`.
- La base utiliza `django.contrib.gis.db.backends.postgis`.
- GDAL y GEOS se cargan desde variables de entorno o desde la instalación local de QGIS cuando está disponible.
- PostgreSQL confirmó PostGIS 3.6.2 y el soporte de GEOS/PROJ.

## Modelo

`PosicionUnidad.ubicacion` es un `PointField` con SRID 4326 e índice espacial GiST. No existen columnas duplicadas de latitud o longitud. La longitud se almacena en `x` y la latitud en `y` mediante `Point(longitud, latitud, srid=4326)`.

La migración `0003_posicionunidad_postgis` conserva compatibilidad con la migración anterior: agrega temporalmente el punto, transforma cualquier coordenada existente y después retira las columnas decimales.

## Consultas

Se mantienen índices temporales por despliegue y fecha de recepción. Las pruebas también verifican una consulta espacial básica por distancia ejecutada en PostGIS.

## Alcance excluido

No se implementaron mapas, WebSockets, análisis de rutas, geocodificación, PWA ni almacenamiento offline.
