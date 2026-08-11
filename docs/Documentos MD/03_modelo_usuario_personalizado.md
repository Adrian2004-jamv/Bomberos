# Prompt 3: modelo de usuario personalizado

## Auditoría previa

Antes de realizar cambios se comprobó que:

- `Bomberos.db` existía, pero medía 0 bytes.
- No contenía tablas ni información.
- No existían migraciones propias aplicadas.
- Era seguro configurar el modelo personalizado antes de crear las tablas iniciales.

No se eliminó ni reemplazó la base de datos.

## Modelo creado

Se creó `usuarios.Usuario`, heredando de `AbstractUser`, con estos campos adicionales:

- `cedula`: texto de hasta 10 caracteres y valor único.
- `telefono`: texto opcional de hasta 15 caracteres.
- `cargo_institucional`: texto opcional de hasta 100 caracteres.
- `debe_cambiar_clave`: booleano con valor inicial `True`.
- `fecha_actualizacion`: fecha y hora actualizadas automáticamente.

El método `__str__` devuelve el nombre completo o, si no existe, el nombre de usuario.

## Configuración

En `config/settings.py` se añadió:

```python
AUTH_USER_MODEL = "usuarios.Usuario"
```

## Django Admin

El modelo se registró con una clase basada en `UserAdmin`. Se añadieron los campos institucionales a las pantallas de creación y edición, columnas útiles en el listado y búsquedas por usuario, cédula, nombres, apellidos y correo.

`fecha_actualizacion` quedó como campo de solo lectura.

## Archivos modificados o creados

- `usuarios/models.py`
- `usuarios/admin.py`
- `config/settings.py`
- `usuarios/migrations/0001_initial.py`

## Migraciones y verificación

Se ejecutaron:

```powershell
python manage.py makemigrations usuarios
python manage.py migrate
python manage.py check
```

Resultado final:

```text
System check identified no issues (0 silenced).
Modelo: usuarios.Usuario
Usuarios: 0
```
