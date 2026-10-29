"""Fase 1 de «el periodo operacional es solo del SCI-201»: los datos.

La 0016-0018 repartieron TODOS los formularios por periodo: un SCI-202, un SCI-211,
un SCI-214 por cada periodo, y al iniciar el siguiente los anteriores quedaban
bloqueados. El Cuerpo de Bomberos pidió que el periodo sea únicamente del SCI-201 y
que los demás formularios vuelvan a guardarse una sola vez por emergencia.

Esta migración no cambia ninguna restricción: deja los datos listos para que la
siguiente (0022) pueda imponerlas. Va en dos migraciones porque PostgreSQL no deja
alterar una tabla en la misma transacción en que se movieron sus filas.

Qué pasa con las emergencias que ya tienen más de un periodo (nada se pierde):

* Un formulario distinto del 201 que existe en varios periodos se queda con UN
  registro: el del periodo más reciente, que es el que estaba vigente. Lo que
  contenían los demás no se borra: viaja dentro de ese mismo registro, en la clave
  reservada ``_periodos_anteriores`` de su JSON (con el número del periodo, su
  estado, quién lo preparó y todos sus datos), y el editor la conserva intacta en
  cada guardado.
* Lo mismo con el SCI-211: queda la cabecera del periodo más reciente y los
  registros de recursos de las demás pasan a ella, con su orden y a continuación
  de los que ya tenía. Ninguna fila de recursos se elimina.
* Todo formulario que no es el 201 pierde la referencia al periodo.
* El SCI-201 no se toca: conserva todos sus periodos.

El camino inverso devuelve cada formulario al periodo vigente de su emergencia (o
crea el periodo 1 si no hay ninguno), pero no puede volver a separar lo que se
unificó: los datos de los periodos anteriores se quedan en ``_periodos_anteriores``.
"""

from django.db import migrations, models

RESPALDO = "_periodos_anteriores"


def _sello(formulario):
    periodo = formulario.periodo
    return {
        "periodo": periodo.numero if periodo else None,
        "inicio": periodo.inicio.isoformat() if periodo else None,
        "fin": periodo.fin.isoformat() if periodo and periodo.fin else None,
        "estado": formulario.estado,
        "preparado_por": formulario.preparado_por,
        "aprobado_por": formulario.aprobado_por,
        "posicion_preparado_por": formulario.posicion_preparado_por,
        "datos": formulario.datos or {},
    }


def unificar(apps, schema_editor):
    FormularioSCI = apps.get_model("emergencias", "FormularioSCI")
    FormularioSCI211 = apps.get_model("emergencias", "FormularioSCI211")
    RegistroRecursoSCI211 = apps.get_model("emergencias", "RegistroRecursoSCI211")

    # ── Formularios genéricos ───────────────────────────────────────────────
    grupos = {}
    for formulario in (
        FormularioSCI.objects.exclude(codigo_sci="201")
        .select_related("periodo").order_by("emergencia_id", "codigo_sci")
    ):
        grupos.setdefault((formulario.emergencia_id, formulario.codigo_sci), []).append(formulario)

    for formularios in grupos.values():
        # El más reciente primero: el del periodo con el número más alto.
        formularios.sort(
            key=lambda f: (f.periodo.numero if f.periodo else 0, f.pk), reverse=True
        )
        vigente, anteriores = formularios[0], formularios[1:]
        if anteriores:
            datos = dict(vigente.datos or {})
            guardados = list(datos.get(RESPALDO) or [])
            guardados.extend(_sello(f) for f in reversed(anteriores))
            datos[RESPALDO] = guardados
            vigente.datos = datos
            vigente.save(update_fields=["datos"])
            FormularioSCI.objects.filter(pk__in=[f.pk for f in anteriores]).delete()

    FormularioSCI.objects.exclude(codigo_sci="201").update(periodo=None)

    # ── SCI-211 ─────────────────────────────────────────────────────────────
    por_emergencia = {}
    for formulario in FormularioSCI211.objects.select_related("periodo").order_by("emergencia_id"):
        por_emergencia.setdefault(formulario.emergencia_id, []).append(formulario)

    for formularios in por_emergencia.values():
        if len(formularios) < 2:
            continue
        formularios.sort(key=lambda f: (f.periodo.numero, f.pk), reverse=True)
        vigente, anteriores = formularios[0], formularios[1:]
        siguiente = (
            RegistroRecursoSCI211.objects.filter(formulario=vigente)
            .aggregate(maximo=models.Max("orden"))["maximo"] or 0
        )
        for anterior in reversed(anteriores):  # del periodo más viejo al más nuevo
            for registro in RegistroRecursoSCI211.objects.filter(
                formulario=anterior
            ).order_by("orden", "pk"):
                siguiente += 1
                # Un despliegue solo puede constar una vez por formulario: si el
                # de la cabecera vigente ya lo tiene, la fila se conserva igual,
                # sin el vínculo.
                if registro.despliegue_id and RegistroRecursoSCI211.objects.filter(
                    formulario=vigente, despliegue_id=registro.despliegue_id
                ).exists():
                    registro.despliegue = None
                registro.formulario = vigente
                registro.orden = siguiente
                registro.save(update_fields=["formulario", "orden", "despliegue"])
        FormularioSCI211.objects.filter(pk__in=[f.pk for f in anteriores]).delete()
        # El número del formulario deja de llevar el sufijo del periodo.
        if "-P" in vigente.codigo:
            base = vigente.codigo.rsplit("-P", 1)[0]
            if not FormularioSCI211.objects.filter(codigo=base).exists():
                vigente.codigo = base
                vigente.save(update_fields=["codigo"])


def devolver_periodos(apps, schema_editor):
    """Camino inverso: cada formulario vuelve al periodo vigente de su emergencia."""
    Emergencia = apps.get_model("emergencias", "Emergencia")
    FormularioSCI = apps.get_model("emergencias", "FormularioSCI")
    PeriodoOperacional = apps.get_model("emergencias", "PeriodoOperacional")

    pendientes = FormularioSCI.objects.filter(periodo__isnull=True)
    for emergencia_id in pendientes.values_list("emergencia_id", flat=True).distinct():
        periodo = (
            PeriodoOperacional.objects.filter(emergencia_id=emergencia_id)
            .order_by("-numero").first()
        )
        if periodo is None:
            emergencia = Emergencia.objects.get(pk=emergencia_id)
            periodo = PeriodoOperacional.objects.create(
                emergencia=emergencia, numero=1, inicio=emergencia.fecha_reporte,
            )
        pendientes.filter(emergencia_id=emergencia_id).update(periodo=periodo)


class Migration(migrations.Migration):

    dependencies = [
        ("emergencias", "0020_sin_motivo_broma"),
    ]

    operations = [
        migrations.AlterField(
            model_name="formulariosci",
            name="periodo",
            field=models.ForeignKey(
                blank=True, null=True,
                help_text="Solo el SCI-201 trabaja por periodo operacional.",
                on_delete=models.deletion.PROTECT, related_name="formularios",
                to="emergencias.periodooperacional",
                verbose_name="periodo operacional",
            ),
        ),
        migrations.RunPython(unificar, devolver_periodos),
    ]
