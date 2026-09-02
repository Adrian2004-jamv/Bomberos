# Sistema Bomberos Cotopaxi

Proyecto académico desarrollado con Django para una tesis sobre la gestión de inventarios y capacidades operativas de los Cuerpos de Bomberos de Cotopaxi.

## Módulos actuales

- Usuarios autorizados vinculados a estaciones, grupos y permisos básicos, con edición, desactivación, restablecimiento de clave y cambio obligatorio de la clave asignada.
- Cantones, Cuerpos de Bomberos y estaciones.
- Categorías, tipos y recursos de inventario, con catálogo editable desde la aplicación por el alcance provincial.
- Historial de estado operativo y disponibilidad de recursos.
- Catálogo y evaluación histórica de capacidades basada en recursos materiales.
- Registro de emergencias con ciclo operativo propio: reportada, en atención, controlada, cerrada o cancelada.
- Despacho de unidades del inventario al incidente, con seguimiento de asignada, en ruta, en sitio, retornando, finalizada o cancelada.
- Historial y transmisión GPS de unidades desplegadas mediante PostGIS.
- Mapa operativo con emergencias activas, unidades desplegadas y recorridos recientes.
- Dashboard con la situación operativa: incidentes en curso, unidades desplegadas y documentación pendiente.
- Exportación del inventario a Excel y CSV desde la tabla, y del registro de incidentes a CSV desde el servidor.
- Los doce formularios SCI, con borrador, finalización y vista imprimible.

## Requisitos

- Python 3.14.
- Django 6.1.
- PostgreSQL 18 con PostGIS 3.6.
- Psycopg 3.
- GDAL y GEOS, bibliotecas nativas que `django.contrib.gis` carga con `ctypes`. Se obtienen de los wheels de `rasterio` y `shapely`, iguales en desarrollo y en producción; si no están instalados, el sistema usa la instalación local de QGIS.
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

## Despliegue en Render

El despliegue se declara en [`render.yaml`](render.yaml) y **no utiliza contenedores**. Render crea tres recursos: el servicio web sobre ASGI, la base PostgreSQL y la instancia Key Value que comparte los mensajes de los WebSockets.

El punto delicado es que `django.contrib.gis` carga GDAL y GEOS con `ctypes` al importar el modulo: son bibliotecas del sistema, no paquetes de Python, y el entorno nativo de Render trae un conjunto fijo de herramientas que no las incluye. Se resuelve declarando `rasterio` y `shapely` en `requirements.txt`, cuyos wheels precompilados traen esas bibliotecas dentro; `config/settings.py` las localiza por patron, porque el nombre del archivo cambia con cada version. La misma version de GDAL queda en desarrollo y en produccion.

La extension espacial la crea la migracion `emergencias/0003_posicionunidad_postgis.py` mediante `CreateExtension("postgis")`, que emite `CREATE EXTENSION IF NOT EXISTS`. Una base recien creada queda lista sin pasos manuales y las bases existentes no se alteran.

Configuracion que toma el servicio del entorno:

| Variable | Origen | Efecto |
| --- | --- | --- |
| `DJANGO_DEBUG` | `render.yaml` | `False` activa HTTPS obligatorio, cookies seguras y HSTS. |
| `DJANGO_SECRET_KEY` | generada por Render | Sin ella el arranque falla; no se acepta la clave de desarrollo. |
| `DATABASE_URL` | base de datos | Tiene prioridad sobre las variables `POSTGRES_*` del entorno local. |
| `REDIS_URL` | instancia Key Value | Capa de canales compartida para los WebSockets. |
| `RENDER_EXTERNAL_HOSTNAME` | plataforma | Alimenta `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` sin escribir el dominio. |

El plan gratuito de Render no ofrece consola remota, de modo que no es posible ejecutar `createsuperuser` de forma interactiva. El primer acceso lo resuelve `crear_superusuario_inicial`, que se ejecuta al final de la construccion: lee `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_PASSWORD`, `DJANGO_SUPERUSER_EMAIL` y `DJANGO_SUPERUSER_CEDULA`, y solo actua si la base todavia no tiene ningun superusuario, por lo que los despliegues siguientes no lo repiten. Render pide esos valores al crear el Blueprint y no quedan escritos en el repositorio. Si el usuario ya existe y hay que recuperar el acceso, se define ademas `DJANGO_SUPERUSER_REINICIAR_CLAVE=1`, con lo cual el comando actualiza la clave, reactiva la cuenta y le devuelve la condicion de superusuario. La construccion carga ademas el catalogo de los siete cantones con `cargar_datos_cotopaxi`, que tambien es idempotente.

