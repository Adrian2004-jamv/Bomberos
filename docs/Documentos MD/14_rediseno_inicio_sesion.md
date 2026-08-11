# Prompt 14: rediseño moderno del inicio de sesión

## Objetivo

Reducir la apariencia de plantilla genérica del acceso y darle una identidad más sencilla, moderna e institucional, manteniendo intactos el flujo de autenticación, rutas, campos, CSRF y mensajes de error.

## Cambios visuales

La pantalla ahora utiliza una pieza central contenida sobre un fondo neutro, en lugar de dividir todo el viewport en dos mitades rígidas.

El panel institucional mantiene azul oscuro relacionado con coordinación y respuesta, con rojo y naranja usados solo como acentos. Se redujo el tamaño del titular, se simplificó la información y se agregó una identidad compacta de Bomberos Cotopaxi.

El formulario incorpora:

- jerarquía tipográfica más compacta;
- campos con iconos discretos y estados de foco visibles;
- botón de acceso con una interacción ligera;
- alerta de error más clara;
- ayuda institucional sin credenciales de demostración;
- adaptación específica para tabletas y teléfonos.

## Archivos modificados

- `templates/usuarios/login.html`
- `static/css/login.css`
- `docs/Documentos MD/README.md`
- `docs/Documentos MD/14_rediseno_inicio_sesion.md`

## Verificación

```text
System check identified no issues (0 silenced).
Found 8 test(s).
Ran 8 tests
OK
```

No se modificaron rutas, modelos, migraciones ni lógica de autenticación.
