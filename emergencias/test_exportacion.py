"""Exportación del registro de incidentes a CSV.

El listado se pagina, de modo que el archivo no puede salir de la tabla del
navegador: debe traer todas las filas que corresponden a los filtros, y solo
las del ámbito autorizado.
"""

import csv
import io

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso

from .models import DespliegueUnidad, Emergencia, FormularioSCI211
from .services import desplegar_unidad

class BaseExportacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="LAT-EX")
        cls.cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Exportación", sigla="CBE-EX",
            ruc="0596000000501", direccion="Centro",
        )
        cls.cuerpo_ajeno = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Ajeno Ex", sigla="CBAE-EX",
            ruc="0596000000502", direccion="Sur",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo, nombre="Estación Central Exportación",
            codigo="ECE-EX", direccion="Centro",
            latitud="-0.930000", longitud="-78.610000",
        )
        cls.estacion_ajena = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo_ajeno, nombre="Central Ajena Exportación",
            codigo="CAE-EX", direccion="Sur",
            latitud="-1.010000", longitud="-78.660000",
        )
        categoria = CategoriaRecurso.objects.create(nombre="Vehículos", codigo="VEH-EX")
        cls.tipo_unidad = TipoRecurso.objects.create(
            categoria=categoria, nombre="Autobomba", codigo="AUT-EX",
            es_unidad_desplegable=True,
        )
        cls.usuario = get_user_model().objects.create_user(
            username="exporta-ex", cedula="0610000001", password="clave",
            first_name="Ana", last_name="Ruiz", estacion=cls.estacion,
        )
        cls.usuario.groups.add(Group.objects.get(name="Responsable institucional"))
        cls.consulta = get_user_model().objects.create_user(
            username="consulta-ex", cedula="0610000002", password="clave",
            estacion=cls.estacion,
        )
        cls.consulta.groups.add(Group.objects.get(name="Operador de consulta"))

    def crear(self, codigo, tipo="Incendio estructural",
              estado=Emergencia.Estado.REPORTADA, estacion=None):
        return Emergencia.objects.create(
            codigo=codigo, tipo_emergencia=tipo,
            prioridad=Emergencia.Prioridad.ALTA, estado=estado,
            direccion="Centro de Latacunga", latitud="-0.933333", longitud="-78.616667",
            estacion_responsable=estacion or self.estacion,
            registrado_por=self.usuario,
        )

    def exportar(self, usuario=None, **parametros):
        self.client.force_login(usuario or self.usuario)
        return self.client.get(reverse("emergencias:exportar"), parametros)

    def leer(self, respuesta):
        contenido = b"".join(respuesta.streaming_content).decode("utf-8")
        self.assertTrue(contenido.startswith("﻿"), "falta la marca de orden de bytes")
        return list(csv.reader(io.StringIO(contenido.lstrip("﻿")), delimiter=";"))

class ContenidoTests(BaseExportacionTests):
    def test_la_cabecera_describe_las_columnas(self):
        self.crear("EX-001")
        filas = self.leer(self.exportar())
        self.assertEqual(filas[0][0], "Código")
        self.assertIn("Estación responsable", filas[0])
        self.assertIn("Unidades activas", filas[0])
        self.assertIn("SCI-211", filas[0])

    def test_una_fila_por_incidente_con_sus_datos(self):
        emergencia = self.crear("EX-010", tipo="Incendio forestal")
        filas = self.leer(self.exportar())
        self.assertEqual(len(filas), 2)
        fila = dict(zip(filas[0], filas[1]))
        self.assertEqual(fila["Código"], "EX-010")
        self.assertEqual(fila["Tipo de emergencia"], "Incendio forestal")
        self.assertEqual(fila["Estado"], "Reportada")
        self.assertEqual(fila["Fase operativa"], "En curso")
        self.assertEqual(fila["Estación responsable"], self.estacion.nombre)
        self.assertEqual(fila["Institución"], self.cuerpo.nombre)
        self.assertEqual(fila["Registrado por"], "Ana Ruiz")
        self.assertEqual(fila["SCI-211"], "Pendiente")
        self.assertEqual(fila["Formularios SCI"], "0/12")
        self.assertEqual(emergencia.codigo, fila["Código"])

    def test_cuenta_los_despliegues_totales_y_los_activos(self):
        emergencia = self.crear("EX-020")
        for indice in range(2):
            unidad = Recurso.objects.create(
                estacion=self.estacion, tipo=self.tipo_unidad,
                codigo_interno=f"AB-EX-{indice}", nombre=f"Unidad {indice}",
            )
            despliegue = desplegar_unidad(emergencia, unidad, self.usuario)
            if indice == 0:
                DespliegueUnidad.objects.filter(pk=despliegue.pk).update(
                    estado=DespliegueUnidad.Estado.FINALIZADA
                )
        fila = dict(zip(*self.leer(self.exportar())))
        self.assertEqual(fila["Unidades desplegadas"], "2")
        self.assertEqual(fila["Unidades activas"], "1")

    def test_refleja_el_estado_del_sci211(self):
        emergencia = self.crear("EX-030")
        FormularioSCI211.objects.create(
            emergencia=emergencia, codigo="SCI211-EX-1",
            creado_por=self.usuario, modificado_por=self.usuario,
        )
        fila = dict(zip(*self.leer(self.exportar())))
        self.assertEqual(fila["SCI-211"], "Borrador")
        self.assertEqual(fila["Formularios SCI"], "1/12")

    def test_un_incidente_abierto_no_lleva_fecha_de_cierre(self):
        self.crear("EX-040")
        fila = dict(zip(*self.leer(self.exportar())))
        self.assertEqual(fila["Fecha de cierre"], "")

