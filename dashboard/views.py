from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .services import construir_dashboard

@login_required
def principal(request):
    contexto = construir_dashboard(request.user)
    contexto["fecha_actual"] = timezone.localdate()
    return render(request, "dashboard/principal.html", contexto)
