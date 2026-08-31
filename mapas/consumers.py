from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from emergencias.permissions import puede_consultar_emergencias
from inventario.permissions import estaciones_permitidas

def grupo_estacion(estacion_id):
    return f"gps.estacion.{int(estacion_id)}"

@database_sync_to_async
def grupos_autorizados(usuario):
    if not usuario.is_authenticated or not puede_consultar_emergencias(usuario):
        return None
    ids = list(estaciones_permitidas(usuario).values_list("pk", flat=True))
    return [grupo_estacion(estacion_id) for estacion_id in ids]

class MapaPosicionesConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        grupos = await grupos_autorizados(self.scope.get("user"))
        if grupos is None:
            await self.close(code=4403)
            return
        self.grupos_gps = grupos
        for grupo in grupos:
            await self.channel_layer.group_add(grupo, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        for grupo in getattr(self, "grupos_gps", ()):
            await self.channel_layer.group_discard(grupo, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Este canal es exclusivamente de salida; no acepta comandos operativos.
        return

    async def gps_posicion(self, event):
        await self.send_json({"tipo": "posicion.actualizada", "posicion": event["posicion"]})
