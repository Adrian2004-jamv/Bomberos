import re
from pathlib import Path

from django.conf import settings

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso

from .forms_sci import RegistroRecursoSCI211Form, etiqueta_de_recurso
from .esquemas_sci import ESQUEMAS_SCI, HORA, TABLA, TEXTO, secciones_con_valores
from .models import DespliegueUnidad
from .models import Emergencia, FormularioSCI, FormularioSCI211, RegistroRecursoSCI211
from .services import desplegar_unidad
from .services_sci import (desplegar_recursos_del_sci211, finalizar_sci,
                           finalizar_sci211)

class SCI211Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Prueba", codigo="SCI-T")
        cls.cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Prueba", sigla="SCI-T", ruc="0599999999001",
            direccion="Dirección institucional",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo, nombre="Estación Norte", codigo="EN-SCI",
            direccion="Norte", latitud="-0.900000", longitud="-78.600000",
        )
        cls.otra_estacion = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo, nombre="Estación Sur", codigo="ES-SCI",
            direccion="Sur", latitud="-0.910000", longitud="-78.610000",
        )
        cls.otro_cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Otra Institución", sigla="SCI-O",
            ruc="0599999999002", direccion="Otra dirección",
        )
        cls.estacion_otra_institucion = Estacion.objects.create(
            cuerpo_bomberos=cls.otro_cuerpo, nombre="Estación Externa", codigo="EX-SCI",
            direccion="Exterior", latitud="-0.920000", longitud="-78.620000",
        )
        cls.usuario = cls._usuario("responsable-sci", "0571000001", "Responsable de estación", cls.estacion)
        cls.consulta = cls._usuario("consulta-sci", "0571000002", "Operador de consulta", cls.estacion)
        cls.otro = cls._usuario("otro-sci", "0571000003", "Responsable de estación", cls.otra_estacion)
        cls.otra_institucion = cls._usuario(
            "externo-sci", "0571000004", "Responsable institucional", cls.estacion_otra_institucion
        )
        cls.superusuario = get_user_model().objects.create_superuser(
            username="super-sci", cedula="0571000005", password="clave", estacion=None,
        )

    @classmethod
    def _usuario(cls, nombre, cedula, grupo, estacion):
        usuario = get_user_model().objects.create_user(username=nombre, cedula=cedula, password="clave", estacion=estacion)
        usuario.groups.add(Group.objects.get(name=grupo))
        return usuario

    def setUp(self):
        self.emergencia = Emergencia.objects.create(
            codigo="EM-SCI-001", tipo_emergencia="Incendio de prueba", direccion="Calle Ficticia 123",
            latitud="-0.933333", longitud="-78.616667", estacion_responsable=self.estacion,
            registrado_por=self.usuario,
        )

    def crear_formulario(self, completo=True):
        f = FormularioSCI211.objects.create(
            emergencia=self.emergencia, codigo="SCI-211-EM-SCI-001", punto_registro="Puesto de Comando",
            registrador_1="Usuario de Prueba", creado_por=self.usuario, modificado_por=self.usuario,
        )
        if completo:
            RegistroRecursoSCI211.objects.create(
                formulario=f, solicitado_por="CI Prueba", fecha_hora_solicitud=self.emergencia.fecha_reporte,
                clase_recurso="Vehículos", tipo_recurso="Autobomba", institucion_procedencia="Bomberos Prueba",
                matricula_identificacion="TEST-001", numero_personas=4, estado_recurso="disponible",
                asignado_a="Área de Espera", observaciones="Contenido <script>alert('x')</script> y ñ.",
            )
        return f

    def crear_recurso_verificado(self, estacion=None, codigo="REC-SCI-01"):
        categoria, _ = CategoriaRecurso.objects.get_or_create(
            codigo="CAT-SCI-TEST", defaults={"nombre": "Vehículos SCI prueba"}
        )
        tipo, _ = TipoRecurso.objects.get_or_create(
            categoria=categoria, codigo="TIP-SCI-TEST",
            defaults={"nombre": "Autobomba SCI prueba"},
        )
        return Recurso.objects.create(
            estacion=estacion or self.estacion, tipo=tipo,
            codigo_interno=codigo, nombre="Autobomba verificada",
            estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
            disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
            fecha_confirmacion_disponibilidad=timezone.now(),
        )

    def cerrar_el_211(self, formulario):
        """Cierra el SCI-211 como se cierra en la realidad: con la emergencia
        terminada. Antes bastaba con pedirlo, pero el registro de recursos
        sigue abierto mientras puedan llegar unidades."""
        Emergencia.objects.filter(pk=self.emergencia.pk).update(
            estado=Emergencia.Estado.CERRADA
        )
        self.emergencia.refresh_from_db()
        formulario.refresh_from_db()
        return finalizar_sci211(formulario, self.usuario)

    def finalizar_anteriores(self, codigo_objetivo):
        """Prepara el flujo previo cuando una prueba se enfoca en un paso posterior."""
        orden = ["201", "207", "211", "202", "203", "204", "205", "206",
                 "215", "214", "221", "222"]
        for codigo in orden[:orden.index(codigo_objetivo)]:
            if codigo == "211":
                formulario, _ = FormularioSCI211.objects.get_or_create(
                    emergencia=self.emergencia,
                    defaults={
                        "codigo": f"SCI-211-{self.emergencia.pk}",
                        "punto_registro": "Puesto de Comando",
                        "registrador_1": self.usuario.username,
                        "creado_por": self.usuario,
                        "modificado_por": self.usuario,
                    },
                )
                # El SCI-211 no se finaliza con la emergencia abierta: para la
                # cadena basta con que tenga recursos anotados, que es el
                # estado real en el que estará durante toda la intervención.
                if not formulario.registros.exists():
                    formulario.registros.create(
                        orden=1, solicitado_por="Comandante de Incidente",
                        fecha_hora_solicitud=self.emergencia.fecha_reporte,
                        clase_recurso="Vehículos", tipo_recurso="Autobomba",
                        institucion_procedencia="Cuerpo de Bomberos",
                        matricula_identificacion="PREVIO-01",
                        numero_personas=1, asignado_a="Zona de operaciones",
                    )
            else:
                formulario, _ = FormularioSCI.objects.get_or_create(
                    emergencia=self.emergencia, codigo_sci=codigo,
                    defaults={
                        "datos": {"preparado": True},
                        "creado_por": self.usuario,
                        "modificado_por": self.usuario,
                    },
                )
                formulario.estado = FormularioSCI.Estado.FINALIZADO
                formulario.finalizado_por = self.usuario
                formulario.fecha_finalizacion = timezone.now()
                formulario.save(update_fields=(
                    "estado", "finalizado_por", "fecha_finalizacion"
                ))

    def test_creacion_autorizada_y_borrador(self):
        self.finalizar_anteriores("211")
        self.client.force_login(self.usuario)
        respuesta = self.client.post(reverse("emergencias:sci211_crear", args=[self.emergencia.pk]))
        self.assertEqual(respuesta.status_code, 302)
        formulario = FormularioSCI211.objects.get(emergencia=self.emergencia)
        self.assertEqual(formulario.estado, FormularioSCI211.Estado.BORRADOR)
        self.assertEqual(formulario.registrador_1, self.usuario.username)

        formulario.punto_registro = "Área de Espera editada"
        formulario.save(update_fields=("punto_registro",))
        segunda = self.client.post(reverse("emergencias:sci211_crear", args=[self.emergencia.pk]))
        self.assertEqual(segunda.status_code, 302)
        self.assertEqual(FormularioSCI211.objects.filter(emergencia=self.emergencia).count(), 1)
        formulario.refresh_from_db()
        self.assertEqual(formulario.punto_registro, "Área de Espera editada")

    def test_restriccion_unica_impide_duplicado(self):
        self.crear_formulario()
        with self.assertRaises(IntegrityError), transaction.atomic():
            FormularioSCI211.objects.create(
                emergencia=self.emergencia, codigo="SCI-211-DUPLICADO",
                punto_registro="Base", registrador_1="Prueba",
                creado_por=self.usuario, modificado_por=self.usuario,
            )

    def test_finalizacion_congela_datos_e_impide_edicion(self):
        self.finalizar_anteriores("211")
        formulario = self.cerrar_el_211(self.crear_formulario())
        self.assertEqual(formulario.estado, FormularioSCI211.Estado.FINALIZADO)
        self.assertEqual(formulario.institucion_emitida, self.cuerpo.nombre)
        self.assertEqual(formulario.incidente_nombre_emitido, self.emergencia.tipo_emergencia)
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse("emergencias:sci211_editar", args=[formulario.pk])).status_code, 302)
        respuesta = self.client.post(reverse("emergencias:sci211_editar", args=[formulario.pk]), {"punto_registro": "ALTERADO"})
        self.assertEqual(respuesta.status_code, 302)
        formulario.refresh_from_db()
        self.assertEqual(formulario.punto_registro, "Puesto de Comando")
        self.assertNotContains(self.client.get(reverse("emergencias:sci211_detalle", args=[formulario.pk])), "Eliminar")

    def test_no_finaliza_incompleto(self):
        formulario = self.crear_formulario(completo=False)
        self.client.force_login(self.usuario)
        respuesta = self.client.post(reverse("emergencias:sci211_finalizar", args=[formulario.pk]))
        formulario.refresh_from_db()
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(formulario.estado, FormularioSCI211.Estado.BORRADOR)

    def _datos_edicion(self, formulario, accion=None):
        """POST completo de la pantalla de edicion, con un recurso valido."""
        datos = {
            "punto_registro": "Puesto de Comando",
            "registrador_1": "Usuario de Prueba",
            "registrador_2": "",
            "registrador_3": "",
            "registros-TOTAL_FORMS": "1",
            "registros-INITIAL_FORMS": "0",
            "registros-MIN_NUM_FORMS": "1",
            "registros-MAX_NUM_FORMS": "1000",
            "registros-0-id": "",
            "registros-0-formulario": str(formulario.pk),
            "registros-0-solicitado_por": "Comandante de Incidente",
            "registros-0-fecha_hora_solicitud": "2026-08-21T09:15",
            "registros-0-clase_recurso": "Vehículos",
            "registros-0-tipo_recurso": "Autobomba",
            "registros-0-fecha_hora_arribo": "2026-08-21T09:32",
            "registros-0-institucion_procedencia": "Cuerpo de Bomberos de Latacunga",
            "registros-0-matricula_identificacion": "AB-01",
            "registros-0-numero_personas": "4",
            "registros-0-estado_recurso": "disponible",
            "registros-0-asignado_a": "Sector El Salto",
            "registros-0-desmovilizado_por": "",
            "registros-0-fecha_hora_desmovilizacion": "",
            "registros-0-observaciones": "Unidad en ataque inicial.",
        }
        if accion:
            datos["accion"] = accion
        return datos

    def test_finalizar_desde_la_edicion_guarda_antes_de_continuar(self):
        self.finalizar_anteriores("211")
        """El boton de finalizar debe enviar el formulario, no navegar fuera de el.

        Cuando era un enlace, lo escrito se perdia y el usuario chocaba con
        «Debe registrar al menos un recurso antes de finalizar».
        """
        formulario = self.crear_formulario(completo=False)
        self.client.force_login(self.usuario)
        respuesta = self.client.post(
            reverse("emergencias:sci211_editar", args=[formulario.pk]),
            self._datos_edicion(formulario, accion="finalizar"),
        )
        self.assertRedirects(
            respuesta, reverse("emergencias:sci211_finalizar", args=[formulario.pk])
        )
        self.assertEqual(formulario.registros.count(), 1)
        registro = formulario.registros.get()
        self.assertEqual(registro.matricula_identificacion, "AB-01")
        self.assertEqual(registro.orden, 1)

    def test_guardar_borrador_regresa_a_la_ficha_de_la_emergencia(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario(completo=False)
        self.client.force_login(self.usuario)
        respuesta = self.client.post(
            reverse("emergencias:sci211_editar", args=[formulario.pk]),
            self._datos_edicion(formulario),
        )
        self.assertRedirects(
            respuesta,
            reverse("emergencias:detalle", args=[self.emergencia.pk]) + "#formularios-sci",
        )
        self.assertEqual(formulario.registros.count(), 1)

    def test_restriccion_estacion_y_solo_lectura(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        self.client.force_login(self.otro)
        self.assertEqual(self.client.get(reverse("emergencias:sci211_detalle", args=[formulario.pk])).status_code, 404)
        self.client.force_login(self.consulta)
        self.assertEqual(self.client.get(reverse("emergencias:sci211_detalle", args=[formulario.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("emergencias:sci211_editar", args=[formulario.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("emergencias:sci211_imprimir", args=[formulario.pk])).status_code, 200)
        self.client.force_login(self.otra_institucion)
        self.assertEqual(self.client.get(reverse("emergencias:sci211_detalle", args=[formulario.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("emergencias:sci211_crear", args=[self.emergencia.pk])).status_code, 404)

    def test_acceso_anonimo_requiere_autenticacion(self):
        formulario = self.crear_formulario()
        for nombre, args in (
            ("sci211_lista", []), ("sci211_detalle", [formulario.pk]),
            ("sci211_editar", [formulario.pk]), ("sci211_finalizar", [formulario.pk]),
            ("sci211_imprimir", [formulario.pk]),
        ):
            self.assertEqual(self.client.get(reverse(f"emergencias:{nombre}", args=args)).status_code, 302)

    def test_integracion_detalle_muestra_accion_estado_y_actualizacion(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:detalle", args=[self.emergencia.pk]))
        # La acción vive solo en el aviso del paso siguiente: el encabezado
        # repetía el mismo botón sin decir de qué formulario se trataba. Con el
        # 211 ya en uso, el paso que se anuncia es el que sigue.
        self.assertContains(respuesta, "Registro abierto")
        self.assertContains(respuesta, "Siguiente: SCI-202")
        self.assertContains(respuesta, 'class="sci-next-step__cta"', html=False)
        self.assertNotContains(respuesta, "Continuar SCI-211")
        self.assertContains(respuesta, "Incompleto o con errores")
        # El 211 con recursos ya no comparte el ámbar de lo incompleto.
        self.assertContains(
            respuesta, 'class="sci-form-tab sci-form-tab--open"', html=False
        )
        self.assertContains(
            respuesta, 'class="sci-form-tab sci-form-tab--locked"', html=False
        )
        self.assertContains(respuesta, "Paso 1: SCI-201")
        self.cerrar_el_211(formulario)
        respuesta = self.client.get(reverse("emergencias:detalle", args=[self.emergencia.pk]))
        self.assertNotContains(respuesta, "Consultar SCI-211")
        self.assertNotContains(respuesta, "Vista imprimible")
        self.assertContains(respuesta, "Formularios disponibles para imprimir")
        self.assertContains(respuesta, "SCI-211")
        self.assertContains(respuesta, 'class="sci-form-tabs"', html=False)
        self.assertContains(respuesta, 'class="sci-form-tab sci-form-tab--complete"', html=False)
        self.assertContains(respuesta, "Finalizado correctamente")

    def test_detalle_presenta_el_orden_operativo_del_manual(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:detalle", args=[self.emergencia.pk])
        )
        self.assertEqual(
            [item["codigo"] for item in respuesta.context["catalogo_sci"]],
            ["201", "207", "211", "202", "203", "204", "205", "206",
             "215", "214", "221", "222"],
        )
        self.assertContains(respuesta, "Orden recomendado según las fases")
        self.assertContains(respuesta, "Resumen del Incidente")
        self.assertContains(respuesta, "Plan de Comunicaciones")
        self.assertContains(respuesta, "Verificación de la Desmovilización")

    def test_ver_el_sci_211_sin_crearlo_muestra_la_cuadricula_en_blanco(self):
        """Antes respondia 404: el 211 no figura entre los esquemas editables."""
        self.finalizar_anteriores("211")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse(
            "emergencias:sci_visualizar", args=["211", self.emergencia.pk]
        ))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Formulario SCI-211")
        self.assertContains(respuesta, "A. Solicitud")
        self.assertContains(respuesta, "12. Observaciones")

    def test_ver_el_sci_211_ya_creado_lleva_a_su_documento(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse(
            "emergencias:sci_visualizar", args=["211", self.emergencia.pk]
        ))
        self.assertRedirects(
            respuesta, reverse("emergencias:sci211_imprimir", args=[formulario.pk])
        )

    def test_al_comenzar_estan_abiertos_el_primero_y_las_bitacoras(self):
        """Las bitácoras no esperan turno: el carro sale antes de que nadie
        redacte el resumen del incidente, y las actividades del periodo
        empiezan mucho antes de que el plan de acción esté escrito."""
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:detalle", args=[self.emergencia.pk])
        )
        catalogo = respuesta.context["catalogo_sci"]
        abiertos = {item["codigo"] for item in catalogo if not item["bloqueado"]}
        self.assertEqual(abiertos, {"201", "211", "214"})
        self.assertContains(respuesta, 'class="sci-form-tab sci-form-tab--locked"')
        self.assertNotContains(
            respuesta,
            reverse("emergencias:sci_visualizar", args=["207", self.emergencia.pk]),
        )

    def test_url_directa_no_permite_saltar_el_orden(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse(
            "emergencias:sci_editar", args=["202", self.emergencia.pk]
        ))
        self.assertRedirects(
            respuesta,
            reverse("emergencias:detalle", args=[self.emergencia.pk])
            + "#formularios-sci",
        )

    def test_finalizar_un_paso_desbloquea_solo_el_siguiente(self):
        FormularioSCI.objects.create(
            emergencia=self.emergencia, codigo_sci="201", datos={"ok": True},
            estado=FormularioSCI.Estado.FINALIZADO,
            creado_por=self.usuario, modificado_por=self.usuario,
            finalizado_por=self.usuario, fecha_finalizacion=timezone.now(),
        )
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:detalle", args=[self.emergencia.pk])
        )
        catalogo = respuesta.context["catalogo_sci"]
        abiertos = {item["codigo"] for item in catalogo if not item["bloqueado"]}
        # El 201 ya cerrado sigue siendo accesible, el 207 se abre detrás de él
        # y las bitácoras nunca esperaron. El 202 aguarda al 207 y al 211.
        self.assertEqual(abiertos, {"201", "207", "211", "214"})

    def test_editor_generico_solo_ofrece_inventario_verificado_del_ambito(self):
        self.finalizar_anteriores("202")
        recurso = self.crear_recurso_verificado()
        ajeno = self.crear_recurso_verificado(
            estacion=self.estacion_otra_institucion, codigo="REC-AJENO"
        )
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse(
            "emergencias:sci_editar", args=["202", self.emergencia.pk]
        ))
        self.assertContains(respuesta, str(recurso.pk))
        self.assertContains(respuesta, "REC-SCI-01 - Autobomba verificada")
        self.assertNotContains(respuesta, "REC-AJENO")

        respuesta = self.client.post(reverse(
            "emergencias:sci_editar", args=["202", self.emergencia.pk]
        ), {
            "plan-0-estrategia": "Controlar incendio",
            "plan-0-tactica": "Ataque directo",
            # Va en «por solicitar»: «en el lugar» solo admite lo que el
            # SCI-211 haya registrado, y esta unidad sigue en la estación.
            "plan-0-recursos_lugar": "",
            "plan-0-recursos_solicitar": str(recurso.pk),
            "plan-0-asignacion": "División A",
        })
        self.assertEqual(respuesta.status_code, 302)
        guardado = FormularioSCI.objects.get(
            emergencia=self.emergencia, codigo_sci="202"
        )
        self.assertIn("REC-SCI-01 - Autobomba verificada", str(guardado.datos))
        self.assertNotIn(str(ajeno.pk), str(guardado.datos))

    def test_sci211_autocompleta_datos_desde_el_recurso_seleccionado(self):
        recurso = self.crear_recurso_verificado()
        form = RegistroRecursoSCI211Form(data={
            "recurso_inventario": recurso.pk,
            "solicitado_por": "Comandante",
            "fecha_hora_solicitud": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
            "numero_personas": 1,
            "estado_recurso": "disponible",
            "asignado_a": "Área de Espera",
        }, usuario=self.usuario)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["matricula_identificacion"], "REC-SCI-01")
        self.assertEqual(form.cleaned_data["institucion_procedencia"], self.cuerpo.nombre)

    def test_menu_incluye_formularios_sci_y_marca_opcion_activa(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:lista"))
        self.assertContains(respuesta, "Formularios SCI")
        self.assertContains(respuesta, reverse("emergencias:sci211_lista"))
        respuesta = self.client.get(reverse("emergencias:sci211_lista"))
        self.assertContains(
            respuesta,
            f'href="{reverse("emergencias:sci211_lista")}" aria-current="page"',
            html=False,
        )

    def test_accion_es_primer_modulo_y_formularios_no_activa_accion(self):
        self.finalizar_anteriores("215")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:lista"))
        contenido = respuesta.content.decode()
        self.assertLess(contenido.index("> Acción"), contenido.index("> Panel de control"))
        self.assertContains(
            respuesta,
            f'href="{reverse("emergencias:lista")}" aria-current="page"',
            html=False,
        )

        formulario_sci = self.client.get(reverse(
            "emergencias:sci_editar", args=["215", self.emergencia.pk]
        ))
        self.assertContains(
            formulario_sci,
            f'href="{reverse("emergencias:sci211_lista")}" aria-current="page"',
            html=False,
        )
        self.assertNotContains(
            formulario_sci,
            f'href="{reverse("emergencias:lista")}" aria-current="page"',
            html=False,
        )

    def test_superusuario_sin_estacion_ve_boton_y_centro_de_formularios(self):
        formulario = self.crear_formulario()
        self.client.force_login(self.superusuario)
        respuesta = self.client.get(reverse("emergencias:lista"))
        self.assertContains(respuesta, "Formularios SCI")
        respuesta = self.client.get(reverse("emergencias:sci211_lista"))
        self.assertContains(respuesta, "Expedientes operativos")
        self.assertContains(respuesta, formulario.codigo)
        self.assertContains(respuesta, "Editar")
        self.assertContains(respuesta, "Visualizar e imprimir")

    def test_catalogo_muestra_los_doce_formularios_y_sus_fichas(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:sci211_lista"))
        self.assertContains(respuesta, "Formularios organizados por incidente")
        self.assertContains(respuesta, "Consultar catálogo general de formularios")
        self.assertNotContains(respuesta, "Seleccionar formulario SCI")
        self.assertNotContains(respuesta, "selector_formularios_sci.js")
        self.assertContains(respuesta, 'class="panel sci-catalog-panel sci-catalog-disclosure sci-catalog-disclosure--standalone"', html=False)
        for codigo in ("201", "202", "203", "204", "205", "206", "207", "211", "214", "215", "221", "222"):
            self.assertContains(respuesta, f"SCI-{codigo}")
        self.assertContains(respuesta, "Editable", count=12)

        ficha = self.client.get(reverse("emergencias:sci_catalogo_detalle", args=["205"]))
        self.assertEqual(ficha.status_code, 200)
        self.assertContains(ficha, "Plan de Comunicaciones")
        self.assertContains(ficha, "Edición, consulta e impresión habilitadas")

        inexistente = self.client.get(reverse("emergencias:sci_catalogo_detalle", args=["999"]))
        self.assertEqual(inexistente.status_code, 404)

    def test_incidentes_se_despliegan_y_muestran_solo_formularios_existentes(self):
        self.crear_formulario()
        FormularioSCI.objects.create(
            emergencia=self.emergencia,
            codigo_sci="205",
            datos={"periodo": "En curso"},
            creado_por=self.usuario,
            modificado_por=self.usuario,
        )
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse("emergencias:sci211_lista"))

        self.assertContains(respuesta, "data-sci-incident", html=False)
        self.assertContains(respuesta, f'data-incident-code="{self.emergencia.codigo}"', html=False)
        expediente = next(item for item in respuesta.context["expedientes"] if item.pk == self.emergencia.pk)
        self.assertEqual([documento["codigo"] for documento in expediente.documentos_sci], ["211", "205"])
        self.assertContains(respuesta, 'data-document-code="205"', html=False)
        self.assertContains(respuesta, 'data-document-code="211"', html=False)
        self.assertContains(respuesta, 'class="sci-expedient-action"', html=False)
        self.assertContains(respuesta, 'class="sci-doc-action sci-doc-action--edit"', html=False)
        self.assertContains(respuesta, 'class="sci-doc-action sci-doc-action--view"', html=False)
        self.assertContains(respuesta, "ti-printer", html=False)

    def test_catalogo_permite_visualizar_los_doce_formularios_sin_incidente(self):
        self.client.force_login(self.usuario)
        for codigo in ("201", "202", "203", "204", "205", "206", "207", "211", "214", "215", "221", "222"):
            with self.subTest(codigo=codigo):
                respuesta = self.client.get(reverse("emergencias:sci_catalogo_visualizar", args=[codigo]))
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, f"Formulario SCI-{codigo}")
                self.assertContains(respuesta, "VISTA-PREVIA")
                self.assertContains(respuesta, "Vista de catálogo sin incidente asociado")

    def test_todos_los_formularios_tienen_visualizacion_vinculada_a_emergencia(self):
        self.finalizar_anteriores("222")
        self.client.force_login(self.usuario)
        for codigo in ("201", "202", "203", "204", "205", "206", "207", "214", "215", "221", "222"):
            respuesta = self.client.get(reverse(
                "emergencias:sci_visualizar", args=[codigo, self.emergencia.pk]
            ))
            self.assertEqual(respuesta.status_code, 200)
            self.assertContains(respuesta, f"Formulario SCI-{codigo}")
            self.assertContains(respuesta, self.emergencia.tipo_emergencia)
            self.assertContains(respuesta, "Imprimir")

    def test_formulario_generico_guarda_tabla_y_periodo_operacional(self):
        self.finalizar_anteriores("205")
        recurso = self.crear_recurso_verificado(codigo="RADIO-SCI-01")
        self.client.force_login(self.usuario)
        url = reverse("emergencias:sci_editar", args=["205", self.emergencia.pk])
        respuesta = self.client.post(url, {
            "periodo_numero": "1",
            "periodo_inicio": "2026-08-18T08:00",
            "periodo_fin": "2026-08-18T20:00",
            "canales-0-sistema": str(recurso.pk),
            "canales-0-canal": "Canal 1",
            "canales-0-asignado": "Comando",
            "canales-0-ubicacion": "Puesto de Comando",
            "canales-0-observaciones": "Sin novedades",
            "canales-1-sistema": str(recurso.pk),
            "canales-1-canal": "Canal 2",
            "canales-1-asignado": "Operaciones",
            "canales-1-ubicacion": "Zona caliente",
            "canales-1-observaciones": "",
            "preparado_por": "Luis Herrera",
        })
        self.assertRedirects(
            respuesta,
            reverse("emergencias:detalle", args=[self.emergencia.pk]) + "#formularios-sci",
        )
        formulario = FormularioSCI.objects.get(emergencia=self.emergencia, codigo_sci="205")
        self.assertEqual(formulario.datos["periodo_numero"], "1")
        self.assertEqual(len(formulario.datos["canales"]), 2)
        self.assertEqual(formulario.datos["canales"][0]["canal"], "Canal 1")
        self.assertEqual(formulario.preparado_por, "Luis Herrera")
        impresion = self.client.get(reverse(
            "emergencias:sci_visualizar", args=["205", self.emergencia.pk]
        ))
        self.assertContains(impresion, "RADIO-SCI-01 - Autobomba verificada")
        self.assertContains(impresion, "Zona caliente")
        self.assertContains(impresion, "Editar")

    def test_filas_vacias_no_se_guardan(self):
        self.finalizar_anteriores("215")
        self.client.force_login(self.usuario)
        self.client.post(reverse("emergencias:sci_editar", args=["215", self.emergencia.pk]), {
            "analisis-0-area": "Perímetro",
            "analisis-0-riesgo": "Colapso estructural",
            "analisis-0-accion": "Acordonar 20 m",
            "analisis-1-area": "",
            "analisis-1-riesgo": "",
            "analisis-1-accion": "",
        })
        formulario = FormularioSCI.objects.get(emergencia=self.emergencia, codigo_sci="215")
        self.assertEqual(len(formulario.datos["analisis"]), 1)

    def test_formulario_con_filas_fijas_conserva_las_posiciones_oficiales(self):
        self.finalizar_anteriores("203")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse(
            "emergencias:sci_editar", args=["203", self.emergencia.pk]
        ))
        self.assertContains(respuesta, "Oficial de Seguridad")
        self.assertContains(respuesta, "Unidad de Desmovilización")
        self.assertContains(respuesta, "D. Rama Operaciones Aéreas — Supervisor de ala fija")

    def test_finalizar_bloquea_la_edicion_del_formulario_generico(self):
        self.finalizar_anteriores("214")
        self.client.force_login(self.usuario)
        self.client.post(reverse("emergencias:sci_editar", args=["214", self.emergencia.pk]), {
            "actividades-0-hora": "09:15",
            "actividades-0-evento": "Arribo de la primera unidad",
        })
        # El SCI-214 es la bitácora del periodo operacional: se cierra cuando
        # la emergencia termina, igual que el registro de recursos.
        Emergencia.objects.filter(pk=self.emergencia.pk).update(
            estado=Emergencia.Estado.CERRADA
        )
        finalizar = reverse("emergencias:sci_finalizar", args=["214", self.emergencia.pk])
        self.client.post(finalizar)
        formulario = FormularioSCI.objects.get(emergencia=self.emergencia, codigo_sci="214")
        self.assertEqual(formulario.estado, FormularioSCI.Estado.FINALIZADO)
        self.assertEqual(formulario.finalizado_por, self.usuario)
        edicion = self.client.get(reverse("emergencias:sci_editar", args=["214", self.emergencia.pk]))
        self.assertRedirects(
            edicion, reverse("emergencias:sci_visualizar", args=["214", self.emergencia.pk])
        )

    def test_no_se_puede_finalizar_un_formulario_vacio(self):
        self.finalizar_anteriores("206")
        self.client.force_login(self.usuario)
        self.client.get(reverse("emergencias:sci_editar", args=["206", self.emergencia.pk]))
        self.client.post(reverse("emergencias:sci_finalizar", args=["206", self.emergencia.pk]))
        formulario = FormularioSCI.objects.get(emergencia=self.emergencia, codigo_sci="206")
        self.assertEqual(formulario.estado, FormularioSCI.Estado.BORRADOR)

    def test_codigo_sci_inexistente_devuelve_404(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse(
            "emergencias:sci_visualizar", args=["999", self.emergencia.pk]
        ))
        self.assertEqual(respuesta.status_code, 404)

    def test_editor_carga_estilos_documentales_y_acciones_funcionales(self):
        self.finalizar_anteriores("215")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse(
            "emergencias:sci_editar", args=["215", self.emergencia.pk]
        ))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "emergencias/css/sci_editor.css")
        self.assertContains(respuesta, 'id="sci-document-form"', html=False)
        self.assertContains(respuesta, 'form="sci-document-form"', html=False)
        self.assertContains(respuesta, "Guardar cambios")
        self.assertContains(respuesta, "Vista de impresión")

    def test_vista_imprimible_protegida_y_original_intacto(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        original = Path("Total de Formularios SCI/SCI - 211 formulario.xlsx")
        antes = original.read_bytes()
        self.assertEqual(self.client.get(reverse("emergencias:sci211_imprimir", args=[formulario.pk])).status_code, 302)
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:sci211_imprimir", args=[formulario.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Formulario SCI - 211")
        self.assertContains(respuesta, "window.print()")
        self.assertEqual(original.read_bytes(), antes)

    def test_hoja_imprimible_escapa_html_y_representa_espanol(self):
        formulario = self.crear_formulario()
        html = render_to_string("emergencias/sci211/pdf.html", {"formulario": formulario})
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("Matrícula", html)
        self.assertIn("@page", html)

class ControlesDeFechaSCITests(TestCase):
    """Las columnas de fecha se llenan con un calendario, no escribiendo."""

    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="FEC-T")
        cuerpo = CuerpoBomberos.objects.create(
            canton=canton, nombre="Bomberos Fechas", sigla="FEC-T",
            ruc="0596000000900", direccion="Centro",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo, nombre="Estación Fechas", codigo="EF-SCI",
            direccion="Centro", latitud="-0.930000", longitud="-78.610000",
        )
        cls.usuario = get_user_model().objects.create_user(
            username="fechas-sci", cedula="0800000001", password="clave",
            estacion=cls.estacion,
        )
        cls.usuario.groups.add(Group.objects.get(name="Responsable institucional"))
        cls.emergencia = Emergencia.objects.create(
            codigo="IE-01012026-900", tipo_emergencia="Incendio estructural",
            direccion="Centro", estacion_responsable=cls.estacion,
            registrado_por=cls.usuario,
        )

    def editar(self, codigo):
        self.client.force_login(self.usuario)
        return self.client.get(reverse(
            "emergencias:sci_editar", args=[codigo, self.emergencia.pk]
        ))

    def test_el_sci_201_ofrece_calendario_en_el_resumen_de_acciones(self):
        respuesta = self.editar("201")
        self.assertContains(respuesta, 'type="datetime-local" name="acciones-0-fecha_hora"')

    def test_el_sci_214_declara_su_columna_de_hora(self):
        """El 214 se abre al final del flujo, así que se revisa su esquema.

        Llegar a él por la interfaz exige finalizar los nueve formularios
        anteriores, que es lo que comprueban las pruebas del flujo secuencial.
        """
        seccion = next(
            s for s in ESQUEMAS_SCI["214"]["secciones"] if s["nombre"] == "actividades"
        )
        columna = next(c for c in seccion["columnas"] if c["nombre"] == "hora")
        self.assertEqual(columna["tipo"], HORA)

    def test_una_columna_de_hora_se_dibuja_con_reloj(self):
        seccion = next(
            s for s in ESQUEMAS_SCI["214"]["secciones"] if s["nombre"] == "actividades"
        )
        filas = secciones_con_valores(ESQUEMAS_SCI["214"], {})
        actividades = next(s for s in filas if s["nombre"] == "actividades")
        primera = actividades["filas"][0]["celdas"][0]
        self.assertEqual(primera["tipo"], HORA)
        self.assertEqual(seccion["columnas"][0]["etiqueta"], "Hora")

    def test_las_columnas_de_texto_siguen_siendo_texto(self):
        respuesta = self.editar("201")
        self.assertContains(respuesta, 'name="acciones-0-accion"')
        self.assertNotContains(respuesta, 'type="datetime-local" name="acciones-0-accion"')

    def test_un_valor_anterior_sin_formato_no_desaparece(self):
        """Lo escrito antes de que la columna tuviera tipo debe seguir visible."""
        FormularioSCI.objects.create(
            emergencia=self.emergencia, codigo_sci="201",
            datos={"acciones": [{"fecha_hora": "aasdas", "accion": "Arribo"}]},
            creado_por=self.usuario, modificado_por=self.usuario,
        )
        respuesta = self.editar("201")
        self.assertContains(respuesta, "aasdas")
        self.assertNotContains(respuesta, 'type="datetime-local" name="acciones-0-fecha_hora"')

    def test_un_valor_con_formato_valido_usa_el_calendario(self):
        FormularioSCI.objects.create(
            emergencia=self.emergencia, codigo_sci="201",
            datos={"acciones": [{"fecha_hora": "2026-03-10T09:15", "accion": "Arribo"}]},
            creado_por=self.usuario, modificado_por=self.usuario,
        )
        respuesta = self.editar("201")
        self.assertContains(respuesta, 'type="datetime-local" name="acciones-0-fecha_hora"')
        self.assertContains(respuesta, 'value="2026-03-10T09:15"')

    def test_la_impresion_permite_cortar_palabras_largas(self):
        FormularioSCI.objects.create(
            emergencia=self.emergencia, codigo_sci="201",
            datos={"estrategias": "a" * 400},
            creado_por=self.usuario, modificado_por=self.usuario,
        )
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse(
            "emergencias:sci_visualizar", args=["201", self.emergencia.pk]
        ))
        self.assertContains(respuesta, "overflow-wrap:anywhere")
        self.assertContains(respuesta, "table-layout:fixed")