El despliegue de unidades se registra desde el detalle de la emergencia, con el boton **Despachar unidad**. En el panel de administracion `DespliegueUnidad` sigue siendo de solo lectura: crearlo ahi saltaria las validaciones y el bloqueo de fila del servicio, y dejaria el inventario sin el cambio de disponibilidad correspondiente. Para poblar una demostracion sin capturar nada a mano, defina `DJANGO_CARGAR_ESCENARIOS=1` y espere la reconstruccion: se ejecutan `cargar_inventario_bomberil` y `cargar_escenarios_sci`, que crean los incidentes `INC-2026-001` e `INC-2026-002` con sus unidades desplegadas y su SCI-211 armado a partir de ellas. El inventario va primero porque el escenario necesita las unidades `AB-01` y `AMB-01` en la estacion de Latacunga, y `cargar_datos_cotopaxi` no crea la ambulancia. Si esa carga falla, la construccion continua y la aplicacion se publica igual: son datos de demostracion y no deben condicionar el despliegue. El comando usa codigos fijos y sus borrados estan acotados a esas dos emergencias, de modo que no altera los incidentes registrados por usuarios. Conviene retirar la variable despues de la carga.

Para vaciar el padron de emergencias de prueba, defina `DJANGO_LIMPIAR_EMERGENCIAS` y espere la reconstruccion. El valor es `todas` para retirar el padron entero, o una fecha `AAAA-MM-DD` para retirar solo lo anterior a ese dia. Se van las emergencias con sus formularios SCI, sus despliegues y sus posiciones de GPS, y las unidades que estaban asignadas vuelven al inventario como disponibles; el inventario, las estaciones y los usuarios no se tocan. **Retire la variable en cuanto termine el despliegue**: mientras siga definida, cada reconstruccion vuelve a borrar, y una reconstruccion la dispara cualquier envio a la rama principal. La construccion lo recuerda en su registro. En local el comando es `python manage.py limpiar_emergencias`, que ensaya salvo que se le pase `--ejecutar` y admite `--antes-de`, `--codigo`, `--estacion` o `--todas`; sin ningun criterio se niega a actuar.

Para un dominio propio se definen ademas `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS`, ambas separadas por comas.

Los archivos estaticos los sirve WhiteNoise desde el propio proceso, con `CompressedStaticFilesStorage`. El versionado de cada archivo se hace a mano, con el sufijo `?v=` en las plantillas.

El proyecto incluye `core.storage.EstaticosConManifiesto`, que agrega un hash al nombre de cada archivo y haria innecesario ese sufijo. **No esta activo**, y conviene entender por que antes de encenderlo con la variable `DJANGO_STATICFILES_BACKEND`:

1. El service worker precarga catorce rutas escritas sin hash en `static/pwa/service-worker.js`. Con el manifiesto activo, ninguna pagina volveria a pedir esas rutas, de modo que la precarga quedaria sin efecto y el modo sin conexion dependeria de lo que se acumule durante la navegacion. Para activarlo hay que generar antes esa lista con la etiqueta `{% static %}`, sirviendo el archivo como plantilla.
2. Las pruebas corren con `DEBUG=False` y resuelven cada archivo contra el manifiesto, que no existe en una copia recien clonada hasta ejecutar `collectstatic`.

Los planes gratuitos de Render tienen dos limites que conviene tener presentes: el servicio web se suspende tras un periodo sin trafico y la primera peticion siguiente tarda cerca de un minuto, y las bases de datos gratuitas caducan a los treinta dias de creadas.

## Aplicación web progresiva

El sistema incluye manifiesto web, iconos instalables, service worker, indicador de conexión, aviso controlado de actualizaciones y una página institucional sin conexión. En navegadores compatibles, el botón **Instalar aplicación** aparece únicamente cuando el navegador autoriza la instalación.

Para comprobarla localmente:

1. Ejecute el servidor y abra `http://localhost:8000/`.
2. Revise **Application > Manifest** y **Application > Service Workers** en las herramientas del navegador.
3. Cargue una vez la aplicación, active el modo sin conexión y navegue para verificar la página offline.
4. Confirme en **Cache Storage** que solo existen CSS, JavaScript, iconos, el logotipo y la página offline.

