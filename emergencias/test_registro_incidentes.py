"""Filtros y paginación del registro de incidentes.

Los tres filtros existían en JavaScript sobre las filas ya dibujadas; aquí se
comprueba que ahora los resuelve la base y que conviven con la paginación.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from instituciones.models import Canton, CuerpoBomberos, Estacion

from .esquemas_sci import ESQUEMAS_SCI
from .models import Emergencia, FormularioSCI, FormularioSCI211


class BaseRegistroTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="LAT-RG")
        cls.cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Registro", sigla="CBR-RG",
            ruc="0596000000401", direccion="Centro",
        )
        cls.cuerpo_ajeno = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Ajeno Rg", sigla="CBAR-RG",
            ruc="0596000000402", direccion="Sur",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo, nombre="Estación Central Registro",
            codigo="ECR-RG", direccion="Centro",
            latitud="-0.930000", longitud="-78.610000",
        )
        cls.estacion_ajena = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo_ajeno, nombre="Central Ajena Registro",
            codigo="CAR-RG", direccion="Sur",
            latitud="-1.010000", longitud="-78.660000",
        )
        cls.usuario = get_user_model().objects.create_user(
            username="registro-rg", cedula="0600000001", password="clave",
            estacion=cls.estacion,
        )
        cls.usuario.groups.add(Group.objects.get(name="Responsable institucional"))

    def crear(self, codigo, tipo="Incendio estructural",
              estado=Emergencia.Estado.REPORTADA, estacion=None, direccion="Centro"):
        return Emergencia.objects.create(
            codigo=codigo, tipo_emergencia=tipo,
            prioridad=Emergencia.Prioridad.ALTA, estado=estado,
            direccion=direccion, latitud="-0.933333", longitud="-78.616667",
            estacion_responsable=estacion or self.estacion,
            registrado_por=self.usuario,
        )

    def listar(self, **parametros):
        self.client.force_login(self.usuario)
        return self.client.get(reverse("emergencias:lista"), parametros)

    def codigos(self, respuesta):
        return [emergencia.codigo for emergencia in respuesta.context["emergencias"]]


class FiltroPorFaseTests(BaseRegistroTests):
    def setUp(self):
        self.crear("RG-CURSO-1")
        self.crear("RG-CURSO-2", estado=Emergencia.Estado.EN_ATENCION)
        self.crear("RG-FIN-1", estado=Emergencia.Estado.CERRADA)
        self.crear("RG-FIN-2", estado=Emergencia.Estado.CANCELADA)

    def test_sin_fase_muestra_todos(self):
        respuesta = self.listar()
        self.assertEqual(len(self.codigos(respuesta)), 4)
        self.assertEqual(respuesta.context["fase_activa"], "all")

    def test_solo_los_incidentes_en_curso(self):
        respuesta = self.listar(fase="curso")
        self.assertCountEqual(self.codigos(respuesta), ["RG-CURSO-1", "RG-CURSO-2"])

    def test_solo_los_terminados(self):
        respuesta = self.listar(fase="terminada")
        self.assertCountEqual(self.codigos(respuesta), ["RG-FIN-1", "RG-FIN-2"])

    def test_los_conteos_acompanan_a_los_botones(self):
        respuesta = self.listar(fase="curso")
        self.assertEqual(respuesta.context["total_en_curso"], 2)
        self.assertEqual(respuesta.context["total_terminadas"], 2)

    def test_una_fase_invalida_no_filtra_ni_rompe(self):
        respuesta = self.listar(fase="inventada")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(self.codigos(respuesta)), 4)


class BusquedaTests(BaseRegistroTests):
    def setUp(self):
        self.crear("RG-BUS-001", tipo="Incendio forestal", direccion="Vía a Pujilí")
        self.crear("RG-BUS-002", tipo="Rescate en altura", direccion="Centro")
        self.crear("RG-OTRO-003", tipo="Inundación", direccion="Barrio El Salto",
                   estado=Emergencia.Estado.CERRADA)

    def test_busca_por_codigo(self):
        self.assertCountEqual(
            self.codigos(self.listar(q="RG-BUS")), ["RG-BUS-001", "RG-BUS-002"]
        )

    def test_busca_por_tipo_de_emergencia(self):
        self.assertEqual(self.codigos(self.listar(q="forestal")), ["RG-BUS-001"])

    def test_busca_por_direccion(self):
        self.assertEqual(self.codigos(self.listar(q="El Salto")), ["RG-OTRO-003"])

    def test_busca_por_estacion(self):
        self.assertEqual(len(self.codigos(self.listar(q="Central Registro"))), 3)

    def test_busca_por_la_etiqueta_del_estado(self):
        """El estado se guarda como clave, no como la etiqueta que se ve."""
        self.assertEqual(self.codigos(self.listar(q="Cerrada")), ["RG-OTRO-003"])

    def test_la_busqueda_no_distingue_mayusculas(self):
        self.assertEqual(self.codigos(self.listar(q="FORESTAL")), ["RG-BUS-001"])

    def test_sin_coincidencias_lo_explica(self):
        respuesta = self.listar(q="terremoto")
        self.assertEqual(self.codigos(respuesta), [])
        self.assertContains(respuesta, "Sin coincidencias")
        self.assertNotContains(respuesta, "No existen emergencias registradas")

    def test_la_busqueda_se_combina_con_la_fase(self):
        self.assertEqual(self.codigos(self.listar(q="RG", fase="terminada")),
                         ["RG-OTRO-003"])

    def test_los_espacios_sobrantes_no_afectan(self):
        self.assertEqual(self.codigos(self.listar(q="  forestal  ")), ["RG-BUS-001"])


class FiltroPorEtapaSciTests(BaseRegistroTests):
    def setUp(self):
        self.sin_iniciar = self.crear("RG-SCI-VACIO")
        self.en_curso = self.crear("RG-SCI-PARCIAL")
        self.completa = self.crear("RG-SCI-COMPLETA")
        FormularioSCI211.objects.create(
            emergencia=self.en_curso, codigo="SCI211-RG-1",
            creado_por=self.usuario, modificado_por=self.usuario
        )
        FormularioSCI211.objects.create(
            emergencia=self.completa, codigo="SCI211-RG-2",
            creado_por=self.usuario, modificado_por=self.usuario
        )
        for codigo in ESQUEMAS_SCI:
            FormularioSCI.objects.create(
                emergencia=self.completa, codigo_sci=codigo,
                creado_por=self.usuario, modificado_por=self.usuario
            )

    def test_sin_iniciar(self):
        self.assertEqual(self.codigos(self.listar(etapa="sin_iniciar")), ["RG-SCI-VACIO"])

    def test_en_elaboracion(self):
        self.assertEqual(
            self.codigos(self.listar(etapa="en_elaboracion")), ["RG-SCI-PARCIAL"]
        )

    def test_completa(self):
        self.assertEqual(self.codigos(self.listar(etapa="completa")), ["RG-SCI-COMPLETA"])

    def test_el_avance_documental_se_calcula_desde_la_anotacion(self):
        respuesta = self.listar(etapa="completa")
        emergencia = respuesta.context["emergencias"][0]
        self.assertEqual(emergencia.formularios_completados, 12)
        self.assertEqual(emergencia.porcentaje_formularios, 100)
        self.assertContains(respuesta, "12/12 formularios")


class PaginacionTests(BaseRegistroTests):
    def setUp(self):
        for indice in range(15):
            self.crear(f"RG-PAG-{indice:03d}")

    def test_la_primera_pagina_esta_acotada(self):
        respuesta = self.listar()
        self.assertEqual(len(self.codigos(respuesta)), 12)
        self.assertEqual(respuesta.context["pagina"].paginator.count, 15)
        self.assertEqual(respuesta.context["pagina"].paginator.num_pages, 2)

    def test_la_segunda_pagina_trae_el_resto(self):
        respuesta = self.listar(pagina=2)
        self.assertEqual(len(self.codigos(respuesta)), 3)

    def test_ninguna_fila_se_repite_entre_paginas(self):
        primera = set(self.codigos(self.listar()))
        segunda = set(self.codigos(self.listar(pagina=2)))
        self.assertEqual(len(primera | segunda), 15)
        self.assertEqual(primera & segunda, set())

    def test_una_pagina_inexistente_devuelve_la_ultima(self):
        respuesta = self.listar(pagina=99)
        self.assertEqual(respuesta.context["pagina"].number, 2)

    def test_el_enlace_de_pagina_conserva_los_filtros(self):
        respuesta = self.listar(q="RG-PAG", fase="curso")
        self.assertEqual(respuesta.context["querystring"], "q=RG-PAG&fase=curso")
        self.assertContains(respuesta, "q=RG-PAG&amp;fase=curso&amp;pagina=2")

    def test_el_boton_de_fase_no_arrastra_la_fase_anterior(self):
        respuesta = self.listar(q="RG-PAG", fase="terminada")
        self.assertEqual(respuesta.context["querystring_sin_fase"], "q=RG-PAG")


class AlcanceYFormularioTests(BaseRegistroTests):
    def test_los_filtros_no_alcanzan_a_otra_institucion(self):
        self.crear("RG-AJENO", estacion=self.estacion_ajena)
        self.crear("RG-PROPIO")
        self.assertEqual(self.codigos(self.listar(q="RG-")), ["RG-PROPIO"])

    def test_la_barra_de_filtros_conserva_lo_elegido(self):
        self.crear("RG-ESTADO")
        respuesta = self.listar(q="RG-", etapa="sin_iniciar", fase="curso")
        self.assertContains(respuesta, 'value="RG-"')
        self.assertContains(respuesta, '<option value="sin_iniciar" selected>')
        self.assertContains(respuesta, 'value="curso"')
        self.assertContains(respuesta, "Limpiar")

    def test_sin_filtros_no_ofrece_limpiar(self):
        self.crear("RG-LIMPIO")
        self.assertNotContains(self.listar(), "Limpiar")

    def test_el_listado_vacio_conserva_su_mensaje_original(self):
        respuesta = self.listar()
        self.assertContains(respuesta, "No existen emergencias registradas")

    def test_el_registro_no_acepta_post(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.post(reverse("emergencias:lista")).status_code, 405)