class DespachoDesdeSCI211Tests(SCI211Tests):
    """Registrar una unidad en el SCI-211 es la decisión de despacharla."""

    def crear_unidad_desplegable(self, codigo="AB-SCI-01"):
        categoria, _ = CategoriaRecurso.objects.get_or_create(
            codigo="CAT-DESP", defaults={"nombre": "Vehículos"}
        )
        tipo, _ = TipoRecurso.objects.get_or_create(
            categoria=categoria, codigo="TIP-DESP",
            defaults={"nombre": "Autobomba", "es_unidad_desplegable": True},
        )
        return Recurso.objects.create(
            estacion=self.estacion, tipo=tipo, codigo_interno=codigo,
            nombre="Autobomba desplegable",
            estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
            disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
            fecha_confirmacion_disponibilidad=timezone.now(),
        )

    def guardar_con_recurso(self, formulario, recurso):
        self.client.force_login(self.usuario)
        registro = formulario.registros.first()
        return self.client.post(
            reverse("emergencias:sci211_editar", args=[formulario.pk]),
            {
                "punto_registro": "Puesto de Comando",
                "registrador_1": "Usuario de Prueba",
                "registrador_2": "", "registrador_3": "",
                "registros-TOTAL_FORMS": "1", "registros-INITIAL_FORMS": "1",
                "registros-MIN_NUM_FORMS": "1", "registros-MAX_NUM_FORMS": "1000",
                "registros-0-id": str(registro.pk),
                "registros-0-recurso_inventario": str(recurso.pk),
                "registros-0-solicitado_por": "CI Prueba",
                "registros-0-fecha_hora_solicitud": "2026-08-29T10:00",
                "registros-0-tipo_recurso": "", "registros-0-clase_recurso": "",
                "registros-0-institucion_procedencia": "",
                "registros-0-matricula_identificacion": "",
                "registros-0-numero_personas": "2",
                "registros-0-estado_recurso": "disponible",
                "registros-0-asignado_a": "Área de Espera",
                "registros-0-desmovilizado_por": "",
                "registros-0-observaciones": "",
            },
        )

    def test_registrar_una_unidad_la_despacha(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        unidad = self.crear_unidad_desplegable()
        self.guardar_con_recurso(formulario, unidad)

        despliegue = DespliegueUnidad.objects.filter(
            emergencia=self.emergencia, unidad=unidad
        ).first()
        self.assertIsNotNone(despliegue)
        self.assertIn(despliegue.estado, DespliegueUnidad.ESTADOS_ACTIVOS)
        unidad.refresh_from_db()
        self.assertEqual(unidad.disponibilidad, Recurso.Disponibilidad.ASIGNADO)

    def test_el_registro_queda_enlazado_a_su_despliegue(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        unidad = self.crear_unidad_desplegable()
        self.guardar_con_recurso(formulario, unidad)

        registro = formulario.registros.first()
        self.assertIsNotNone(registro.despliegue)
        self.assertEqual(registro.despliegue.unidad, unidad)

    def test_guardar_dos_veces_no_despacha_por_duplicado(self):
        """Antes obligaba a despachar aparte y quedaba el riesgo de repetirlo."""
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        unidad = self.crear_unidad_desplegable()
        self.guardar_con_recurso(formulario, unidad)
        self.guardar_con_recurso(formulario, unidad)

        self.assertEqual(
            DespliegueUnidad.objects.filter(emergencia=self.emergencia, unidad=unidad).count(), 1
        )

    def test_un_equipo_que_no_es_unidad_no_genera_despliegue(self):
        """El SCI-211 registra también equipos; un ERA no sale como unidad."""
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        equipo = self.crear_recurso_verificado(codigo="ERA-SCI-01")
        self.guardar_con_recurso(formulario, equipo)

        self.assertFalse(
            DespliegueUnidad.objects.filter(emergencia=self.emergencia, unidad=equipo).exists()
        )

    def test_una_unidad_ya_ocupada_no_se_puede_registrar(self):
        """Al despacharla queda ASIGNADA y sale del desplegable de recursos.

        El formulario la rechaza antes de intentar el despacho, que es la
        barrera correcta: una unidad no puede atender dos emergencias.
        """
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        unidad = self.crear_unidad_desplegable()
        otra = Emergencia.objects.create(
            codigo="IE-01012026-777", tipo_emergencia="Incendio forestal",
            direccion="Otro sitio", estacion_responsable=self.estacion,
            registrado_por=self.usuario,
        )
        desplegar_unidad(otra, unidad, self.usuario)

        respuesta = self.guardar_con_recurso(formulario, unidad)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            DespliegueUnidad.objects.filter(emergencia=self.emergencia).count(), 0
        )
        self.assertEqual(
            DespliegueUnidad.objects.filter(emergencia=otra, unidad=unidad).count(), 1
        )

class CuadriculaSCI211Tests(SCI211Tests):
    """Autocompletado del recurso y alta de filas sin recargar."""

    def abrir_editor(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        self.crear_recurso_verificado(codigo="REC-CUAD-01")
        self.client.force_login(self.usuario)
        return self.client.get(reverse("emergencias:sci211_editar", args=[formulario.pk]))

    def test_cada_opcion_lleva_los_datos_del_recurso(self):
        respuesta = self.abrir_editor()
        self.assertContains(respuesta, 'data-clase="Vehículos SCI prueba"')
        self.assertContains(respuesta, 'data-tipo="Autobomba SCI prueba"')
        self.assertContains(respuesta, 'data-matricula="REC-CUAD-01"')

    def test_los_campos_derivados_estan_marcados_para_el_guion(self):
        respuesta = self.abrir_editor()
        for marca in ("clase", "tipo", "institucion", "matricula"):
            self.assertContains(respuesta, f'data-derivado="{marca}"')

    def test_el_editor_ofrece_agregar_otro_recurso(self):
        respuesta = self.abrir_editor()
        self.assertContains(respuesta, "data-add-resource")
        self.assertContains(respuesta, "data-resource-template")
        self.assertContains(respuesta, "__prefix__")
        self.assertContains(respuesta, "emergencias/js/sci211_recursos.js")

class ConUnidadDesplegable:
    """Aporta una unidad despachable sin arrastrar las pruebas de otra clase."""

    def crear_unidad_desplegable(self, codigo="AMB-FIN-01"):
        categoria, _ = CategoriaRecurso.objects.get_or_create(
            codigo="CAT-FIN", defaults={"nombre": "Vehículos"}
        )
        tipo, _ = TipoRecurso.objects.get_or_create(
            categoria=categoria, codigo="TIP-FIN",
            defaults={"nombre": "Ambulancia tipo II", "es_unidad_desplegable": True},
        )
        return Recurso.objects.create(
            estacion=self.estacion, tipo=tipo, codigo_interno=codigo,
            nombre="Ambulancia", estado_operativo=Recurso.EstadoOperativo.OPERATIVO,
            disponibilidad=Recurso.Disponibilidad.DISPONIBLE,
            fecha_confirmacion_disponibilidad=timezone.now(),
        )


class DespachoAlFinalizarTests(ConUnidadDesplegable, SCI211Tests):
    """Finalizar también despacha: se llega aquí sin pasar por el editor."""

    def test_finalizar_despacha_la_unidad_anotada(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario(completo=False)
        unidad = self.crear_unidad_desplegable()
        formulario.registros.create(
            orden=1, solicitado_por="CI", fecha_hora_solicitud=self.emergencia.fecha_reporte,
            recurso_inventario=unidad, clase_recurso="Vehículos",
            institucion_procedencia="Bomberos", matricula_identificacion=unidad.codigo_interno,
            numero_personas=2, estado_recurso="disponible",
        )
        self.client.force_login(self.usuario)
        self.client.post(reverse("emergencias:sci211_finalizar", args=[formulario.pk]))

        self.assertTrue(
            DespliegueUnidad.objects.filter(
                emergencia=self.emergencia, unidad=unidad
            ).exists()
        )

    def test_el_editor_avisa_cuando_no_hay_recursos_que_ofrecer(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:sci211_editar", args=[formulario.pk]))
        self.assertContains(respuesta, "No hay recursos que ofrecer")

    def test_con_recursos_disponibles_no_aparece_el_aviso(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        self.crear_unidad_desplegable(codigo="AMB-FIN-02")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:sci211_editar", args=[formulario.pk]))
        self.assertNotContains(respuesta, "No hay recursos que ofrecer")


class InventarioSinConfirmarTests(ConUnidadDesplegable, SCI211Tests):
    """El inventario recién cargado nace sin confirmar y debe seguir sirviendo."""

    def unidad_sin_confirmar(self, codigo="AMB-NUEVA"):
        unidad = self.crear_unidad_desplegable(codigo)
        Recurso.objects.filter(pk=unidad.pk).update(
            fecha_confirmacion_disponibilidad=None
        )
        unidad.refresh_from_db()
        return unidad

    def test_la_lista_ofrece_la_unidad_aunque_no_este_confirmada(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        unidad = self.unidad_sin_confirmar()
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:sci211_editar", args=[formulario.pk]))
        campo = respuesta.context["registros"].forms[0].fields["recurso_inventario"]
        self.assertIn(unidad, campo.queryset)

    def test_la_etiqueta_advierte_que_falta_confirmar(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        self.unidad_sin_confirmar()
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:sci211_editar", args=[formulario.pk]))
        self.assertContains(respuesta, "disponibilidad sin confirmar hoy")

    def test_una_unidad_sin_confirmar_se_despacha_igual(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario(completo=False)
        unidad = self.unidad_sin_confirmar()
        formulario.registros.create(
            orden=1, solicitado_por="CI", fecha_hora_solicitud=self.emergencia.fecha_reporte,
            recurso_inventario=unidad, clase_recurso="Vehículos",
            institucion_procedencia="Bomberos", matricula_identificacion=unidad.codigo_interno,
            numero_personas=2, estado_recurso="disponible",
        )
        despachadas, avisos = desplegar_recursos_del_sci211(formulario, self.usuario)
        self.assertEqual(despachadas, 1)
        self.assertEqual(avisos, [])

    def test_un_recurso_escrito_a_mano_avisa_que_no_saldra(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario(completo=False)
        formulario.registros.create(
            orden=1, solicitado_por="CI", fecha_hora_solicitud=self.emergencia.fecha_reporte,
            clase_recurso="Vehículos", tipo_recurso="Ambulancia",
            institucion_procedencia="Bomberos", matricula_identificacion="ESCRITA-A-MANO",
            numero_personas=2, estado_recurso="disponible",
        )
        despachadas, avisos = desplegar_recursos_del_sci211(formulario, self.usuario)
        self.assertEqual(despachadas, 0)
        self.assertEqual(len(avisos), 1)
        self.assertIn("no generan despliegue", avisos[0])

    def test_sin_recursos_a_mano_no_hay_aviso(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario(completo=False)
        formulario.registros.create(
            orden=1, solicitado_por="CI", fecha_hora_solicitud=self.emergencia.fecha_reporte,
            recurso_inventario=self.crear_unidad_desplegable("AMB-LIMPIA"),
            clase_recurso="Vehículos", institucion_procedencia="Bomberos",
            matricula_identificacion="AMB-LIMPIA", numero_personas=2,
            estado_recurso="disponible",
        )
        _, avisos = desplegar_recursos_del_sci211(formulario, self.usuario)
        self.assertEqual(avisos, [])


class ListaCompletaDeRecursosTests(ConUnidadDesplegable, SCI211Tests):
    """Nada desaparece de la lista: lo que no puede salir se ve y se explica."""

    def unidad_ocupada(self, codigo="AMB-OCUPADA"):
        unidad = self.crear_unidad_desplegable(codigo)
        Recurso.objects.filter(pk=unidad.pk).update(
            disponibilidad=Recurso.Disponibilidad.ASIGNADO
        )
        unidad.refresh_from_db()
        return unidad

    def abrir(self, formulario):
        self.client.force_login(self.usuario)
        return self.client.get(reverse("emergencias:sci211_editar", args=[formulario.pk]))

    def test_una_unidad_asignada_sigue_en_la_lista(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        unidad = self.unidad_ocupada()
        campo = self.abrir(formulario).context["registros"].forms[0].fields["recurso_inventario"]
        self.assertIn(unidad, campo.queryset)

    def test_la_etiqueta_dice_por_que_no_puede_salir(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        self.unidad_ocupada()
        self.assertContains(self.abrir(formulario), "ya asignada a otra emergencia")

    def test_la_opcion_bloqueada_no_se_puede_elegir(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        unidad = self.unidad_ocupada()
        marca = f'<option value="{unidad.pk}"'
        cuerpo = self.abrir(formulario).content.decode()
        opcion = cuerpo[cuerpo.index(marca):cuerpo.index(marca) + 400]
        self.assertIn("disabled", opcion.split("</option>")[0])

    def test_el_servidor_rechaza_una_unidad_ocupada(self):
        unidad = self.unidad_ocupada()
        formulario = RegistroRecursoSCI211Form(
            data={
                "recurso_inventario": unidad.pk, "solicitado_por": "CI",
                "fecha_hora_solicitud": "2026-01-01T10:00", "numero_personas": "2",
                "estado_recurso": "disponible", "asignado_a": "Zona de operaciones",
            },
            usuario=self.usuario,
        )
        self.assertFalse(formulario.is_valid())
        self.assertIn("recurso_inventario", formulario.errors)

    def test_una_unidad_libre_se_acepta(self):
        unidad = self.crear_unidad_desplegable("AMB-LIBRE")
        formulario = RegistroRecursoSCI211Form(
            data={
                "recurso_inventario": unidad.pk, "solicitado_por": "CI",
                "fecha_hora_solicitud": "2026-01-01T10:00", "numero_personas": "2",
                "estado_recurso": "disponible", "asignado_a": "Zona de operaciones",
            },
            usuario=self.usuario,
        )
        self.assertTrue(formulario.is_valid(), formulario.errors)

    def test_el_recurso_ya_guardado_se_conserva_aunque_quede_ocupado(self):
        self.finalizar_anteriores("211")
        contenedor = self.crear_formulario(completo=False)
        unidad = self.crear_unidad_desplegable("AMB-GUARDADA")
        registro = contenedor.registros.create(
            orden=1, solicitado_por="CI",
            fecha_hora_solicitud=self.emergencia.fecha_reporte,
            recurso_inventario=unidad, clase_recurso="Vehículos",
            institucion_procedencia="Bomberos",
            matricula_identificacion=unidad.codigo_interno,
            numero_personas=2, estado_recurso="disponible",
        )
        Recurso.objects.filter(pk=unidad.pk).update(
            disponibilidad=Recurso.Disponibilidad.ASIGNADO
        )
        formulario = RegistroRecursoSCI211Form(
            data={
                "recurso_inventario": unidad.pk, "solicitado_por": "CI",
                "fecha_hora_solicitud": "2026-01-01T10:00", "numero_personas": "2",
                "estado_recurso": "disponible", "asignado_a": "Zona de operaciones",
            },
            instance=registro, usuario=self.usuario,
        )
        self.assertTrue(formulario.is_valid(), formulario.errors)


class TarjetaDeRecursoTests(ConUnidadDesplegable, SCI211Tests):
    """El editor pliega cada recurso y ya no pregunta su disponibilidad."""

    def abrir(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        self.client.force_login(self.usuario)
        return self.client.get(reverse("emergencias:sci211_editar", args=[formulario.pk]))

    def test_el_editor_ya_no_pregunta_el_estado_del_recurso(self):
        respuesta = self.abrir()
        campos = respuesta.context["registros"].forms[0].fields
        self.assertNotIn("estado_recurso", campos)

    def test_ofrece_guardar_editar_y_eliminar_por_recurso(self):
        respuesta = self.abrir()
        for marca in ("data-resource-save", "data-resource-edit", "data-resource-delete"):
            self.assertContains(respuesta, marca)

    def test_la_casilla_de_borrado_sigue_existiendo_oculta(self):
        respuesta = self.abrir()
        self.assertContains(respuesta, "-DELETE")
        self.assertContains(respuesta, "field--hidden")

    def test_se_guarda_sin_enviar_el_estado_del_recurso(self):
        self.finalizar_anteriores("211")
        contenedor = self.crear_formulario(completo=False)
        unidad = self.crear_unidad_desplegable("AMB-TARJETA")
        formulario = RegistroRecursoSCI211Form(
            data={
                "recurso_inventario": unidad.pk, "solicitado_por": "CI",
                "fecha_hora_solicitud": "2026-01-01T10:00", "numero_personas": "2",
                "asignado_a": "Zona de operaciones",
            },
            usuario=self.usuario,
        )
        self.assertTrue(formulario.is_valid(), formulario.errors)
        registro = formulario.save(commit=False)
        registro.formulario = contenedor
        registro.orden = 1
        registro.save()
        self.assertEqual(
            registro.estado_recurso, RegistroRecursoSCI211.EstadoRecurso.DISPONIBLE
        )


class AccionUnicaDelPanelSCITests(ConUnidadDesplegable, SCI211Tests):
    """El botón de llenar vive en un solo sitio: el aviso del paso siguiente."""

    def detalle(self):
        self.client.force_login(self.usuario)
        return self.client.get(reverse("emergencias:detalle", args=[self.emergencia.pk]))

    def test_el_encabezado_no_repite_el_boton_del_paso_siguiente(self):
        respuesta = self.detalle()
        self.assertContains(respuesta, "Siguiente: SCI-201")
        # Un solo llamado a la acción en todo el panel.
        self.assertEqual(respuesta.content.decode().count("sci-next-step__cta"), 1)
        self.assertNotContains(respuesta, "sci-panel-action--primary")

    def test_con_todo_finalizado_no_queda_ninguna_accion_de_llenado(self):
        # El ayudante cierra lo anterior al código indicado, así que el último
        # de la lista hay que cerrarlo aparte.
        self.finalizar_anteriores("222")
        ultimo = FormularioSCI.objects.create(
            emergencia=self.emergencia, codigo_sci="222",
            datos={"preparado": True}, creado_por=self.usuario,
            modificado_por=self.usuario,
            estado=FormularioSCI.Estado.FINALIZADO,
            finalizado_por=self.usuario, fecha_finalizacion=timezone.now(),
        )
        self.assertEqual(ultimo.estado, FormularioSCI.Estado.FINALIZADO)
        respuesta = self.detalle()
        # Con los once genéricos cerrados no queda nada que anunciar: el
        # SCI-211 sigue abierto —lo estará hasta que la emergencia termine—
        # pero un registro en uso no es un paso pendiente.
        self.assertNotContains(respuesta, "sci-next-step__cta")
        self.assertContains(respuesta, "Registro abierto")
        self.assertContains(respuesta, "Formularios disponibles para imprimir")


class SelectDeOpcionesSCITests(SCI211Tests):
    """Un desplegable de opciones cortas debe caber en su columna."""

    def editor_207(self):
        self.finalizar_anteriores("207")
        self.client.force_login(self.usuario)
        return self.client.get(
            reverse("emergencias:sci_editar", args=["207", self.emergencia.pk])
        )

    def test_el_select_de_sexo_lleva_su_propia_clase(self):
        respuesta = self.editor_207()
        self.assertContains(respuesta, 'class="sci-tabla__opcion"')

    def test_la_clase_se_libera_del_ancho_minimo_del_selector_de_recursos(self):
        hoja = (
            Path(settings.BASE_DIR)
            / "static" / "emergencias" / "css" / "sci_editor.css"
        ).read_text(encoding="utf-8")
        bloque = hoja[hoja.index("select.sci-tabla__opcion"):]
        self.assertIn("min-width: 0", bloque[:300])

    def test_el_selector_de_recursos_se_recorta_en_vez_de_desbordarse(self):
        """El SCI-202 pone dos columnas de recursos al 12 %: pedir 10rem cada
        una las sacaba encima de «Asignación / Ubicación»."""
        hoja = (
            Path(settings.BASE_DIR)
            / "static" / "emergencias" / "css" / "sci_editor.css"
        ).read_text(encoding="utf-8")
        self.assertNotIn("min-width:10rem", hoja)
        self.assertIn("text-overflow:ellipsis", hoja)

    def test_el_recurso_elegido_se_lee_entero_al_pasar_el_raton(self):
        """Recortado con puntos suspensivos, el título es la única forma de
        leer la etiqueta completa sin abrir el desplegable."""
        self.finalizar_anteriores("205")
        etiqueta = "RADIO-SCI-01 - Autobomba verificada (Estación Norte)"
        FormularioSCI.objects.create(
            emergencia=self.emergencia, codigo_sci="205",
            datos={"canales": [{"sistema": etiqueta, "canal": "Canal 1"}]},
            creado_por=self.usuario, modificado_por=self.usuario,
        )
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci_editar", args=["205", self.emergencia.pk])
        )
        self.assertContains(respuesta, f'title="{etiqueta}"')


class AnchosDeLaCuadriculaSCITests(TestCase):
    """Ningún control puede exigir más ancho del que su columna declara.

    Las anchuras las fija el formulario oficial y hay columnas del 7 %. Un
    «min-width» en píxeles o en «rem» las ignora y el control se desborda
    sobre las vecinas, como ocurrió en el SCI-202 y en el SCI-207.
    """

    def hoja(self):
        return (
            Path(settings.BASE_DIR)
            / "static" / "emergencias" / "css" / "sci_editor.css"
        ).read_text(encoding="utf-8")

    def test_ningun_control_de_la_cuadricula_exige_ancho_minimo(self):
        hoja = self.hoja()
        anchos = re.findall(r"\.sci-tabla[^{}]*\{[^{}]*?min-width:\s*([^;}]+)", hoja)
        self.assertTrue(anchos, "Se esperaba al menos una regla de min-width.")
        for ancho in anchos:
            self.assertEqual(
                ancho.strip(), "0",
                f"La cuadrícula declara min-width: {ancho.strip()}; "
                "una columna estrecha del formulario oficial no lo soportaría.",
            )

    def test_las_columnas_estrechas_siguen_existiendo_en_los_esquemas(self):
        """Si esto deja de encontrarlas, la regla de arriba ya no hace falta."""
        estrechas = [
            (codigo, columna["nombre"], columna["ancho"])
            for codigo, esquema in ESQUEMAS_SCI.items()
            for seccion in esquema["secciones"]
            if seccion.get("tipo") == TABLA
            for columna in seccion["columnas"]
            if (columna.get("recurso_inventario") or columna.get("tipo") != TEXTO)
            and columna.get("ancho", "").endswith("%")
            and float(columna["ancho"][:-1]) < 13
        ]
        self.assertTrue(estrechas, "Ya no hay columnas estrechas con control.")


class DespachoSinEsperarTurnoTests(SCI211Tests):
    """El SCI-211 se abre desde el primer momento; los demás conservan su orden."""

    def test_se_entra_al_211_sin_haber_llenado_nada(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.post(
            reverse("emergencias:sci211_crear", args=[self.emergencia.pk])
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(
            FormularioSCI211.objects.filter(emergencia=self.emergencia).exists()
        )

    def test_el_202_sigue_esperando_a_los_anteriores(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci_editar", args=["202", self.emergencia.pk]),
            follow=True,
        )
        self.assertContains(respuesta, "Finalice primero el formulario")

    def test_cerrar_el_211_solo_no_abre_el_202(self):
        formulario = self.crear_formulario()
        FormularioSCI211.objects.filter(pk=formulario.pk).update(
            estado=FormularioSCI211.Estado.FINALIZADO,
            finalizado_por=self.usuario, fecha_finalizacion=timezone.now(),
        )
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci_editar", args=["202", self.emergencia.pk]),
            follow=True,
        )
        self.assertContains(respuesta, "Finalice primero el formulario")

    def test_el_211_no_muestra_candado_en_la_ficha(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:detalle", args=[self.emergencia.pk])
        )
        tarjeta = next(
            item for item in respuesta.context["catalogo_sci"]
            if item["codigo"] == "211"
        )
        self.assertFalse(tarjeta["bloqueado"])


class DesplegableAgrupadoTests(ConUnidadDesplegable, SCI211Tests):
    """El inventario se ofrece por encabezados, con las unidades delante."""

    def abrir(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        self.client.force_login(self.usuario)
        return self.client.get(reverse("emergencias:sci211_editar", args=[formulario.pk]))

    def test_el_desplegable_trae_encabezados(self):
        self.crear_unidad_desplegable("AB-GRUPO-01")
        respuesta = self.abrir()
        self.assertContains(respuesta, '<optgroup label="Unidades desplegables">')

    def test_las_unidades_van_antes_que_el_resto(self):
        self.crear_unidad_desplegable("AB-GRUPO-02")
        cuerpo = self.abrir().content.decode()
        posicion_unidades = cuerpo.index('label="Unidades desplegables"')
        # El equipo de radio de la base de pruebas cae en su propia categoría.
        otros = [
            cuerpo.index(f'label="{nombre}"')
            for nombre in ("Comunicaciones SCI",) if f'label="{nombre}"' in cuerpo
        ]
        for posicion in otros:
            self.assertLess(posicion_unidades, posicion)

    def test_la_opcion_conserva_sus_datos_para_el_autocompletado(self):
        unidad = self.crear_unidad_desplegable("AB-GRUPO-03")
        respuesta = self.abrir()
        # Agrupar no puede romper los atributos que rellenan clase y tipo.
        self.assertContains(respuesta, f'data-matricula="{unidad.codigo_interno}"')
        self.assertContains(respuesta, 'data-desplegable="1"')

    def test_la_etiqueta_no_cambia_al_agrupar(self):
        """Es el valor que guardan los formularios SCI genéricos: si cambia,
        los ya llenos dejan de reconocer su recurso."""
        unidad = self.crear_unidad_desplegable("AB-GRUPO-04")
        respuesta = self.abrir()
        self.assertContains(
            respuesta,
            f"{unidad.codigo_interno} - {unidad.nombre} ({self.estacion.nombre})",
        )


class ImprimibleDel211Tests(SCI211Tests):
    """Desde la vista imprimible se vuelve al editor si aún es borrador."""

    def imprimir(self, formulario):
        self.client.force_login(self.usuario)
        return self.client.get(
            reverse("emergencias:sci211_imprimir", args=[formulario.pk])
        )

    def test_un_borrador_ofrece_volver_a_editar(self):
        formulario = self.crear_formulario(completo=False)
        respuesta = self.imprimir(formulario)
        self.assertContains(respuesta, "Editar")
        self.assertContains(
            respuesta, reverse("emergencias:sci211_editar", args=[formulario.pk])
        )

    def test_un_formulario_finalizado_no_lo_ofrece(self):
        formulario = self.crear_formulario()
        self.cerrar_el_211(formulario)
        respuesta = self.imprimir(formulario)
        self.assertNotContains(
            respuesta, reverse("emergencias:sci211_editar", args=[formulario.pk])
        )

    def test_quien_no_puede_editar_tampoco_lo_ve(self):
        formulario = self.crear_formulario(completo=False)
        consulta = get_user_model().objects.create_user(
            username="consulta-imprimir", cedula="1700000001", password="clave",
            estacion=self.estacion,
        )
        consulta.groups.add(Group.objects.get(name="Operador de consulta"))
        self.client.force_login(consulta)
        respuesta = self.client.get(
            reverse("emergencias:sci211_imprimir", args=[formulario.pk])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(
            respuesta, reverse("emergencias:sci211_editar", args=[formulario.pk])
        )


class BotonGuardarDelRecursoTests(ConUnidadDesplegable, SCI211Tests):
    """El botón de cada tarjeta guarda de verdad, no solo minimiza."""

    def datos_con_recurso(self, formulario, unidad, accion):
        datos = self._datos_edicion(formulario)
        datos["registros-0-recurso_inventario"] = str(unidad.pk)
        datos["accion"] = accion
        return datos

    def test_el_boton_de_la_tarjeta_persiste_el_recurso(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario(completo=False)
        unidad = self.crear_unidad_desplegable("AB-GUARDA-01")
        self.client.force_login(self.usuario)

        self.client.post(
            reverse("emergencias:sci211_editar", args=[formulario.pk]),
            self.datos_con_recurso(formulario, unidad, "guardar_recurso"),
        )
        registro = formulario.registros.first()
        self.assertIsNotNone(registro)
        self.assertEqual(registro.recurso_inventario, unidad)

    def test_guardar_un_recurso_devuelve_al_editor_y_no_a_la_ficha(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario(completo=False)
        unidad = self.crear_unidad_desplegable("AB-GUARDA-02")
        self.client.force_login(self.usuario)

        respuesta = self.client.post(
            reverse("emergencias:sci211_editar", args=[formulario.pk]),
            self.datos_con_recurso(formulario, unidad, "guardar_recurso"),
        )
        self.assertRedirects(
            respuesta,
            reverse("emergencias:sci211_editar", args=[formulario.pk]) + "?plegar=1",
        )

    def test_al_volver_se_pide_plegar_lo_ya_anotado(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario(completo=False)
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci211_editar", args=[formulario.pk]) + "?plegar=1"
        )
        self.assertContains(respuesta, "data-plegar-guardados")

    def test_sin_ese_parametro_las_tarjetas_salen_abiertas(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario(completo=False)
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci211_editar", args=[formulario.pk])
        )
        self.assertNotContains(respuesta, "data-plegar-guardados")

    def test_el_boton_envia_el_formulario(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario(completo=False)
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci211_editar", args=[formulario.pk])
        )
        # Si vuelve a ser «type=button» deja de guardar y solo minimiza.
        self.assertContains(respuesta, 'type="submit" name="accion" value="guardar_recurso"')

    def test_el_boton_de_editar_puede_ocultarse(self):
        hoja = (
            Path(settings.BASE_DIR)
            / "static" / "emergencias" / "css" / "sci211.css"
        ).read_text(encoding="utf-8")
        # «display: inline-flex» vence al atributo hidden si no se contempla.
        self.assertIn(".resource-action[hidden]", hoja)


class RecursosEnElLugarDel202Tests(ConUnidadDesplegable, SCI211Tests):
    """«En el lugar» solo ofrece lo que el SCI-211 registró en la emergencia."""

    def anotar_en_el_211(self, unidad):
        formulario, _ = FormularioSCI211.objects.get_or_create(
            emergencia=self.emergencia,
            defaults={
                "codigo": f"SCI-211-{self.emergencia.pk}",
                "punto_registro": "Puesto de Comando",
                "registrador_1": self.usuario.username,
                "creado_por": self.usuario, "modificado_por": self.usuario,
            },
        )
        formulario.registros.create(
            orden=1, solicitado_por="CI",
            fecha_hora_solicitud=self.emergencia.fecha_reporte,
            recurso_inventario=unidad, clase_recurso="Vehículos",
            institucion_procedencia="Bomberos",
            matricula_identificacion=unidad.codigo_interno,
            numero_personas=2, asignado_a="Zona de operaciones",
        )
        return formulario

    def abrir_202(self):
        self.finalizar_anteriores("202")
        self.client.force_login(self.usuario)
        return self.client.get(
            reverse("emergencias:sci_editar", args=["202", self.emergencia.pk])
        )

    def test_sin_nada_registrado_lo_dice(self):
        respuesta = self.abrir_202()
        self.assertEqual(respuesta.context["recursos_del_lugar"], [])
        self.assertContains(respuesta, "Ningún recurso registrado aún en el SCI-211")

    def test_solo_aparece_lo_anotado_en_el_211(self):
        en_escena = self.crear_unidad_desplegable("AB-LUGAR-01")
        self.crear_unidad_desplegable("AB-PATIO-01")
        self.anotar_en_el_211(en_escena)

        respuesta = self.abrir_202()
        codigos = {r.codigo_interno for r in respuesta.context["recursos_del_lugar"]}
        self.assertEqual(codigos, {"AB-LUGAR-01"})
        # El inventario completo sigue disponible para «por solicitar».
        del_inventario = {
            r.codigo_interno for r in respuesta.context["recursos_disponibles"]
        }
        self.assertIn("AB-PATIO-01", del_inventario)

    def test_el_servidor_rechaza_uno_que_no_esta_en_la_escena(self):
        en_escena = self.crear_unidad_desplegable("AB-LUGAR-02")
        en_patio = self.crear_unidad_desplegable("AB-PATIO-02")
        self.anotar_en_el_211(en_escena)
        self.finalizar_anteriores("202")
        self.client.force_login(self.usuario)

        respuesta = self.client.post(
            reverse("emergencias:sci_editar", args=["202", self.emergencia.pk]),
            {"plan-0-recursos_lugar": str(en_patio.pk), "preparado_por": "CI"},
            follow=True,
        )
        self.assertContains(respuesta, "solo admite recursos que el SCI-211")

    def test_el_servidor_acepta_uno_que_si_esta_en_la_escena(self):
        en_escena = self.crear_unidad_desplegable("AB-LUGAR-03")
        self.anotar_en_el_211(en_escena)
        self.finalizar_anteriores("202")
        self.client.force_login(self.usuario)

        self.client.post(
            reverse("emergencias:sci_editar", args=["202", self.emergencia.pk]),
            {
                "plan-0-estrategia": "Controlar el frente",
                "plan-0-recursos_lugar": str(en_escena.pk),
                "preparado_por": "CI",
            },
        )
        formulario = FormularioSCI.objects.get(
            emergencia=self.emergencia, codigo_sci="202"
        )
        self.assertEqual(
            formulario.datos["plan"][0]["recursos_lugar"],
            etiqueta_de_recurso(en_escena),
        )

    def test_por_solicitar_sigue_ofreciendo_el_inventario(self):
        self.crear_unidad_desplegable("AB-PATIO-03")
        self.finalizar_anteriores("202")
        self.client.force_login(self.usuario)
        respuesta = self.client.post(
            reverse("emergencias:sci_editar", args=["202", self.emergencia.pk]),
            {
                "plan-0-recursos_solicitar": str(
                    Recurso.objects.get(codigo_interno="AB-PATIO-03").pk
                ),
                "preparado_por": "CI",
            },
            follow=True,
        )
        self.assertNotContains(respuesta, "solo admite recursos que el SCI-211")


class RegistroAbiertoDuranteLaEmergenciaTests(ConUnidadDesplegable, SCI211Tests):
    """El SCI-211 es una bitácora: vive mientras la emergencia esté abierta."""

    def test_no_se_cierra_con_la_emergencia_en_marcha(self):
        formulario = self.crear_formulario()
        with self.assertRaises(ValidationError) as capturado:
            finalizar_sci211(formulario, self.usuario)
        self.assertIn("cuando la emergencia termina", str(capturado.exception))
        formulario.refresh_from_db()
        self.assertTrue(formulario.es_editable)

    def test_se_cierra_una_vez_terminada(self):
        formulario = self.crear_formulario()
        cerrado = self.cerrar_el_211(formulario)
        self.assertEqual(cerrado.estado, FormularioSCI211.Estado.FINALIZADO)

    def test_con_recursos_anotados_desbloquea_los_siguientes(self):
        """Sin esto, exigirle estar cerrado dejaría el 202 bloqueado para
        siempre: el 211 no puede cerrarse hasta que la emergencia termine."""
        self.finalizar_anteriores("211")
        self.crear_formulario(completo=False).registros.create(
            orden=1, solicitado_por="CI",
            fecha_hora_solicitud=self.emergencia.fecha_reporte,
            recurso_inventario=self.crear_unidad_desplegable("AB-BITACORA-01"),
            clase_recurso="Vehículos", institucion_procedencia="Bomberos",
            matricula_identificacion="AB-BITACORA-01", numero_personas=2,
            asignado_a="Zona de operaciones",
        )
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci_editar", args=["202", self.emergencia.pk])
        )
        self.assertEqual(respuesta.status_code, 200)

    def test_un_211_vacio_no_desbloquea_nada(self):
        self.finalizar_anteriores("211")
        self.crear_formulario(completo=False)
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci_editar", args=["202", self.emergencia.pk]),
            follow=True,
        )
        self.assertContains(respuesta, "Finalice primero el formulario")

    def test_la_ficha_lo_llama_registro_abierto(self):
        self.finalizar_anteriores("211")
        self.crear_formulario(completo=False).registros.create(
            orden=1, solicitado_por="CI",
            fecha_hora_solicitud=self.emergencia.fecha_reporte,
            recurso_inventario=self.crear_unidad_desplegable("AB-BITACORA-02"),
            clase_recurso="Vehículos", institucion_procedencia="Bomberos",
            matricula_identificacion="AB-BITACORA-02", numero_personas=2,
            asignado_a="Zona de operaciones",
        )
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:detalle", args=[self.emergencia.pk])
        )
        self.assertContains(respuesta, "Registro abierto")

class SolicitudDel202AlSCI211Tests(ConUnidadDesplegable, SCI211Tests):
    """Lo que el plan de acción solicita queda anotado en el registro."""

    def guardar_202(self, unidad):
        self.finalizar_anteriores("202")
        self.client.force_login(self.usuario)
        return self.client.post(
            reverse("emergencias:sci_editar", args=["202", self.emergencia.pk]),
            {
                "plan-0-estrategia": "Reforzar el ataque",
                "plan-0-recursos_solicitar": str(unidad.pk),
                "preparado_por": "Comandante de Incidente",
            },
            follow=True,
        )

    def test_el_recurso_solicitado_aparece_en_el_211(self):
        unidad = self.crear_unidad_desplegable("AMB-PEDIDA-01")
        self.guardar_202(unidad)
        formulario = FormularioSCI211.objects.get(emergencia=self.emergencia)
        self.assertTrue(
            formulario.registros.filter(recurso_inventario=unidad).exists()
        )

    def test_queda_constancia_de_quien_y_cuando_lo_pidio(self):
        unidad = self.crear_unidad_desplegable("AMB-PEDIDA-02")
        self.guardar_202(unidad)
        registro = FormularioSCI211.objects.get(
            emergencia=self.emergencia
        ).registros.get(recurso_inventario=unidad)
        self.assertEqual(registro.solicitado_por, self.usuario.username)
        self.assertIsNotNone(registro.fecha_hora_solicitud)

    def test_la_unidad_solicitada_se_despacha(self):
        unidad = self.crear_unidad_desplegable("AMB-PEDIDA-03")
        self.guardar_202(unidad)
        self.assertTrue(
            DespliegueUnidad.objects.filter(
                emergencia=self.emergencia, unidad=unidad
            ).exists()
        )

    def test_no_se_duplica_al_volver_a_guardar(self):
        unidad = self.crear_unidad_desplegable("AMB-PEDIDA-04")
        self.guardar_202(unidad)
        self.guardar_202(unidad)
        formulario = FormularioSCI211.objects.get(emergencia=self.emergencia)
        self.assertEqual(
            formulario.registros.filter(recurso_inventario=unidad).count(), 1
        )

    def test_lo_anotado_como_en_el_lugar_no_se_vuelve_a_solicitar(self):
        """«En el lugar» ya está en la escena: trasladarlo seria pedir otra vez
        lo que ya llegó."""
        unidad = self.crear_unidad_desplegable("AMB-PEDIDA-05")
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario(completo=False)
        formulario.registros.create(
            orden=1, solicitado_por="CI",
            fecha_hora_solicitud=self.emergencia.fecha_reporte,
            recurso_inventario=unidad, clase_recurso="Vehículos",
            institucion_procedencia="Bomberos",
            matricula_identificacion=unidad.codigo_interno,
            numero_personas=2, asignado_a="Zona de operaciones",
        )
        self.finalizar_anteriores("202")
        self.client.force_login(self.usuario)
        self.client.post(
            reverse("emergencias:sci_editar", args=["202", self.emergencia.pk]),
            {
                "plan-0-estrategia": "Sostener el ataque",
                "plan-0-recursos_lugar": str(unidad.pk),
                "preparado_por": "CI",
            },
        )
        self.assertEqual(
            formulario.registros.filter(recurso_inventario=unidad).count(), 1
        )


class ColorDelRegistroAbiertoTests(ConUnidadDesplegable, SCI211Tests):
    """Un registro en uso se distingue de uno incompleto, no comparte color."""

    def con_recursos(self):
        self.finalizar_anteriores("211")
        self.crear_formulario(completo=False).registros.create(
            orden=1, solicitado_por="CI",
            fecha_hora_solicitud=self.emergencia.fecha_reporte,
            recurso_inventario=self.crear_unidad_desplegable("AB-COLOR-01"),
            clase_recurso="Vehículos", institucion_procedencia="Bomberos",
            matricula_identificacion="AB-COLOR-01", numero_personas=2,
            asignado_a="Zona de operaciones",
        )
        self.client.force_login(self.usuario)
        return self.client.get(reverse("emergencias:detalle", args=[self.emergencia.pk]))

    def test_el_211_en_uso_tiene_su_propio_estado(self):
        respuesta = self.con_recursos()
        tarjeta = next(
            item for item in respuesta.context["catalogo_sci"]
            if item["codigo"] == "211"
        )
        self.assertEqual(tarjeta["clave_estado"], "open")
        self.assertEqual(tarjeta["etiqueta_estado"], "Registro abierto")

    def test_no_se_pinta_como_incompleto(self):
        respuesta = self.con_recursos()
        self.assertContains(respuesta, "sci-form-tab--open")

    def test_la_leyenda_explica_el_color(self):
        respuesta = self.con_recursos()
        self.assertContains(respuesta, "Registro abierto durante la emergencia")
        self.assertContains(respuesta, "sci-status-dot--open")

    def test_el_estado_existe_en_la_hoja_de_estilos(self):
        hoja = (
            Path(settings.BASE_DIR)
            / "static" / "emergencias" / "css" / "emergencias.css"
        ).read_text(encoding="utf-8")
        self.assertIn(".sci-form-tab--open{", hoja)
        self.assertIn(".sci-status-dot--open{", hoja)

    def test_un_211_vacio_ya_se_pinta_como_bitacora_pero_lo_dice(self):
        """El azul describe qué clase de formulario es, no cuánto lleva
        escrito; la etiqueta avisa de que todavía no tiene anotaciones."""
        self.finalizar_anteriores("211")
        self.crear_formulario(completo=False)
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:detalle", args=[self.emergencia.pk])
        )
        tarjeta = next(
            item for item in respuesta.context["catalogo_sci"]
            if item["codigo"] == "211"
        )
        self.assertEqual(tarjeta["clave_estado"], "open")
        self.assertEqual(tarjeta["etiqueta_estado"], "Registro abierto · sin anotaciones")
        # Vacía sigue siendo el paso pendiente: es lo primero que hay que llenar.
        self.assertFalse(tarjeta["en_curso"])

    def test_el_214_es_azul_desde_antes_de_abrirse(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:detalle", args=[self.emergencia.pk])
        )
        tarjeta = next(
            item for item in respuesta.context["catalogo_sci"]
            if item["codigo"] == "214"
        )
        self.assertEqual(tarjeta["clave_estado"], "open")
        self.assertFalse(tarjeta["bloqueado"])

    def test_los_que_no_son_bitacora_no_se_pintan_de_azul(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:detalle", args=[self.emergencia.pk])
        )
        claves = {
            item["codigo"]: item["clave_estado"]
            for item in respuesta.context["catalogo_sci"]
        }
        self.assertEqual(claves["202"], "pending")
        self.assertEqual(claves["221"], "pending")


class BitacoraDelSCI214Tests(ConUnidadDesplegable, SCI211Tests):
    """El SCI-214 es la bitácora del periodo: se cierra con la emergencia."""

    def escribir_214(self, con_contenido=True):
        return FormularioSCI.objects.create(
            emergencia=self.emergencia, codigo_sci="214",
            datos={"actividades": [{"hora": "10:00", "evento": "Arribo"}]}
            if con_contenido else {},
            creado_por=self.usuario, modificado_por=self.usuario,
        )

    def test_no_se_cierra_con_la_emergencia_en_marcha(self):
        formulario = self.escribir_214()
        with self.assertRaises(ValidationError) as capturado:
            finalizar_sci(formulario, self.usuario)
        self.assertIn("cuando la emergencia termina", str(capturado.exception))

    def test_se_cierra_una_vez_terminada(self):
        formulario = self.escribir_214()
        Emergencia.objects.filter(pk=self.emergencia.pk).update(
            estado=Emergencia.Estado.CERRADA
        )
        cerrado = finalizar_sci(formulario, self.usuario)
        self.assertEqual(cerrado.estado, FormularioSCI.Estado.FINALIZADO)

    def test_en_uso_desbloquea_los_siguientes(self):
        self.finalizar_anteriores("214")
        self.escribir_214()
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci_editar", args=["221", self.emergencia.pk])
        )
        self.assertEqual(respuesta.status_code, 200)

    def test_vacio_no_desbloquea_nada(self):
        self.finalizar_anteriores("214")
        self.escribir_214(con_contenido=False)
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci_editar", args=["221", self.emergencia.pk]),
            follow=True,
        )
        self.assertContains(respuesta, "Finalice primero el formulario")

    def test_la_ficha_lo_pinta_como_registro_abierto(self):
        self.finalizar_anteriores("214")
        self.escribir_214()
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:detalle", args=[self.emergencia.pk])
        )
        tarjeta = next(
            item for item in respuesta.context["catalogo_sci"]
            if item["codigo"] == "214"
        )
        self.assertEqual(tarjeta["clave_estado"], "open")

    def test_el_207_sigue_cerrandose_cuando_se_quiera(self):
        """No es continuo a propósito: una emergencia sin víctimas dejaría su
        registro vacío para siempre, y con él toda la cadena detenida."""
        formulario = FormularioSCI.objects.create(
            emergencia=self.emergencia, codigo_sci="207",
            datos={"pacientes": [{"nombre": "N. N."}]},
            creado_por=self.usuario, modificado_por=self.usuario,
        )
        cerrado = finalizar_sci(formulario, self.usuario)
        self.assertEqual(cerrado.estado, FormularioSCI.Estado.FINALIZADO)


class BitacorasSinEsperarTurnoTests(SCI211Tests):
    """Una bitácora se abre desde el principio o no sirve como bitácora."""

    def test_el_214_se_abre_sin_haber_llenado_nada(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci_editar", args=["214", self.emergencia.pk])
        )
        self.assertEqual(respuesta.status_code, 200)

    def test_el_214_no_muestra_candado(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:detalle", args=[self.emergencia.pk])
        )
        tarjeta = next(
            item for item in respuesta.context["catalogo_sci"]
            if item["codigo"] == "214"
        )
        self.assertFalse(tarjeta["bloqueado"])

    def test_los_que_no_son_bitacora_siguen_esperando(self):
        self.client.force_login(self.usuario)
        for codigo in ("202", "203", "205", "221", "222"):
            respuesta = self.client.get(
                reverse("emergencias:sci_editar", args=[codigo, self.emergencia.pk]),
                follow=True,
            )
            self.assertContains(
                respuesta, "Finalice primero el formulario",
                msg_prefix=f"El SCI-{codigo} no debería abrirse todavía",
            )

    def test_el_221_sigue_necesitando_al_214(self):
        """Eximir a la bitácora de esperar turno no la exime de ser requisito
        de las que vienen detrás."""
        self.finalizar_anteriores("214")
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("emergencias:sci_editar", args=["221", self.emergencia.pk]),
            follow=True,
        )
        self.assertContains(respuesta, "Finalice primero el formulario")


class MenosTecleoTests(ConUnidadDesplegable, SCI211Tests):
    """Lo que se responde siempre igual viene hecho, pero se puede cambiar."""

    def test_el_solicitante_viene_con_el_nombre_de_quien_registra(self):
        formulario = RegistroRecursoSCI211Form(usuario=self.usuario)
        self.assertEqual(
            formulario.fields["solicitado_por"].initial,
            self.usuario.get_full_name() or self.usuario.username,
        )

    def test_la_hora_de_solicitud_viene_puesta(self):
        formulario = RegistroRecursoSCI211Form(usuario=self.usuario)
        self.assertIsNotNone(formulario.fields["fecha_hora_solicitud"].initial)

    def test_una_fila_ya_guardada_conserva_lo_suyo(self):
        self.finalizar_anteriores("211")
        contenedor = self.crear_formulario(completo=False)
        registro = contenedor.registros.create(
            orden=1, solicitado_por="Comandante anterior",
            fecha_hora_solicitud=self.emergencia.fecha_reporte,
            clase_recurso="Vehículos", institucion_procedencia="Bomberos",
            matricula_identificacion="AB-VIEJA", numero_personas=1,
            asignado_a="Zona de operaciones",
        )
        formulario = RegistroRecursoSCI211Form(instance=registro, usuario=self.usuario)
        self.assertIsNone(formulario.fields["solicitado_por"].initial)
        self.assertEqual(formulario["solicitado_por"].value(), "Comandante anterior")

    def test_los_campos_de_fecha_llevan_el_boton_de_ahora(self):
        self.finalizar_anteriores("211")
        formulario = self.crear_formulario()
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("emergencias:sci211_editar", args=[formulario.pk]))
        self.assertContains(respuesta, "emergencias/js/ahora.js")

class PeriodoHeredadoTests(SCI211Tests):
    """El periodo operacional se escribe una vez y se ofrece en los demás."""

    def escribir_periodo_en_el_202(self):
        self.finalizar_anteriores("202")
        FormularioSCI.objects.create(
            emergencia=self.emergencia, codigo_sci="202",
            datos={
                "periodo_numero": "1",
                "periodo_inicio": "2026-09-03T08:00",
                "periodo_fin": "2026-09-03T12:00",
            },
            creado_por=self.usuario, modificado_por=self.usuario,
            estado=FormularioSCI.Estado.FINALIZADO,
            finalizado_por=self.usuario, fecha_finalizacion=timezone.now(),
        )

    def abrir(self, codigo):
        self.client.force_login(self.usuario)
        return self.client.get(
            reverse("emergencias:sci_editar", args=[codigo, self.emergencia.pk])
        )

    def test_el_203_lo_recibe_del_202(self):
        self.escribir_periodo_en_el_202()
        campos = {c["nombre"]: c for c in self.abrir("203").context["campos_periodo"]}
        self.assertEqual(campos["periodo_numero"]["valor"], "1")
        self.assertEqual(campos["periodo_inicio"]["valor"], "2026-09-03T08:00")
        self.assertTrue(campos["periodo_numero"]["heredado"])

    def test_se_avisa_de_que_viene_de_otro_formulario(self):
        self.escribir_periodo_en_el_202()
        self.assertContains(self.abrir("203"), "tomado de otro formulario")

    def test_lo_propio_manda_sobre_lo_heredado(self):
        self.escribir_periodo_en_el_202()
        FormularioSCI.objects.create(
            emergencia=self.emergencia, codigo_sci="203",
            datos={"periodo_numero": "2"},
            creado_por=self.usuario, modificado_por=self.usuario,
        )
        campos = {c["nombre"]: c for c in self.abrir("203").context["campos_periodo"]}
        self.assertEqual(campos["periodo_numero"]["valor"], "2")
        self.assertFalse(campos["periodo_numero"]["heredado"])

    def test_sin_nada_escrito_no_se_inventa_periodo(self):
        self.finalizar_anteriores("202")
        campos = {c["nombre"]: c for c in self.abrir("202").context["campos_periodo"]}
        self.assertEqual(campos["periodo_numero"]["valor"], "")
        self.assertFalse(campos["periodo_numero"]["heredado"])

    def test_la_firma_viene_con_el_nombre_de_quien_entra(self):
        self.finalizar_anteriores("202")
        respuesta = self.abrir("202")
        self.assertEqual(
            respuesta.context["preparado_por_sugerido"],
            self.usuario.get_full_name() or self.usuario.username,
        )
        self.assertContains(respuesta, self.usuario.username)
