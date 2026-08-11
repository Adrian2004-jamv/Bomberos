# Mapa operativo de unidades desplegadas

## Alcance

Se creó el SIG Web operativo para consultar emergencias activas, despliegues y últimas posiciones GPS autorizadas. La actualización utiliza peticiones periódicas; no se incorporaron WebSockets, PWA ni mapas offline.

## Componentes

- Vista autenticada `/mapa/`.
- Endpoint GeoJSON `/mapa/datos/`.
- Endpoint de recorrido `/mapa/recorridos/<id>/`.
- Leaflet 1.9.4 almacenado localmente.
- OpenStreetMap como capa de teselas con atribución visible.
- Marcadores diferenciados de emergencias y unidades.
- Recorrido reciente limitado a 200 puntos del despliegue seleccionado.
- Lista textual accesible para unidades con y sin posición GPS.

## Actualización y antigüedad

El navegador actualiza los datos cada 10 segundos cuando la pestaña está visible. La clasificación se calcula con la recepción del servidor:

- reciente: hasta 60 segundos;
- con retraso: hasta 300 segundos;
- sin actualización prolongada: más de 300 segundos;
- esperando primera posición: sin historial GPS.

## Seguridad

Los filtros se aplican después de construir el ámbito permitido del usuario y nunca amplían su acceso. Los endpoints no entregan recorridos ni unidades pertenecientes a instituciones o estaciones no autorizadas. Los textos de los popups se escapan antes de insertarse en HTML.

## Responsive

La interfaz es mobile-first, ofrece filtros plegables, controles táctiles, lista alternativa, leyenda textual y estados que no dependen únicamente del color.
