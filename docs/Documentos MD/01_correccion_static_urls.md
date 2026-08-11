# Prompt 1: corrección de `static` en las rutas

## Problema

Al ejecutar `python manage.py check`, Django producía:

```text
NameError: name 'static' is not defined
```

`config/urls.py` utilizaba la función `static()` para servir archivos multimedia durante el desarrollo, pero no la había importado.

## Cambio realizado

Se añadió en `config/urls.py`:

```python
from django.conf.urls.static import static
```

Se conservó la configuración existente que incorpora `MEDIA_URL` únicamente cuando `DEBUG` está activo.

## Archivo modificado

- `config/urls.py`

## Verificación

Se ejecutó:

```powershell
python manage.py check
```

Resultado:

```text
System check identified no issues (0 silenced).
```
