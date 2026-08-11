import json
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import cache_control, never_cache
from django.views.decorators.http import require_GET


def inicio(request):
    return redirect("dashboard:principal")


@require_GET
@never_cache
def manifiesto(request):
    return JsonResponse(
        {
            "id": "/",
            "name": "Sistema de Bomberos de Cotopaxi",
            "short_name": "Bomberos Cotopaxi",
            "description": "Gestión institucional de inventarios, capacidades operativas y emergencias.",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": "#f5f7fa",
            "theme_color": "#b5121b",
            "lang": "es-EC",
            "orientation": "any",
            "icons": [
                {
                    "src": "/static/pwa/icons/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": "/static/pwa/icons/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": "/static/pwa/icons/icon-maskable-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable",
                },
            ],
        },
        json_dumps_params={"ensure_ascii": False},
        content_type="application/manifest+json",
    )


@require_GET
@never_cache
def service_worker(request):
    ruta = Path(settings.BASE_DIR) / "static" / "pwa" / "service-worker.js"
    response = HttpResponse(
        ruta.read_text(encoding="utf-8"),
        content_type="application/javascript; charset=utf-8",
    )
    response["Service-Worker-Allowed"] = "/"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_GET
@cache_control(public=True, max_age=3600)
def sin_conexion(request):
    return render(request, "core/sin_conexion.html")
