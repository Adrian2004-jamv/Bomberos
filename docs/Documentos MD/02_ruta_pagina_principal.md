# Prompt 2: creación de la ruta de inicio

## Problema

La dirección `http://127.0.0.1:8000/` devolvía un error 404 porque `config.urls` solo tenía las rutas de administración y archivos multimedia.

## Cambios realizados

Se creó la vista `inicio` en `core/views.py`:

```python
def inicio(request):
    return render(request, "PlantillaPrincipal.html")
```

Se conectó la ruta raíz en `config/urls.py`:

```python
path('', views.inicio, name='inicio')
```

La vista utiliza la plantilla `templates/PlantillaPrincipal.html`. En ese momento la plantilla estaba vacía, por lo que la ruta respondía correctamente, aunque sin contenido visual.

## Archivos modificados

- `core/views.py`
- `config/urls.py`

## Verificación

```powershell
python manage.py check
```

Resultado:

```text
System check identified no issues (0 silenced).
```
