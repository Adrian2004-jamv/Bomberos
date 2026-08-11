# Prompt 5: relación usuario-estación y grupos

## Auditoría previa

Se confirmó que:

- Las migraciones iniciales de `usuarios` e `instituciones` estaban aplicadas.
- Existían 0 usuarios, 0 estaciones y 0 grupos.
- No había conflictos de datos.

## Relación `Usuario` → `Estacion`

Se añadió a `usuarios.Usuario`:

```python
estacion = models.ForeignKey(
    "instituciones.Estacion",
    on_delete=models.PROTECT,
    related_name="usuarios",
    verbose_name="estación",
    null=True,
    blank=True,
)
```

La relación es temporalmente opcional. `PROTECT` evita eliminar una estación que tenga usuarios asignados.

La estructura institucional de un usuario puede consultarse así:

```python
usuario.estacion
usuario.estacion.cuerpo_bomberos
usuario.estacion.cuerpo_bomberos.canton
```

Los usuarios de una estación se obtienen con:

```python
estacion.usuarios.all()
```

## Django Admin

Se añadió la estación:

- a las pantallas de creación y edición;
- al listado de usuarios;
- a los filtros;
- a las búsquedas por nombre y código de estación.

También se conservaron los controles nativos de grupos y permisos de `UserAdmin`.

## Grupos iniciales

Una migración de datos reproducible creó:

- Administrador del sistema.
- Responsable provincial.
- Responsable institucional.
- Responsable de estación.
- Encargado de inventario.
- Operador de consulta.

Se utilizó `get_or_create` para evitar duplicados. No se asignaron permisos detallados ni se crearon usuarios de demostración.

Los grupos permiten administrar permisos de forma centralizada, admitir varios grupos por usuario y utilizar directamente el sistema de autorización de Django, evitando un campo `rol` de texto difícil de validar y mantener.

## Archivos modificados o creados

- `usuarios/models.py`
- `usuarios/admin.py`
- `usuarios/migrations/0002_usuario_estacion.py`
- `usuarios/migrations/0003_crear_grupos_iniciales.py`

## Verificación

```text
System check identified no issues (0 silenced).
No changes detected
Usuarios: 0
Grupos: 6
```

Cada grupo quedó creado con 0 permisos, según el alcance solicitado.
