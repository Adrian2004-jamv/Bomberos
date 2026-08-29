"""Filtros y paginación del registro de incidentes.

Los tres filtros existían en JavaScript sobre las filas ya dibujadas; aquí se
comprueba que ahora los resuelve la base y que conviven con la paginación.
"""

import json
from datetime import datetime

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion

from .esquemas_sci import ESQUEMAS_SCI
from .forms import TIPOS_EMERGENCIA
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
              estado=Emergencia.Estado.REPORTADA, estacion=None, direccion="Centro",
              fecha_reporte=None):
        campos = {}
        if fecha_reporte is not None:
            campos["fecha_reporte"] = fecha_reporte
        return Emergencia.objects.create(
            codigo=codigo, tipo_emergencia=tipo,
            prioridad=Emergencia.Prioridad.ALTA, estado=estado,
            direccion=direccion, latitud="-0.933333", longitud="-78.616667",
            estacion_responsable=estacion or self.estacion,
            registrado_por=self.usuario, **campos,
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


class FiltroPorTipoEmergenciaTests(BaseRegistroTests):
    def setUp(self):
        self.crear("RG-TIPO-FORESTAL", tipo="Incendio forestal")
        self.crear("RG-TIPO-RESCATE", tipo="Rescate en altura")
        self.crear(
            "RG-TIPO-INUNDACION", tipo="Inundación",
            estado=Emergencia.Estado.CERRADA,
        )

    def test_filtra_por_tipo_exacto(self):
        self.assertEqual(
            self.codigos(self.listar(tipo="Incendio forestal")),
            ["RG-TIPO-FORESTAL"],
        )

    def test_incluye_descripciones_especificas_del_tipo(self):
        self.assertEqual(
            self.codigos(self.listar(tipo="Rescate")), ["RG-TIPO-RESCATE"]
        )

    def test_se_combina_con_la_fase(self):
        self.assertEqual(
            self.codigos(self.listar(tipo="Inundación", fase="terminada")),
            ["RG-TIPO-INUNDACION"],
        )

    def test_el_selector_conserva_el_tipo_elegido(self):
        respuesta = self.listar(tipo="Rescate")
        self.assertContains(respuesta, '<option value="Rescate" selected>')


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
        respuesta = self.listar(
            q="RG-", tipo="Incendio estructural", fase="curso"
        )
        self.assertContains(respuesta, 'value="RG-"')
        self.assertContains(
            respuesta, '<option value="Incendio estructural" selected>'
        )
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


class FiltroPorFechaTests(BaseRegistroTests):
    """Rango de fechas sobre la fecha de reporte, en hora local."""

    def setUp(self):
        def local(anio, mes, dia, hora=12):
            ingenuo = datetime(anio, mes, dia, hora)
            return timezone.make_aware(ingenuo, timezone.get_current_timezone())

        self.crear("RG-FEC-1", fecha_reporte=local(2026, 3, 1))
        self.crear("RG-FEC-2", fecha_reporte=local(2026, 3, 10))
        self.crear("RG-FEC-3", fecha_reporte=local(2026, 3, 20))

    def test_sin_fechas_muestra_todos(self):
        self.assertEqual(len(self.codigos(self.listar())), 3)

    def test_desde_incluye_su_propio_dia(self):
        codigos = self.codigos(self.listar(desde="2026-03-10"))
        self.assertEqual(sorted(codigos), ["RG-FEC-2", "RG-FEC-3"])

    def test_hasta_incluye_su_propio_dia(self):
        codigos = self.codigos(self.listar(hasta="2026-03-10"))
        self.assertEqual(sorted(codigos), ["RG-FEC-1", "RG-FEC-2"])

    def test_rango_cerrado_acota_por_ambos_extremos(self):
        codigos = self.codigos(self.listar(desde="2026-03-05", hasta="2026-03-15"))
        self.assertEqual(codigos, ["RG-FEC-2"])

    def test_un_solo_dia_se_expresa_con_el_mismo_valor(self):
        codigos = self.codigos(self.listar(desde="2026-03-10", hasta="2026-03-10"))
        self.assertEqual(codigos, ["RG-FEC-2"])

    def test_un_rango_sin_incidentes_no_devuelve_nada(self):
        self.assertEqual(self.codigos(self.listar(desde="2026-04-01")), [])

    def test_el_rango_invertido_avisa_y_no_filtra(self):
        respuesta = self.listar(desde="2026-03-20", hasta="2026-03-01")
        self.assertContains(respuesta, "La fecha final no puede ser anterior a la inicial.")
        self.assertEqual(len(self.codigos(respuesta)), 3)

    def test_una_fecha_ilegible_avisa_y_no_rompe(self):
        respuesta = self.listar(desde="no-es-fecha")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "formato AAAA-MM-DD")

    def test_se_combina_con_los_demas_filtros(self):
        self.crear("RG-FEC-4", tipo="Incendio forestal",
                   fecha_reporte=timezone.make_aware(
                       datetime(2026, 3, 12, 12), timezone.get_current_timezone()))
        codigos = self.codigos(self.listar(
            desde="2026-03-05", hasta="2026-03-15", tipo="Incendio forestal"))
        self.assertEqual(codigos, ["RG-FEC-4"])

    def test_la_barra_conserva_las_fechas_elegidas(self):
        respuesta = self.listar(desde="2026-03-05", hasta="2026-03-15")
        self.assertContains(respuesta, 'value="2026-03-05"')
        self.assertContains(respuesta, 'value="2026-03-15"')
        self.assertContains(respuesta, "Limpiar")

    def test_la_hora_local_decide_el_dia_y_no_la_marca_utc(self):
        """A las 22:00 de Ecuador ya es el día siguiente en UTC.

        Si el filtro comparara la marca almacenada sin convertirla, este
        incidente caería fuera del rango que el usuario ve en pantalla.
        """
        self.crear("RG-FEC-NOCHE", fecha_reporte=timezone.make_aware(
            datetime(2026, 3, 25, 22), timezone.get_current_timezone()))
        codigos = self.codigos(self.listar(desde="2026-03-25", hasta="2026-03-25"))
        self.assertEqual(codigos, ["RG-FEC-NOCHE"])

    def test_la_exportacion_respeta_el_rango(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:exportar"), {"desde": "2026-03-05", "hasta": "2026-03-15"}
        )
        contenido = b"".join(respuesta.streaming_content).decode("utf-8-sig")
        self.assertIn("RG-FEC-2", contenido)
        self.assertNotIn("RG-FEC-1", contenido)
        self.assertNotIn("RG-FEC-3", contenido)


