# Prompt 9: preparación del repositorio Git

## Auditoría previa

Se revisó la estructura completa del proyecto. `git status` y `git remote -v` confirmaron que la carpeta todavía no era un repositorio Git.

No se eliminaron archivos, bases de datos ni migraciones.

## Archivos de preparación

Se creó `.gitignore` para excluir:

- cachés y bytecode de Python;
- entornos virtuales;
- bases SQLite locales, incluida `Bomberos.db`;
- contenido de `media` y archivos generados en `staticfiles`;
- variables de entorno, secretos y posibles claves privadas;
- registros y resultados de cobertura;
- configuraciones de editores;
- archivos del sistema operativo;
- artefactos de empaquetado y cachés de herramientas.

Las migraciones, aplicaciones, plantillas, archivos fuente de `static`, documentación, `manage.py`, `requirements.txt` y `README.md` no se ignoran.

## Configuración de Django

`config/settings.py` ahora obtiene la clave mediante:

```python
os.environ.get("DJANGO_SECRET_KEY", valor_de_desarrollo)
```

El valor alternativo está identificado como inseguro para producción. `DJANGO_DEBUG` controla `DEBUG`, cuyo valor predeterminado `True` se documenta como exclusivo del desarrollo local.

No se instalaron dependencias adicionales.

## Dependencias y documentación

Se creó `requirements.txt` únicamente con:

```text
Django==6.1
```

Se creó el `README.md` principal con propósito académico, módulos actuales, requisitos, ejecución local, variables de entorno y advertencia contra datos reales sensibles.

## Git local

Se inicializó un repositorio vacío con rama principal `main` y se configuró:

```text
origin  git@github.com:PonchitoEC/Desarrollo_Sistema_web_Bomberos.git
```

No se ejecutaron `git add`, `git commit`, `git push` ni `git pull`.

## Archivos creados o modificados

- `.gitignore`
- `README.md`
- `requirements.txt`
- `config/settings.py`
- `docs/Documentos MD/README.md`
- `docs/Documentos MD/09_preparacion_repositorio_git.md`
- `.git/` como metadatos locales del repositorio

## Verificación

```text
System check identified no issues (0 silenced).
```

El repositorio quedó detenido antes del primer commit para revisión manual.
