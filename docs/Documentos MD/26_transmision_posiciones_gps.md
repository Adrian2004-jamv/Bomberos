# Captura y almacenamiento de posiciones GPS

## Alcance

Se implementó la transmisión voluntaria de posiciones del navegador para una unidad con despliegue activo. No se incorporaron mapas, WebSockets, almacenamiento offline, service worker ni PWA.

## Implementación

- `PosicionUnidad` conserva el recorrido histórico por despliegue.
- Registra coordenadas, precisión, velocidad, rumbo, altitud, fecha del dispositivo, recepción del servidor, usuario y fuente.
- Los índices optimizan la última posición por despliegue y las consultas cronológicas.
- `registrar_posicion_unidad` centraliza validación, autorización y persistencia transaccional.
- El endpoint POST recibe exclusivamente JSON autenticado y protegido por CSRF.
- El endpoint GET devuelve únicamente la última posición autorizada.
- La pantalla GPS requiere que el usuario presione **Iniciar transmisión**.

## Frecuencia del prototipo

El navegador envía la primera posición y después una nueva cuando han transcurrido al menos 15 segundos o existe un desplazamiento mínimo de 10 metros. Mantiene en memoria como máximo cinco posiciones pendientes; no existe persistencia offline.

## Seguridad y privacidad

- Solo se aceptan despliegues activos y emergencias no cerradas ni canceladas.
- El usuario debe poder gestionar la estación de procedencia.
- Los usuarios de consulta pueden consultar la última posición de su ámbito, pero no transmitir.
- La captura se detiene ante pérdida de autorización, sesión expirada o finalización del despliegue.
- La geolocalización requiere HTTPS en producción; `localhost` puede utilizarla durante desarrollo.
- No se guardan credenciales ni tokens en JavaScript.

## Verificación

Se añadieron pruebas para validadores, servicio, historial, autenticación, permisos, CSRF, métodos HTTP, JSON, última posición y aislamiento institucional.