class FiltrosYAlcanceTests(BaseExportacionTests):
    def setUp(self):
        self.crear("EX-CURSO", tipo="Incendio forestal")
        self.crear("EX-FIN", estado=Emergencia.Estado.CERRADA)
        self.crear("EX-AJENO", estacion=self.estacion_ajena)

    def codigos(self, respuesta):
        filas = self.leer(respuesta)
        return [fila[0] for fila in filas[1:]]

    def test_exporta_todo_el_ambito_sin_filtros(self):
        self.assertCountEqual(self.codigos(self.exportar()), ["EX-CURSO", "EX-FIN"])

    def test_nunca_incluye_incidentes_de_otra_institucion(self):
        self.assertNotIn("EX-AJENO", self.codigos(self.exportar(q="EX-")))

    def test_respeta_el_filtro_de_fase(self):
        self.assertEqual(self.codigos(self.exportar(fase="terminada")), ["EX-FIN"])

    def test_respeta_la_busqueda(self):
        self.assertEqual(self.codigos(self.exportar(q="forestal")), ["EX-CURSO"])

    def test_respeta_la_etapa_documental(self):
        self.assertCountEqual(
            self.codigos(self.exportar(etapa="sin_iniciar")), ["EX-CURSO", "EX-FIN"]
        )
        self.assertEqual(self.codigos(self.exportar(etapa="completa")), [])

class PaginacionYAccesoTests(BaseExportacionTests):
    def test_el_archivo_ignora_la_paginacion_del_listado(self):
        """El listado muestra doce por página; el archivo debe traerlos todos."""
        for indice in range(15):
            self.crear(f"EX-PAG-{indice:03d}")
        filas = self.leer(self.exportar())
        self.assertEqual(len(filas) - 1, 15)

    def test_el_parametro_de_pagina_no_recorta_el_archivo(self):
        for indice in range(15):
            self.crear(f"EX-PG-{indice:03d}")
        filas = self.leer(self.exportar(pagina=2))
        self.assertEqual(len(filas) - 1, 15)

    def test_se_descarga_como_adjunto_con_nombre_propio(self):
        self.crear("EX-NOMBRE")
        respuesta = self.exportar()
        self.assertIn("text/csv", respuesta["Content-Type"])
        self.assertIn("attachment", respuesta["Content-Disposition"])
        self.assertIn("incidentes-", respuesta["Content-Disposition"])

    def test_un_perfil_de_consulta_tambien_puede_exportar_su_ambito(self):
        self.crear("EX-CONSULTA")
        self.assertEqual(
            self.leer(self.exportar(self.consulta))[1][0], "EX-CONSULTA"
        )

    def test_una_cuenta_sin_ambito_no_exporta(self):
        sin_ambito = get_user_model().objects.create_user(
            username="sin-ambito-ex", cedula="0610000009", password="clave"
        )
        self.assertEqual(self.exportar(sin_ambito).status_code, 403)

    def test_acceso_anonimo_va_al_inicio_de_sesion(self):
        respuesta = self.client.get(reverse("emergencias:exportar"))
        self.assertEqual(respuesta.status_code, 302)

    def test_la_exportacion_no_acepta_post(self):
        self.client.force_login(self.usuario)
        self.assertEqual(
            self.client.post(reverse("emergencias:exportar")).status_code, 405
        )

    def test_el_listado_ofrece_el_enlace_conservando_los_filtros(self):
        self.crear("EX-ENLACE")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:lista"), {"q": "EX", "fase": "curso"})
        self.assertContains(respuesta, "Exportar CSV")
        self.assertContains(
            respuesta, f"{reverse('emergencias:exportar')}?q=EX&amp;fase=curso"
        )
