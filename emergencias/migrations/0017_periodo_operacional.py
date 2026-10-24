"""El periodo operacional pasa de ser un número suelto a una tabla del incidente.

La 0016 lo guardó como un entero dentro de cada formulario. Eso alcanza para
numerarlos, pero no para lo que el SCI pide del periodo: su inicio, su fin, y que
los tres o cuatro documentos de un mismo periodo declaren las mismas fechas. Esos
datos vivían como texto dentro del JSON de cada formulario, de modo que nada
impedía que el SCI-202 y el SCI-214 del periodo 2 dijeran cosas distintas.

El traslado no pierde nada: por cada número de periodo que ya exista en una
emergencia se crea su fila, y los formularios quedan apuntando a ella. Las fechas
de inicio que hubiera escritas en el JSON se adoptan como el inicio del periodo;
si no hay ninguna, se usa la fecha de creación del formulario más antiguo de ese
periodo, que es lo más cercano a la verdad que consta.
"""

from django.conf import settings
from django.db import migrations, models
from django.utils import timezone
import django.db.models.deletion


def _fecha_declarada(formulario):
    """La fecha de inicio del periodo que alguien escribió en el formulario."""
    valor = (formulario.datos or {}).get("periodo_inicio")
    if not valor:
        return None
    # El control del navegador entrega «AAAA-MM-DDTHH:MM»; cualquier otra cosa
    # es un valor viejo escrito a mano y no se fuerza.
    fecha = timezone.datetime.fromisoformat(str(valor)) if "T" in str(valor) else None
    if fecha is None:
        return None
    if timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha, timezone.get_default_timezone())
    return fecha


def crear_los_periodos(apps, schema_editor):
    Emergencia = apps.get_model("emergencias", "Emergencia")
    FormularioSCI = apps.get_model("emergencias", "FormularioSCI")
    PeriodoOperacional = apps.get_model("emergencias", "PeriodoOperacional")

    for emergencia in Emergencia.objects.all().iterator():
        formularios = list(
            FormularioSCI.objects.filter(emergencia=emergencia).order_by("pk")
        )
        # Toda emergencia necesita su periodo 1, tenga formularios o no: es el
        # periodo en el que se la atendió.
        numeros = sorted({f.numero_periodo for f in formularios} | {1})

        # Primero se averigua cuándo empezó cada uno; el fin de un periodo es el
        # inicio del siguiente, que es la única fecha de cierre que consta.
        inicios = {}
        for numero in numeros:
            del_numero = [f for f in formularios if f.numero_periodo == numero]
            declarada = next(
                (d for d in (_fecha_declarada(f) for f in del_numero) if d), None
            )
            inicios[numero] = declarada or (
                min(f.fecha_creacion for f in del_numero)
                if del_numero else emergencia.fecha_reporte
            )

        periodos = {}
        for posicion, numero in enumerate(numeros):
            siguiente = numeros[posicion + 1] if posicion + 1 < len(numeros) else None
            fin = inicios[siguiente] if siguiente is not None else None
            # Una fecha escrita a mano puede ser posterior a la del periodo que
            # le sigue; antes que violar la restricción se deja el periodo
            # abierto, que describe mejor «no consta» que una fecha inventada.
            if fin is not None and fin < inicios[numero]:
                fin = None
            periodos[numero] = PeriodoOperacional.objects.create(
                emergencia=emergencia,
                numero=numero,
                inicio=inicios[numero],
                fin=fin,
            )
        for formulario in formularios:
            formulario.periodo = periodos[formulario.numero_periodo]
            formulario.save(update_fields=["periodo"])


def deshacer_los_periodos(apps, schema_editor):
    """Devuelve el número al formulario para poder volver a la 0016."""
    FormularioSCI = apps.get_model("emergencias", "FormularioSCI")
    for formulario in FormularioSCI.objects.select_related("periodo").iterator():
        formulario.numero_periodo = formulario.periodo.numero
        formulario.save(update_fields=["numero_periodo"])


class Migration(migrations.Migration):

    dependencies = [
        ("emergencias", "0016_formulariosci_numero_periodo"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── 1. La tabla ──────────────────────────────────────────────────
        migrations.CreateModel(
            name="PeriodoOperacional",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("numero", models.PositiveSmallIntegerField(
                    verbose_name="número de periodo operacional")),
                ("inicio", models.DateTimeField(default=timezone.now,
                                                verbose_name="fecha y hora de inicio")),
                ("fin", models.DateTimeField(blank=True, null=True,
                                             verbose_name="fecha y hora de finalización")),
                ("motivo", models.TextField(
                    blank=True,
                    help_text="Por qué se abrió este periodo. El primero no lo necesita.",
                    verbose_name="motivo de la reactivación")),
                ("fecha_creacion", models.DateTimeField(auto_now_add=True)),
                ("abierto_por", models.ForeignKey(
                    blank=True, editable=False, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="periodos_operacionales_abiertos",
                    to=settings.AUTH_USER_MODEL)),
                ("emergencia", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="periodos", to="emergencias.emergencia",
                    verbose_name="emergencia")),
            ],
            options={
                "verbose_name": "periodo operacional",
                "verbose_name_plural": "periodos operacionales",
                "ordering": ("emergencia", "numero"),
            },
        ),
        migrations.AddConstraint(
            model_name="periodooperacional",
            constraint=models.UniqueConstraint(
                fields=("emergencia", "numero"),
                name="periodo_operacional_unico_por_emergencia"),
        ),
        migrations.AddConstraint(
            model_name="periodooperacional",
            constraint=models.CheckConstraint(
                condition=models.Q(("fin__isnull", True))
                | models.Q(("fin__gte", models.F("inicio"))),
                name="periodo_operacional_fin_no_anterior_al_inicio"),
        ),

        # ── 2. El vínculo, primero opcional para poder rellenarlo ────────
        migrations.AddField(
            model_name="formulariosci",
            name="periodo",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="formularios", to="emergencias.periodooperacional",
                verbose_name="periodo operacional"),
        ),
        migrations.RunPython(crear_los_periodos, deshacer_los_periodos),

        # ── 3. Ya relleno, el vínculo se vuelve obligatorio ──────────────
        migrations.AlterField(
            model_name="formulariosci",
            name="periodo",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="formularios", to="emergencias.periodooperacional",
                verbose_name="periodo operacional"),
        ),
        migrations.RemoveConstraint(
            model_name="formulariosci",
            name="formulario_sci_unico_por_emergencia_y_periodo",
        ),
        migrations.RemoveField(model_name="formulariosci", name="numero_periodo"),
        migrations.AlterModelOptions(
            name="formulariosci",
            options={"ordering": ("codigo_sci", "periodo__numero", "pk"),
                     "verbose_name": "formulario SCI",
                     "verbose_name_plural": "formularios SCI"},
        ),
        migrations.AddConstraint(
            model_name="formulariosci",
            constraint=models.UniqueConstraint(
                fields=("emergencia", "codigo_sci", "periodo"),
                name="formulario_sci_unico_por_emergencia_y_periodo"),
        ),

        # ── 4. Las dos firmas que pedía el formulario oficial ────────────
        migrations.AddField(
            model_name="formulariosci",
            name="aprobado_por",
            field=models.CharField(blank=True, max_length=150,
                                   verbose_name="aprobado por"),
        ),
        migrations.AddField(
            model_name="formulariosci",
            name="posicion_preparado_por",
            field=models.CharField(blank=True, max_length=150,
                                   verbose_name="posición de quien prepara"),
        ),
    ]
