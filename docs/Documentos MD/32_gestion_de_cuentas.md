# Gestión de cuentas y clave asignada

## Alcance

Se completó el ciclo de vida de una cuenta institucional: cambio de clave propio, obligación de reemplazar la que asignó otra persona, edición del perfil y del rol, desactivación y restablecimiento de acceso. No se tocaron los permisos de alcance, el registro de emergencias ni los formularios SCI.

El punto de partida era que `usuarios/urls.py` solo ofrecía `lista` y `crear`. Nadie podía cambiar su propia clave, porque no existía ninguna ruta de cambio; el operador de sistemas fija la clave al crear la cuenta con `password1`/`password2`, de modo que conocía la de cada usuario que registraba y el titular no tenía forma de sustituirla. Tampoco se podía corregir un apellido, mover a alguien de estación, cambiarle el rol ni retirarle el acceso al salir de la institución.

## El campo que existía sin usarse

`Usuario.debe_cambiar_clave` estaba declarado desde la primera migración y aparecía en el panel de administración, pero ningún código lo leía. Ahora significa una cosa concreta: **la clave vigente la asignó otra persona**.

Se activa de forma explícita en los tres puntos donde eso ocurre:

1. `UsuarioInstitucionalForm.save`, cuando el operador crea la cuenta.
2. La vista `restablecer_clave`, cuando el operador devuelve el acceso a quien la olvidó.
3. `crear_superusuario_inicial`, tanto al crear como al reiniciar, porque la clave llega en una variable de entorno que la plataforma conoce.

El valor por omisión pasó de verdadero a falso. Con el valor anterior, cualquier cuenta creada desde código —incluidas las de las pruebas— habría nacido bloqueada, y la obligación se habría disparado en sitios donde nadie asignó nada en nombre de otro. La migración `0005_debe_cambiar_clave_explicita` cambia el valor por omisión y normaliza a falso las cuentas existentes: como la marca nunca se leyó, su valor actual es un resto del valor por omisión y no una decisión de nadie, y activarla de golpe habría obligado a todo el padrón a cambiar la clave en su siguiente ingreso.

## Middleware

`usuarios.middleware.ExigirCambioDeClave` devuelve al formulario de cambio cualquier petición de un usuario autenticado que tenga la marca activa. Va al final de la cadena, después de la autenticación —necesita `request.user`— y de los mensajes.

Quedan libres el propio formulario de cambio, el inicio y el cierre de sesión, y los tres recursos de la aplicación web progresiva: manifiesto, service worker y página sin conexión. Sin esas excepciones el formulario se redirigiría a sí mismo, no habría forma de salir de una sesión bloqueada y la PWA perdería su caché.

Las rutas se resuelven la primera vez que se usan y no al importar el módulo, porque el mapa de rutas todavía no está cargado cuando Django arma la cadena de middleware.

Consecuencia esperada en producción: el primer ingreso del superusuario creado en Render exige cambiar la clave, con lo cual la que figura en `DJANGO_SUPERUSER_PASSWORD` deja de servir.

## Vistas y rutas

| Ruta | Vista | Función |
| --- | --- | --- |
| `cambiar-clave/` | `cambiar_clave` | Cambio de la clave propia. `update_session_auth_hash` evita que la sesión se cierre al guardar. |
| `<pk>/editar/` | `editar` | Corrige nombre, cédula, contacto, cargo, estación y rol. |
| `<pk>/actividad/` | `cambiar_actividad` | Desactiva o reactiva. Solo POST. |
| `<pk>/restablecer-clave/` | `restablecer_clave` | El operador asigna una clave nueva y la cuenta queda obligada a reemplazarla. |

Las cuatro acotan la cuenta con `usuarios_administrables`, que ya excluye a los superusuarios y limita el ámbito a la institución del gestor; una cuenta ajena responde 404 y no 403, para no revelar que existe.

No hay borrado de cuentas. `Usuario` está protegido con `PROTECT` desde emergencias, despliegues e historial de inventario, y esos registros deben conservar a su responsable; la desactivación cumple la misma función sin perder la trazabilidad.

Nadie puede desactivarse a sí mismo, y quien intenta restablecer su propia clave desde el listado va al formulario de cambio normal: el restablecimiento marca la cuenta como pendiente y cambia el hash de sesión, de modo que el operador se habría bloqueado y expulsado a sí mismo.

## Rol vigente en la edición

El desplegable de roles ofrece solo los que el gestor puede otorgar: el operador de sistemas reparte los cuatro operativos y el superusuario suma los dos de alcance ampliado. Eso deja fuera roles como «Administrador del sistema», que sí pueden estar asignados a una cuenta administrable.

Si el formulario se limitara a esa lista, corregir el teléfono de una cuenta con ese rol la habría degradado en silencio al guardar. Por eso `UsuarioEdicionForm` agrega siempre el rol actual de la cuenta a las opciones disponibles: se conserva si no se toca, y el gestor sigue pudiendo moverla a cualquiera de los roles que sí otorga.

## Interfaz

El listado de cuentas incorpora una columna de acciones con editar, restablecer clave y desactivar o reactivar, y marca «Clave pendiente» junto al estado mientras la cuenta no haya reemplazado la que le asignaron. El botón de desactivar no aparece en la fila del propio gestor.

`templates/usuarios/formulario.html` sirve ahora el alta y la edición desde el contexto. El menú lateral suma **Cambiar contraseña** junto a cerrar sesión.

## Verificación

- `python manage.py check`: sin problemas.
- `python manage.py makemigrations --check`: sin cambios pendientes.
- `python manage.py test usuarios`: 39 pruebas correctas.
- `python manage.py test`: 256 pruebas correctas.
- Comprobación manual sobre la base local: con la marca activa, `/inventario/` redirige al formulario de cambio, que explica el motivo y no ofrece cancelar; el listado de cuentas muestra las acciones y omite la desactivación propia.
