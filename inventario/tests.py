from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse

from instituciones.models import Canton, CuerpoBomberos, Estacion

from .models import CategoriaRecurso, HistorialEstadoRecurso, Recurso, TipoRecurso
from .services import actualizar_estado_recurso


class ActualizarEstadoRecursoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="LAT")
        cuerpo = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Cuerpo de Bomberos de Latacunga",
            sigla="CBL",
            ruc="0590000000001",
            direccion="Latacunga",
        )
        estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo,
            nombre="Estación Central",
            codigo="EC-01",
            direccion="Latacunga",
            latitud="-0.933333",
            longitud="-78.616667",
        )
        categoria = CategoriaRecurso.objects.create(nombre="Vehículo", codigo="VEH")
        tipo = TipoRecurso.objects.create(
            categoria=categoria,
            nombre="Autobomba",
            codigo="AUT",
        )
        cls.recurso = Recurso.objects.create(
            estacion=estacion,
            tipo=tipo,
            codigo_interno="R-001",
            nombre="Autobomba de prueba",
        )
        cls.usuario = get_user_model().objects.create_user(
            username="responsable",
            cedula="0500000001",
            password="clave-segura-prueba",
            estacion=estacion,
        )
        cls.usuario.groups.add(Group.objects.get(name="Encargado de inventario"))

    def test_cambio_valido_actualiza_recurso_y_crea_historial(self):
        recurso, historial = actualizar_estado_recurso(
            recurso=self.recurso,
            nuevo_estado_operativo=Recurso.EstadoOperativo.MANTENIMIENTO,
            nueva_disponibilidad=Recurso.Disponibilidad.NO_DISPONIBLE,
            usuario_responsable=self.usuario,
            motivo="Revisión preventiva",
            observaciones="Ingreso al taller",
        )

        recurso.refresh_from_db()
        self.assertEqual(recurso.estado_operativo, Recurso.EstadoOperativo.MANTENIMIENTO)
        self.assertEqual(recurso.disponibilidad, Recurso.Disponibilidad.NO_DISPONIBLE)
        self.assertEqual(HistorialEstadoRecurso.objects.count(), 1)
        self.assertEqual(historial.estado_anterior, Recurso.EstadoOperativo.OPERATIVO)
        self.assertEqual(historial.disponibilidad_anterior, Recurso.Disponibilidad.DISPONIBLE)
        self.assertEqual(historial.registrado_por, self.usuario)

    def test_sin_cambios_no_crea_historial(self):
        recurso, historial = actualizar_estado_recurso(
            recurso=self.recurso,
            nuevo_estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
            nueva_disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
            usuario_responsable=self.usuario,
            motivo="Verificación sin novedades",
        )

        self.assertEqual(recurso.pk, self.recurso.pk)
        self.assertIsNone(historial)
        self.assertFalse(HistorialEstadoRecurso.objects.exists())


class InterfazInventarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="LAT-I")
        cls.cuerpo_uno = CuerpoBomberos.objects.create(canton=canton, nombre="Bomberos Uno", sigla="CBU", ruc="0591000000001", direccion="Centro")
        cls.cuerpo_dos = CuerpoBomberos.objects.create(canton=canton, nombre="Bomberos Dos", sigla="CBD", ruc="0591000000002", direccion="Sur")
        cls.estacion_uno = Estacion.objects.create(cuerpo_bomberos=cls.cuerpo_uno, nombre="Central", codigo="C1", direccion="Centro", latitud="-0.900000", longitud="-78.600000")
        cls.estacion_uno_b = Estacion.objects.create(cuerpo_bomberos=cls.cuerpo_uno, nombre="Norte", codigo="N1", direccion="Norte", latitud="-0.910000", longitud="-78.610000")
        cls.estacion_dos = Estacion.objects.create(cuerpo_bomberos=cls.cuerpo_dos, nombre="Sur", codigo="S1", direccion="Sur", latitud="-1.000000", longitud="-78.650000")
        cls.categoria = CategoriaRecurso.objects.create(nombre="Vehículos", codigo="VEH-I")
        cls.tipo = TipoRecurso.objects.create(categoria=cls.categoria, nombre="Autobomba", codigo="AUT-I")
        cls.recurso_uno = Recurso.objects.create(estacion=cls.estacion_uno, tipo=cls.tipo, codigo_interno="R-I-001", nombre="Autobomba central", marca="Marca Alfa")
        cls.recurso_uno_b = Recurso.objects.create(estacion=cls.estacion_uno_b, tipo=cls.tipo, codigo_interno="R-I-002", nombre="Autobomba norte", marca="Marca Beta")
        cls.recurso_dos = Recurso.objects.create(estacion=cls.estacion_dos, tipo=cls.tipo, codigo_interno="R-I-003", nombre="Autobomba sur", marca="Marca Gamma")
        cls.usuarios = {}
        cls.usuarios["super"] = get_user_model().objects.create_superuser(username="super-inv", cedula="0510000001", password="clave")
        configuraciones = (
            ("provincial", "Responsable provincial", None, "0510000002"),
            ("institucional", "Responsable institucional", cls.estacion_uno, "0510000003"),
            ("estacion", "Responsable de estación", cls.estacion_uno, "0510000004"),
            ("encargado", "Encargado de inventario", cls.estacion_uno, "0510000005"),
            ("consulta", "Operador de consulta", cls.estacion_uno, "0510000006"),
        )
        for clave, grupo, estacion, cedula in configuraciones:
            usuario = get_user_model().objects.create_user(username=clave, cedula=cedula, password="clave", estacion=estacion)
            usuario.groups.add(Group.objects.get(name=grupo))
            cls.usuarios[clave] = usuario

    def datos_recurso(self, **cambios):
        datos = {"estacion": self.estacion_uno.pk, "tipo": self.tipo.pk, "codigo_interno": "NUEVO-1", "nombre": "Recurso nuevo", "descripcion": "Prueba", "marca": "Marca", "modelo": "Modelo", "numero_serie": "SERIE-1", "anio_fabricacion": "2024", "observaciones": "", "activo": "on"}
        datos.update(cambios)
        return datos

    def test_no_autenticado_es_redirigido(self):
        respuesta = self.client.get(reverse("inventario:lista"))
        self.assertEqual(respuesta.status_code, 302)

    def test_superusuario_y_provincial_ven_todos(self):
        for usuario in (self.usuarios["super"], self.usuarios["provincial"]):
            self.client.force_login(usuario)
            respuesta = self.client.get(reverse("inventario:lista"))
            self.assertContains(respuesta, "R-I-001")
            self.assertContains(respuesta, "R-I-002")
            self.assertContains(respuesta, "R-I-003")

    def test_responsable_institucional_solo_ve_su_cuerpo(self):
        self.client.force_login(self.usuarios["institucional"])
        respuesta = self.client.get(reverse("inventario:lista"))
        self.assertContains(respuesta, "R-I-001")
        self.assertContains(respuesta, "R-I-002")
        self.assertNotContains(respuesta, "R-I-003")

    def test_responsable_estacion_solo_ve_su_estacion(self):
        self.client.force_login(self.usuarios["estacion"])
        respuesta = self.client.get(reverse("inventario:lista"))
        self.assertContains(respuesta, "R-I-001")
        self.assertNotContains(respuesta, "R-I-002")

    def test_encargado_crea_y_edita_en_su_estacion(self):
        self.client.force_login(self.usuarios["encargado"])
        respuesta = self.client.post(reverse("inventario:crear"), self.datos_recurso())
        recurso = Recurso.objects.get(codigo_interno="NUEVO-1")
        self.assertRedirects(respuesta, reverse("inventario:detalle", args=[recurso.pk]))
        datos = self.datos_recurso(nombre="Nombre actualizado", codigo_interno="NUEVO-1")
        self.client.post(reverse("inventario:editar", args=[recurso.pk]), datos)
        recurso.refresh_from_db()
        self.assertEqual(recurso.nombre, "Nombre actualizado")

    def test_operador_consulta_no_modifica(self):
        self.client.force_login(self.usuarios["consulta"])
        for ruta in (reverse("inventario:crear"), reverse("inventario:editar", args=[self.recurso_uno.pk]), reverse("inventario:cambiar_estado", args=[self.recurso_uno.pk])):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 403)

    def test_recurso_ajeno_no_es_accesible_por_url(self):
        self.client.force_login(self.usuarios["encargado"])
        self.assertEqual(self.client.get(reverse("inventario:detalle", args=[self.recurso_dos.pk])).status_code, 404)

    def test_estacion_no_autorizada_en_post_es_rechazada(self):
        self.client.force_login(self.usuarios["encargado"])
        respuesta = self.client.post(reverse("inventario:crear"), self.datos_recurso(estacion=self.estacion_dos.pk))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Escoja una opción válida")
        self.assertFalse(Recurso.objects.filter(codigo_interno="NUEVO-1").exists())

    def test_busqueda_y_filtros_respetan_alcance(self):
        self.client.force_login(self.usuarios["institucional"])
        respuesta = self.client.get(reverse("inventario:lista"), {"q": "Autobomba", "estacion_id": self.estacion_uno_b.pk, "categoria_id": self.categoria.pk})
        self.assertContains(respuesta, "R-I-002")
        self.assertNotContains(respuesta, "R-I-001")
        self.assertNotContains(respuesta, "R-I-003")

    def test_formulario_invalido_muestra_errores(self):
        self.client.force_login(self.usuarios["encargado"])
        respuesta = self.client.post(reverse("inventario:crear"), self.datos_recurso(nombre="", anio_fabricacion="-1"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Este campo es obligatorio")

    def test_edicion_descriptiva_no_cambia_estado_ni_disponibilidad(self):
        self.client.force_login(self.usuarios["encargado"])
        datos = self.datos_recurso(codigo_interno=self.recurso_uno.codigo_interno, nombre="Editado", estado_operativo="dado_baja", disponibilidad="no_disponible")
        self.client.post(reverse("inventario:editar", args=[self.recurso_uno.pk]), datos)
        self.recurso_uno.refresh_from_db()
        self.assertEqual(self.recurso_uno.estado_operativo, Recurso.EstadoOperativo.OPERATIVO)
        self.assertEqual(self.recurso_uno.disponibilidad, Recurso.Disponibilidad.DISPONIBLE)

    def test_cambio_estado_crea_historial_y_sin_diferencias_no_crea_otro(self):
        self.client.force_login(self.usuarios["encargado"])
        ruta = reverse("inventario:cambiar_estado", args=[self.recurso_uno.pk])
        self.client.post(ruta, {"nuevo_estado_operativo": "mantenimiento", "nueva_disponibilidad": "no_disponible", "motivo": "Revisión", "observaciones": "Taller"})
        self.assertEqual(self.recurso_uno.historial_estados.count(), 1)
        self.client.post(ruta, {"nuevo_estado_operativo": "mantenimiento", "nueva_disponibilidad": "no_disponible", "motivo": "Sin novedades", "observaciones": ""})
        self.assertEqual(self.recurso_uno.historial_estados.count(), 1)

    def test_motivo_es_obligatorio(self):
        self.client.force_login(self.usuarios["encargado"])
        respuesta = self.client.post(reverse("inventario:cambiar_estado", args=[self.recurso_uno.pk]), {"nuevo_estado_operativo": "mantenimiento", "nueva_disponibilidad": "no_disponible", "motivo": ""})
        self.assertContains(respuesta, "Este campo es obligatorio")
        self.assertFalse(self.recurso_uno.historial_estados.exists())

    def test_historial_es_solo_lectura(self):
        self.client.force_login(self.usuarios["consulta"])
        ruta = reverse("inventario:historial", args=[self.recurso_uno.pk])
        self.assertEqual(self.client.get(ruta).status_code, 200)
        self.assertEqual(self.client.post(ruta, {}).status_code, 405)

    def test_datatable_recibe_todos_los_resultados_filtrados(self):
        for indice in range(25):
            Recurso.objects.create(estacion=self.estacion_uno, tipo=self.tipo, codigo_interno=f"PAG-{indice:02}", nombre=f"Equipo paginado {indice}")
        self.client.force_login(self.usuarios["encargado"])
        respuesta = self.client.get(reverse("inventario:lista"), {"q": "paginado"})
        self.assertContains(respuesta, "PAG-00")
        self.assertContains(respuesta, "PAG-24")
        self.assertContains(respuesta, "data-inventory-table")
        self.assertContains(respuesta, "datatables-2.3.8.min.js")
        self.assertContains(respuesta, 'data-inventory-column-filter="2"', html=False)
        self.assertContains(respuesta, "Buscar recurso…")
        self.assertContains(respuesta, 'data-inventory-column-filter="8"', html=False)
        self.assertContains(respuesta, 'aria-label="Filtrar por registro"', html=False)
        self.assertContains(respuesta, "inventario_datatable.js?v=3")

    def test_listado_agrupa_por_institucion_categoria_y_tipo(self):
        self.client.force_login(self.usuarios["provincial"])
        respuesta = self.client.get(reverse("inventario:lista"))
        self.assertContains(respuesta, self.cuerpo_uno.nombre)
        self.assertContains(respuesta, self.cuerpo_dos.nombre)
        self.assertContains(respuesta, self.categoria.nombre)
        self.assertContains(respuesta, self.tipo.nombre)
        recursos = list(respuesta.context["recursos"])
        claves = [
            (r.estacion.cuerpo_bomberos.nombre, r.tipo.categoria.nombre, r.tipo.nombre, r.codigo_interno)
            for r in recursos
        ]
        self.assertEqual(claves, sorted(claves))

    def test_consulta_principal_no_duplica_recursos(self):
        self.client.force_login(self.usuarios["provincial"])
        respuesta = self.client.get(reverse("inventario:lista"))
        ids = [recurso.pk for recurso in respuesta.context["recursos"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_peticion_htmx_devuelve_solo_resultados(self):
        self.client.force_login(self.usuarios["encargado"])
        respuesta = self.client.get(reverse("inventario:lista"), HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(respuesta, "inventario/_resultados.html")
        self.assertContains(respuesta, "R-I-001")
        self.assertNotContains(respuesta, "Buscar y filtrar inventario")

    def test_listado_no_muestra_bloque_de_filtros_duplicado(self):
        self.client.force_login(self.usuarios["encargado"])
        respuesta = self.client.get(reverse("inventario:lista"))
        self.assertNotContains(respuesta, "Buscar y filtrar inventario")
        self.assertNotContains(respuesta, "Aplicar filtros")
        self.assertNotContains(respuesta, "htmx-2.0.10.min.js")

    def test_opcion_invalida_produce_error(self):
        with self.assertRaises(ValidationError):
            actualizar_estado_recurso(
                recurso=self.recurso_uno,
                nuevo_estado_operativo="estado_inexistente",
                nueva_disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
                usuario_responsable=self.usuarios["encargado"],
                motivo="Prueba de validación",
            )

        self.recurso_uno.refresh_from_db()
        self.assertEqual(self.recurso_uno.estado_operativo, Recurso.EstadoOperativo.OPERATIVO)
        self.assertFalse(HistorialEstadoRecurso.objects.exists())

    def test_fallo_del_historial_revierte_actualizacion(self):
        with patch(
            "inventario.services.HistorialEstadoRecurso.objects.create",
            side_effect=DatabaseError("Fallo simulado al crear el historial"),
        ):
            with self.assertRaises(DatabaseError):
                actualizar_estado_recurso(
                    recurso=self.recurso_uno,
                    nuevo_estado_operativo=Recurso.EstadoOperativo.FUERA_SERVICIO,
                    nueva_disponibilidad=Recurso.Disponibilidad.NO_DISPONIBLE,
                    usuario_responsable=self.usuarios["encargado"],
                    motivo="Fallo de auditoría simulado",
                )

        self.recurso_uno.refresh_from_db()
        self.assertEqual(self.recurso_uno.estado_operativo, Recurso.EstadoOperativo.OPERATIVO)
        self.assertEqual(self.recurso_uno.disponibilidad, Recurso.Disponibilidad.DISPONIBLE)
        self.assertFalse(HistorialEstadoRecurso.objects.exists())