Los service workers y la geolocalización requieren HTTPS en producción; `localhost` se considera seguro para desarrollo. Los WebSockets deben utilizar `wss://` bajo HTTPS.

La PWA no almacena páginas privadas, inventarios, usuarios, GPS, GeoJSON, recorridos, coordenadas ni operaciones de escritura. Las teselas externas tampoco se precargan ni almacenan. Sin conexión solo está disponible la estructura visual segura; una operación sin confirmación del servidor no se considera guardada.

Limitación actual: todavía no existe almacenamiento offline de posiciones GPS ni sincronización en segundo plano. Esa funcionalidad corresponde a una etapa posterior y requerirá cifrado, control de sesión y resolución explícita de conflictos.

## Formularios SCI

El **SCI-211 - Registro y Control de Recursos** fue el formulario piloto y conserva un modelo propio, porque es el único que se autocompleta desde los despliegues del incidente. Los once restantes comparten un esquema declarativo en `emergencias/esquemas_sci.py` y un editor común. Desde el detalle de una emergencia, un responsable institucional o de estación autorizado puede crear un borrador. Los despliegues existentes se copian como filas iniciales; después se pueden completar solicitud, arribo, procedencia, matrícula, dotación, disponibilidad, asignación, desmovilización y observaciones. El encabezado conserva el nombre del incidente, la fecha de preparación y el lugar de registro; el cierre incluye hasta tres registradores, como el XLSX oficial.

Un borrador puede guardarse y editarse. La acción **Finalizar** exige confirmación y valida que exista al menos un recurso y que sus campos obligatorios sean válidos. Al finalizar se congelan el código, fecha, dirección, institución, estación y coordenadas con los que se emitió el documento; desde entonces es de solo lectura. Los perfiles provinciales y de consulta acceden únicamente dentro de su ámbito, mientras inventario no obtiene edición SCI por ese solo rol.

La vista imprimible reproduce el formulario en HTML con la regla `@page` en A4 horizontal y se envía a la impresora desde el navegador; quien necesite un archivo usa la opción **Guardar como PDF** del propio diálogo de impresión. Se eligió A4 porque el XLSX oficial define orientación horizontal y ajuste a dos páginas de ancho, pero no fija el tamaño de papel. El contenido lo escapa Django y la hoja no carga recursos externos. El sistema no genera ni almacena archivos PDF en el servidor.

Limitaciones: el número de personas se inicia en 1 porque el sistema aún no administra dotaciones; debe confirmarlo el registrador. El XLSX muestra las columnas **Disponible**, **No disponible** y **Asignado a**, mientras su instructivo también menciona **Fuera de servicio**; para conservar ambos sentidos, la hoja imprimible marca ese caso como no disponible y escribe “Fuera de servicio” en la asignación. No se incluyen firmas electrónicas, modo offline ni otros formularios SCI.

## Acceso y cuentas

El operador de sistemas institucional y el superusuario administran las cuentas de su ámbito: crearlas, corregir sus datos y su rol, desactivarlas y restablecer su clave. No se borran, porque `Usuario` está protegido desde emergencias, despliegues e historial de inventario y esos registros deben conservar a su responsable. Nadie puede desactivar su propia cuenta ni intervenir la de un superusuario.

Cuando alguien asigna una clave en nombre de otra persona —al crear la cuenta, al restablecer el acceso o al levantar el despliegue con `crear_superusuario_inicial`— la cuenta queda marcada con `debe_cambiar_clave`. Mientras esa marca siga activa, `usuarios.middleware.ExigirCambioDeClave` devuelve cualquier página al formulario de cambio; solo quedan libres el propio formulario, el inicio y el cierre de sesión, y los tres recursos de la aplicación web progresiva. El usuario recupera el acceso normal en cuanto elige una clave nueva, y su sesión no se interrumpe.

En consecuencia, **el primer ingreso del superusuario creado en Render exige cambiar la clave**: la que viene de `DJANGO_SUPERUSER_PASSWORD` la conoce la plataforma y deja de servir apenas se reemplaza. Lo mismo ocurre después de recuperar el acceso con `DJANGO_SUPERUSER_REINICIAR_CLAVE=1`.

Cualquier usuario puede cambiar su propia clave cuando quiera, desde **Cambiar contraseña** en el menú lateral.

## Protección de datos

Este repositorio es académico. No deben utilizarse ni incorporarse datos personales reales, información operativa sensible, credenciales, claves privadas, archivos `.env`, bases de datos locales ni documentos confidenciales.
