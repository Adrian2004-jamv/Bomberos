# Primera etapa de la aplicación web progresiva

## Alcance

Se convirtió la interfaz en una PWA instalable sin incorporar almacenamiento GPS offline, sincronización en segundo plano, formularios SCI ni notificaciones push.

## Componentes

- Manifiesto público en `/manifest.json`, con identidad, colores, alcance raíz e iconos de 192 y 512 px.
- Service worker público en `/service-worker.js`, servido como JavaScript y autorizado para controlar `/`.
- Página institucional segura en `/sin-conexion/`.
- Controles accesibles de instalación, estado de conexión y actualización disponible.
- Reconexión inmediata del mapa al recibir el evento `online`, conservando su respaldo HTTP periódico.

## Estrategias de caché

- **Estáticos propios:** cache-first únicamente para CSS, JavaScript, imágenes y fuentes bajo `/static/`.
- **Navegación HTML:** network-first y página offline si falla la red. Las respuestas HTML privadas nunca se guardan.
- **GPS, GeoJSON, recorridos, API y WebSockets:** solo red y exclusión explícita de Cache Storage.
- **POST, PUT, PATCH y DELETE:** pasan a la red y nunca se almacenan.
- **Recursos externos y teselas:** no se interceptan ni precargan.

Al cerrar sesión se elimina cualquier caché identificado como dependiente de sesión. La caché estática pública puede conservarse porque no contiene datos de usuario.

## Seguridad

No se almacenan credenciales, tokens, sesiones, CSRF, usuarios, inventarios, coordenadas, recorridos ni datos operativos. El evento `online` es solo un indicador visual y no se interpreta como garantía de que el servidor responda.

## Producción

Los service workers y la geolocalización requieren HTTPS, salvo la excepción de desarrollo en `localhost`. Los WebSockets deben utilizar `wss://` cuando la página se sirve por HTTPS.

## Verificación

Las pruebas comprueban manifiesto, MIME, campos mínimos, iconos, service worker, alcance, página offline, integración de plantilla, exclusiones sensibles y ausencia de credenciales. La instalación y Cache Storage se verifican adicionalmente con las herramientas del navegador.
