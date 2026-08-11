# Actualización GPS en tiempo real mediante WebSockets

## Alcance

Se incorporó Django Channels a la arquitectura ASGI para actualizar las unidades del mapa operativo cuando se registra una nueva posición GPS. El servicio HTTP de captura sigue siendo la única vía que valida y guarda posiciones; el WebSocket es un canal de salida y no acepta comandos de persistencia.

## Arquitectura

- `config/asgi.py` atiende HTTP y WebSockets mediante `ProtocolTypeRouter`.
- `mapas/consumers.py` autentica al usuario y lo incorpora únicamente a grupos calculados desde sus estaciones autorizadas.
- Cada estación utiliza el grupo `gps.estacion.<id>`, evitando difundir posiciones de otras instituciones.
- `emergencias/services.py` programa la publicación con `transaction.on_commit`; nunca se anuncia una posición que no haya quedado confirmada en PostgreSQL.
- `emergencias/realtime.py` publica un evento mínimo, sin credenciales ni datos personales.
- El mapa actualiza el marcador correspondiente sin recentrar la vista y descarta eventos repetidos o antiguos.

## Disponibilidad y reconexión

El navegador abre `ws://` en desarrollo y `wss://` cuando la página usa HTTPS. Ante una desconexión reintenta con espera exponencial de 1 a 30 segundos. La consulta HTTP cada 10 segundos permanece activa como respaldo y fuerza una sincronización completa al recuperar el WebSocket.

La interfaz muestra los estados conectando, tiempo real conectado, reconectando, respaldo por consulta periódica y sin conexión en tiempo real.

## Capa de canales

En desarrollo y pruebas controladas se usa `InMemoryChannelLayer`. Esta opción no sirve para producción ni para varios procesos porque cada proceso conserva sus propios grupos.

En producción se configura Redis:

```powershell
$env:CHANNEL_LAYER_BACKEND="redis"
$env:REDIS_URL="redis://127.0.0.1:6379/0"
python -m daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

En Windows Redis puede ejecutarse dentro de WSL. Debe instalarse de forma consciente, iniciarse con `sudo service redis-server start` y verificarse mediante `redis-cli ping`. No se instaló Redis automáticamente durante este paso.

## Archivos principales

- `config/settings.py`
- `config/asgi.py`
- `mapas/routing.py`
- `mapas/consumers.py`
- `mapas/test_websockets.py`
- `emergencias/realtime.py`
- `emergencias/services.py`
- `templates/mapas/operativo.html`
- `static/mapas/js/operativo.js`
- `static/mapas/css/operativo.css`
- `.env.example`
- `requirements.txt`

## Comprobaciones

Se cubren autenticación, aislamiento por estación e institución, mensajes solo de salida, publicación posterior al commit, ausencia de publicación ante rollback y estructura mínima del evento. También se conservan las pruebas HTTP del mapa, incluyendo el mecanismo de respaldo por consulta periódica.