class MapaRespetaElFiltroTests(BaseRegistroTests):
    """El mapa recibe qué incidentes pasan el filtro para atenuar el resto."""

    def setUp(self):
        def local(dia):
            return timezone.make_aware(
                datetime(2026, 3, dia, 12), timezone.get_current_timezone()
            )

        self.dentro = self.crear("RG-MAP-1", fecha_reporte=local(10))
        self.fuera = self.crear("RG-MAP-2", fecha_reporte=local(25))

    def ids(self, respuesta):
        return json.loads(respuesta.context["ids_en_filtro_json"])

    def test_sin_filtros_el_mapa_no_atenua_nada(self):
        respuesta = self.listar()
        self.assertFalse(respuesta.context["hay_filtros"])
        self.assertContains(respuesta, 'data-incident-map-filtered="0"')

    def test_con_rango_solo_viaja_lo_que_pasa_el_filtro(self):
        respuesta = self.listar(desde="2026-03-01", hasta="2026-03-15")
        self.assertTrue(respuesta.context["hay_filtros"])
        self.assertContains(respuesta, 'data-incident-map-filtered="1"')
        self.assertEqual(self.ids(respuesta), [self.dentro.pk])

    def test_incluye_los_que_no_caben_en_la_pagina(self):
        """El mapa dibuja todo el ámbito, no solo la página que se ve."""
        for numero in range(20):
            self.crear(f"RG-MAP-EXTRA-{numero}",
                       fecha_reporte=timezone.make_aware(
                           datetime(2026, 3, 10, 12), timezone.get_current_timezone()))
        respuesta = self.listar(desde="2026-03-10", hasta="2026-03-10")
        self.assertEqual(len(respuesta.context["emergencias"]), 12)
        self.assertEqual(len(self.ids(respuesta)), 21)

    def test_un_filtro_sin_coincidencias_deja_la_lista_vacia(self):
        respuesta = self.listar(desde="2026-05-01")
        self.assertEqual(self.ids(respuesta), [])
        self.assertContains(respuesta, 'data-incident-map-filtered="1"')

    def test_el_conjunto_no_alcanza_a_otra_institucion(self):
        ajena = self.crear("RG-MAP-AJENA", estacion=self.estacion_ajena,
                           fecha_reporte=timezone.make_aware(
                               datetime(2026, 3, 10, 12), timezone.get_current_timezone()))
        respuesta = self.listar(desde="2026-03-10", hasta="2026-03-10")
        self.assertNotIn(ajena.pk, self.ids(respuesta))


