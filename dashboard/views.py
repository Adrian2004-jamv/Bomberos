from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from emergencias.models import Emergencia
from emergencias.permissions import puede_consultar_emergencias
from inventario.permissions import estaciones_permitidas

from .pdf import generar_pdf_emergencia
from .services import construir_dashboard, datos_informe_emergencia, emergencias_finalizadas


@login_required
def principal(request):
    contexto = construir_dashboard(request.user, parametros=request.GET)
    contexto["fecha_actual"] = timezone.localdate()

    # Emergencias finalizadas para la nueva sección del dashboard
    if puede_consultar_emergencias(request.user):
        estaciones = estaciones_permitidas(request.user)
        contexto["emergencias_terminadas"] = emergencias_finalizadas(estaciones, limite=10)
    else:
        contexto["emergencias_terminadas"] = []

    return render(request, "dashboard/principal.html", contexto)


@login_required
def resumen_emergencia(request, pk):
    """Vista web con el resumen operativo de una emergencia finalizada."""
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied

    estaciones = estaciones_permitidas(request.user)
    emergencia = get_object_or_404(
        Emergencia.objects.select_related(
            "estacion_responsable__cuerpo_bomberos__canton",
            "registrado_por",
        ).prefetch_related(
            "despliegues__unidad__tipo__categoria",
            "despliegues__estacion_procedencia__cuerpo_bomberos",
            "formularios_sci",
        ),
        pk=pk,
        estacion_responsable__in=estaciones,
        estado__in=("cerrada", "cancelada"),
    )

    datos = datos_informe_emergencia(emergencia)
    return render(request, "dashboard/resumen_emergencia.html", {"datos": datos})


@login_required
def descargar_pdf_emergencia(request, pk):
    """Genera y descarga el informe PDF de una emergencia finalizada."""
    if not puede_consultar_emergencias(request.user):
        raise PermissionDenied

    estaciones = estaciones_permitidas(request.user)
    emergencia = get_object_or_404(
        Emergencia.objects.select_related(
            "estacion_responsable__cuerpo_bomberos__canton",
            "registrado_por",
        ).prefetch_related(
            "despliegues__unidad__tipo__categoria",
            "despliegues__estacion_procedencia__cuerpo_bomberos",
            "formularios_sci",
        ),
        pk=pk,
        estacion_responsable__in=estaciones,
        estado__in=("cerrada", "cancelada"),
    )

    datos = datos_informe_emergencia(emergencia)
    pdf_bytes = generar_pdf_emergencia(datos)

    nombre_archivo = f"Informe_Emergencia_{emergencia.codigo}.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
    return response
