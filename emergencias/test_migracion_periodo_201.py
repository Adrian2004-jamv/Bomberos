"""Las migraciones 0021 y 0022 unifican lo que ya existía por periodo sin perder nada.

Hasta la 0020 todos los formularios SCI tenían un registro por periodo operacional.
Ahora solo el SCI-201 trabaja por periodo, de modo que las emergencias que ya pasaron
por más de un periodo traen registros duplicados de los demás formularios. Estas
pruebas arman ese estado —con el esquema de la 0020—, migran hacia delante con datos
dentro y comprueban lo que queda: un solo registro por formulario, el contenido de
los periodos anteriores a salvo, ninguna fila de recursos perdida y el SCI-201 intacto.
"""

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

ANTES = [("emergencias", "0020_sin_motivo_broma")]
DESPUES = [("emergencias", "0022_restricciones_del_periodo_solo_201")]


class MigracionDelPeriodoTests(TransactionTestCase):
    # Como las demás pruebas transaccionales del proyecto, vacía las tablas al
    # terminar (también los grupos que crea una migración de datos). Django las
    # ejecuta después de todas las demás, de modo que no estorba a ninguna.

    def migrar(self, destino):
        ejecutor = MigrationExecutor(connection)
        ejecutor.migrate(destino)
        return ejecutor.loader.project_state(destino).apps

    def tearDown(self):
        ejecutor = MigrationExecutor(connection)
        ejecutor.migrate(ejecutor.loader.graph.leaf_nodes())
        super().tearDown()

    def armar_estado_antiguo(self, apps):
        Canton = apps.get_model("instituciones", "Canton")
        Cuerpo = apps.get_model("instituciones", "CuerpoBomberos")
        Estacion = apps.get_model("instituciones", "Estacion")
        Usuario = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
        Emergencia = apps.get_model("emergencias", "Emergencia")
        Periodo = apps.get_model("emergencias", "PeriodoOperacional")
        Formulario = apps.get_model("emergencias", "FormularioSCI")
        F211 = apps.get_model("emergencias", "FormularioSCI211")
        Registro = apps.get_model("emergencias", "RegistroRecursoSCI211")

        canton = Canton.objects.create(nombre="Mig", codigo="MIG-T")
        cuerpo = Cuerpo.objects.create(
            canton=canton, nombre="Bomberos Mig", sigla="MIG-T",
            ruc="0599999999041", direccion="Dirección",
        )
        estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo, nombre="Estación Mig", codigo="EP-MIG",
            direccion="Centro", latitud="-0.930000", longitud="-78.610000",
        )
        usuario = Usuario.objects.create(username="mig", cedula="0500000777")
        ahora = timezone.now()
        emergencia = Emergencia.objects.create(
            codigo="MIG-001", tipo_emergencia="Incendio", fecha_reporte=ahora,
            direccion="Calle", estado="en_atencion",
            estacion_responsable=estacion, registrado_por=usuario,
        )
        p1 = Periodo.objects.create(
            emergencia=emergencia, numero=1, inicio=ahora, fin=ahora,
        )
        p2 = Periodo.objects.create(
            emergencia=emergencia, numero=2, inicio=ahora, motivo="Relevo",
        )

        def formulario(codigo, periodo, datos, estado="borrador", preparado=""):
            return Formulario.objects.create(
                emergencia=emergencia, codigo_sci=codigo, periodo=periodo, datos=datos,
                estado=estado, preparado_por=preparado,
                creado_por=usuario, modificado_por=usuario,
            )

        # El 201 vive en los dos periodos; el 202 también (y debe unificarse);
        # el 214 solo en el primero.
        formulario("201", p1, {"objetivos_iniciales": "Uno"}, "finalizado", "Capitán Vaca")
        formulario("201", p2, {"objetivos_iniciales": "Dos"})
        formulario("202", p1, {"objetivos": "Plan del periodo uno"}, "finalizado", "Capitán Vaca")
        formulario("202", p2, {"objetivos": "Plan del periodo dos"}, "borrador", "Teniente Chango")
        formulario("214", p1, {"actividades": [{"hora": "09:15", "evento": "Arribo"}]})

        def cabecera(codigo, periodo):
            return F211.objects.create(
                emergencia=emergencia, periodo=periodo, codigo=codigo,
                punto_registro="Puesto de Comando", registrador_1="Capitán Vaca",
                creado_por=usuario, modificado_por=usuario,
            )

        c1 = cabecera("SCI-211-MIG-001", p1)
        c2 = cabecera("SCI-211-MIG-001-P2", p2)
        for cabecera_, nombre in ((c1, "Autobomba 1"), (c1, "Ambulancia 1"), (c2, "Autobomba 2")):
            Registro.objects.create(
                formulario=cabecera_, solicitado_por="Mando", fecha_hora_solicitud=ahora,
                clase_recurso="Vehículos", institucion_procedencia="Bomberos",
                matricula_identificacion=nombre, estado_recurso="disponible",
                asignado_a="Escena",
                orden=Registro.objects.filter(formulario=cabecera_).count() + 1,
            )
        return emergencia.pk

    def test_unifica_sin_perder_nada(self):
        apps = self.migrar(ANTES)
        emergencia_pk = self.armar_estado_antiguo(apps)

        apps = self.migrar(DESPUES)
        Formulario = apps.get_model("emergencias", "FormularioSCI")
        F211 = apps.get_model("emergencias", "FormularioSCI211")
        Registro = apps.get_model("emergencias", "RegistroRecursoSCI211")

        # El SCI-201 conserva sus dos periodos, con su periodo.
        del_201 = Formulario.objects.filter(emergencia_id=emergencia_pk, codigo_sci="201")
        self.assertEqual(sorted(f.periodo.numero for f in del_201), [1, 2])

        # El 202 queda en un solo registro, el del periodo más reciente, sin periodo…
        del_202 = Formulario.objects.get(emergencia_id=emergencia_pk, codigo_sci="202")
        self.assertIsNone(del_202.periodo_id)
        self.assertEqual(del_202.datos["objetivos"], "Plan del periodo dos")
        self.assertEqual(del_202.preparado_por, "Teniente Chango")
        # …y lo del periodo uno viaja dentro, entero.
        respaldo = del_202.datos["_periodos_anteriores"]
        self.assertEqual(len(respaldo), 1)
        self.assertEqual(respaldo[0]["periodo"], 1)
        self.assertEqual(respaldo[0]["estado"], "finalizado")
        self.assertEqual(respaldo[0]["preparado_por"], "Capitán Vaca")
        self.assertEqual(respaldo[0]["datos"], {"objetivos": "Plan del periodo uno"})

        # Un formulario que solo existía en un periodo se queda como estaba, sin periodo.
        del_214 = Formulario.objects.get(emergencia_id=emergencia_pk, codigo_sci="214")
        self.assertIsNone(del_214.periodo_id)
        self.assertNotIn("_periodos_anteriores", del_214.datos)
        self.assertEqual(del_214.datos["actividades"][0]["evento"], "Arribo")

        # El SCI-211: una sola cabecera, sin sufijo de periodo, con TODAS las filas.
        cabeceras = F211.objects.filter(emergencia_id=emergencia_pk)
        self.assertEqual(cabeceras.count(), 1)
        self.assertEqual(cabeceras.get().codigo, "SCI-211-MIG-001")
        filas = list(Registro.objects.filter(formulario__emergencia_id=emergencia_pk)
                     .order_by("orden"))
        self.assertEqual(
            sorted(f.matricula_identificacion for f in filas),
            ["Ambulancia 1", "Autobomba 1", "Autobomba 2"],
        )
        self.assertEqual(sorted(f.orden for f in filas), [1, 2, 3])

    def test_se_puede_volver_atras_y_cada_formulario_recupera_un_periodo(self):
        apps = self.migrar(ANTES)
        emergencia_pk = self.armar_estado_antiguo(apps)
        self.migrar(DESPUES)

        apps = self.migrar(ANTES)
        Formulario = apps.get_model("emergencias", "FormularioSCI")
        F211 = apps.get_model("emergencias", "FormularioSCI211")
        self.assertFalse(
            Formulario.objects.filter(emergencia_id=emergencia_pk, periodo__isnull=True).exists()
        )
        self.assertEqual(F211.objects.get(emergencia_id=emergencia_pk).periodo.numero, 2)
        # Nada desapareció por el camino.
        self.assertEqual(Formulario.objects.filter(emergencia_id=emergencia_pk).count(), 4)
