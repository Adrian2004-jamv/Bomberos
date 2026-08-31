from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso

from .models import EvaluacionCapacidadEstacion, RequisitoRecursoCapacidad, TipoCapacidadOperativa
class InterfazCapacidadesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="LAT-IC")
        cls.cuerpo_uno = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Bomberos Uno",
            sigla="CBU-IC",
            ruc="0594000000001",
            direccion="Centro",
        )
        cls.cuerpo_dos = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Bomberos Dos",
            sigla="CBD-IC",
            ruc="0594000000002",
            direccion="Sur",
        )
        cls.estacion_uno = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo_uno,
            nombre="Central",
            codigo="C-IC",
            direccion="Centro",
            latitud="-0.900000",
            longitud="-78.600000",
        )
        cls.estacion_uno_b = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo_uno,
            nombre="Norte",
            codigo="N-IC",
            direccion="Norte",
            latitud="-0.910000",
            longitud="-78.610000",
        )
        cls.estacion_dos = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo_dos,
            nombre="Sur",
            codigo="S-IC",
            direccion="Sur",
            latitud="-1.000000",
            longitud="-78.650000",
        )
        categoria = CategoriaRecurso.objects.create(nombre="Vehículos", codigo="VEH-IC")
        cls.tipo = TipoRecurso.objects.create(
            categoria=categoria,
            nombre="Autobomba",
            codigo="AUT-IC",
        )
        cls.capacidad = TipoCapacidadOperativa.objects.create(
            nombre="Incendios estructurales",
            codigo="IE-IC",
            descripcion="Respuesta mediante recursos materiales.",
        )
        RequisitoRecursoCapacidad.objects.create(
            capacidad=cls.capacidad,
            tipo_recurso=cls.tipo,
            cantidad_minima=1,
        )
        Recurso.objects.create(
            estacion=cls.estacion_uno,
            tipo=cls.tipo,
            codigo_interno="R-IC-1",
            nombre="Autobomba central",
        )
        cls.usuarios = {}
        configuraciones = (
            ("provincial-cap", "Responsable provincial", None, "0540000001"),
            ("institucional-cap", "Responsable institucional", cls.estacion_uno, "0540000002"),
            ("estacion-cap", "Responsable de estación", cls.estacion_uno, "0540000003"),
            ("inventario-cap", "Encargado de inventario", cls.estacion_uno, "0540000004"),
            ("consulta-cap", "Operador de consulta", cls.estacion_uno, "0540000005"),
        )
        for clave, grupo, estacion, cedula in configuraciones:
            usuario = get_user_model().objects.create_user(
                username=clave,
                cedula=cedula,
                password="clave",
                estacion=estacion,
            )
            usuario.groups.add(Group.objects.get(name=grupo))
            cls.usuarios[grupo] = usuario
        cls.evaluacion_ajena = EvaluacionCapacidadEstacion.objects.create(
            estacion=cls.estacion_dos,
            capacidad=cls.capacidad,
            estado=EvaluacionCapacidadEstacion.Estado.NO_CUMPLE,
            porcentaje_cumplimiento="0.00",
            detalle_recursos=[
                {
                    "nombre": "Autobomba",
                    "cantidad_requerida": 1,
                    "cantidad_encontrada": 0,
                    "faltante": 1,
                    "cumplimiento": False,
                }
            ],
            evaluado_por=cls.usuarios["Responsable provincial"],
        )

    def test_usuario_no_autenticado_es_redirigido(self):
        for nombre in (
            "lista_capacidades",
            "evaluar_capacidad",
            "historial_evaluaciones",
        ):
            with self.subTest(nombre=nombre):
                respuesta = self.client.get(reverse(f"operaciones:{nombre}"))
                self.assertEqual(respuesta.status_code, 302)

    def test_usuario_autorizado_consulta_catalogo_y_detalle(self):
        self.client.force_login(self.usuarios["Operador de consulta"])
        respuesta = self.client.get(reverse("operaciones:lista_capacidades"))
        self.assertContains(respuesta, self.capacidad.nombre)
        self.assertContains(respuesta, "1 requisito")
        detalle = self.client.get(
            reverse("operaciones:detalle_capacidad", args=[self.capacidad.pk])
        )
        self.assertContains(detalle, self.tipo.nombre)
        self.assertNotContains(detalle, "Personal operativo")

    def test_responsable_institucional_solo_selecciona_estaciones_de_su_cuerpo(self):
        self.client.force_login(self.usuarios["Responsable institucional"])
        respuesta = self.client.get(reverse("operaciones:evaluar_capacidad"))
        estaciones = respuesta.context["form"].fields["estacion"].queryset
        self.assertQuerySetEqual(
            estaciones,
            [self.estacion_uno, self.estacion_uno_b],
            ordered=False,
        )
        self.assertNotIn(self.estacion_dos, estaciones)

    def test_responsable_estacion_solo_evalua_su_estacion(self):
        usuario = self.usuarios["Responsable de estación"]
        self.client.force_login(usuario)
        respuesta = self.client.post(
            reverse("operaciones:evaluar_capacidad"),
            {
                "estacion": self.estacion_uno.pk,
                "tipo_capacidad": self.capacidad.pk,
                "observaciones": "Comprobación",
            },
        )
        evaluacion = EvaluacionCapacidadEstacion.objects.exclude(
            pk=self.evaluacion_ajena.pk
        ).get()
        self.assertRedirects(
            respuesta,
            reverse("operaciones:detalle_evaluacion", args=[evaluacion.pk]),
        )
        intento_ajeno = self.client.post(
            reverse("operaciones:evaluar_capacidad"),
            {
                "estacion": self.estacion_dos.pk,
                "tipo_capacidad": self.capacidad.pk,
                "observaciones": "Intento ajeno",
            },
        )
        self.assertEqual(intento_ajeno.status_code, 200)
        self.assertContains(intento_ajeno, "Escoja una opción válida")

    def test_operadores_de_consulta_no_ejecutan_evaluaciones(self):
        for grupo in ("Operador de consulta", "Encargado de inventario"):
            self.client.force_login(self.usuarios[grupo])
            with self.subTest(grupo=grupo):
                self.assertEqual(
                    self.client.get(reverse("operaciones:evaluar_capacidad")).status_code,
                    403,
                )
                self.assertEqual(
                    self.client.post(
                        reverse("operaciones:evaluar_capacidad"),
                        {
                            "estacion": self.estacion_uno.pk,
                            "tipo_capacidad": self.capacidad.pk,
                        },
                    ).status_code,
                    403,
                )

    def test_url_ajena_no_expone_evaluacion(self):
        self.client.force_login(self.usuarios["Responsable institucional"])
        respuesta = self.client.get(
            reverse("operaciones:detalle_evaluacion", args=[self.evaluacion_ajena.pk])
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_formulario_valido_utiliza_servicio_existente(self):
        usuario = self.usuarios["Responsable provincial"]
        self.client.force_login(usuario)
        evaluacion = EvaluacionCapacidadEstacion.objects.create(
            estacion=self.estacion_uno,
            capacidad=self.capacidad,
            estado=EvaluacionCapacidadEstacion.Estado.CUMPLE,
            porcentaje_cumplimiento="100.00",
            detalle_recursos=[],
            evaluado_por=usuario,
        )
        with patch(
            "operaciones.views.evaluar_capacidad_estacion",
            return_value=evaluacion,
        ) as servicio:
            respuesta = self.client.post(
                reverse("operaciones:evaluar_capacidad"),
                {
                    "estacion": self.estacion_uno.pk,
                    "tipo_capacidad": self.capacidad.pk,
                    "observaciones": "Prueba del servicio",
                },
            )
        servicio.assert_called_once_with(
            estacion=self.estacion_uno,
            tipo_capacidad=self.capacidad,
            usuario_evaluador=usuario,
            observaciones="Prueba del servicio",
        )
        self.assertRedirects(
            respuesta,
            reverse("operaciones:detalle_evaluacion", args=[evaluacion.pk]),
        )

    def test_detalle_historico_se_presenta_sin_json_crudo(self):
        self.client.force_login(self.usuarios["Responsable provincial"])
        respuesta = self.client.get(
            reverse(
                "operaciones:detalle_evaluacion",
                args=[self.evaluacion_ajena.pk],
            )
        )
        self.assertContains(respuesta, "Autobomba")
        self.assertContains(respuesta, "Encontrados")
        self.assertContains(respuesta, "Faltantes")
        self.assertNotContains(respuesta, "cantidad_requerida")

    def test_historial_es_solo_lectura(self):
        self.client.force_login(self.usuarios["Responsable provincial"])
        detalle = reverse(
            "operaciones:detalle_evaluacion",
            args=[self.evaluacion_ajena.pk],
        )
        historial = reverse("operaciones:historial_evaluaciones")
        self.assertEqual(self.client.post(detalle, {}).status_code, 405)
        self.assertEqual(self.client.post(historial, {}).status_code, 405)
        nombres_rutas = {patron.name for patron in __import__("operaciones.urls", fromlist=["urlpatterns"]).urlpatterns}
        self.assertNotIn("editar_evaluacion", nombres_rutas)
        self.assertNotIn("eliminar_evaluacion", nombres_rutas)

    def test_filtros_no_amplian_el_alcance_institucional(self):
        self.client.force_login(self.usuarios["Responsable institucional"])
        respuesta = self.client.get(
            reverse("operaciones:historial_evaluaciones"),
            {"estacion": self.estacion_dos.pk},
        )
        self.assertFalse(respuesta.context["evaluaciones"].object_list.exists())
        self.assertNotContains(respuesta, self.estacion_dos.nombre)