class FormularioDeRegistroTests(BaseRegistroTests):
    """Tipo como lista cerrada y selector de ubicación en el mapa."""

    def abrir_creacion(self):
        self.client.force_login(self.usuario)
        return self.client.get(reverse("emergencias:crear"))

    def test_el_tipo_es_una_lista_y_no_texto_libre(self):
        respuesta = self.abrir_creacion()
        campo = respuesta.context["form"].fields["tipo_emergencia"]
        self.assertIsInstance(campo.widget, forms.Select)
        valores = [valor for valor, _etiqueta in campo.choices if valor]
        self.assertEqual(valores, list(TIPOS_EMERGENCIA))

    def test_la_lista_ofrece_los_tipos_de_la_simbologia_del_mapa(self):
        respuesta = self.abrir_creacion()
        for tipo in TIPOS_EMERGENCIA:
            self.assertContains(respuesta, f'<option value="{tipo}">')

    def test_un_tipo_fuera_del_catalogo_se_rechaza(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.post(reverse("emergencias:crear"), {
            "tipo_emergencia": "Erupción volcánica",
            "prioridad": Emergencia.Prioridad.ALTA,
            "fecha_reporte": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
            "direccion": "Centro",
            "estacion_responsable": self.estacion.pk,
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertFormError(
            respuesta.context["form"], "tipo_emergencia",
            "Escoja una opción válida. Erupción volcánica no es una de las opciones disponibles.",
        )

    def test_editar_conserva_un_tipo_anterior_al_catalogo(self):
        """El catálogo se fijó con el sistema en uso; no debe borrar lo antiguo."""
        antigua = self.crear("RG-ANTIGUA", tipo="Rescate en altura")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:editar", args=[antigua.pk]))
        campo = respuesta.context["form"].fields["tipo_emergencia"]
        valores = [valor for valor, _etiqueta in campo.choices]
        self.assertIn("Rescate en altura", valores)
        self.assertContains(respuesta, "(registro anterior)")

    def test_el_formulario_trae_el_selector_de_ubicacion(self):
        respuesta = self.abrir_creacion()
        self.assertContains(respuesta, "data-location-map")
        self.assertContains(respuesta, "data-ubicacion-latitud")
        self.assertContains(respuesta, "data-ubicacion-longitud")
        self.assertContains(respuesta, "emergencias/js/mapa_ubicacion.js")
        self.assertContains(respuesta, "vendor/leaflet/leaflet.js")

    def test_la_ubicacion_sigue_siendo_opcional(self):
        """Se registra por radio antes de conocer la coordenada exacta."""
        self.client.force_login(self.usuario)
        respuesta = self.client.post(reverse("emergencias:crear"), {
            "tipo_emergencia": "Incendio forestal",
            "prioridad": Emergencia.Prioridad.ALTA,
            "fecha_reporte": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
            "direccion": "Vía a Pujilí",
            "estacion_responsable": self.estacion.pk,
        })
        self.assertEqual(respuesta.status_code, 302)
        creada = Emergencia.objects.get(direccion="Vía a Pujilí")
        self.assertIsNone(creada.latitud)


class TerminologiaTests(BaseRegistroTests):
    """La interfaz dice «emergencia»; los formularios SCI conservan «incidente»."""

    def test_el_registro_habla_de_emergencias(self):
        respuesta = self.listar()
        self.assertContains(respuesta, "Registro dinámico de emergencias")
        self.assertNotContains(respuesta, "Registro dinámico de incidentes")

    def test_los_formularios_sci_conservan_el_termino_oficial(self):
        emergencia = self.crear("RG-TERM-1")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse(
            "emergencias:sci_visualizar", args=["201", emergencia.pk]
        ))
        self.assertContains(respuesta, "Resumen del Incidente".upper())
        self.assertContains(respuesta, "Nombre del incidente")
