"""Ciclo de vida de una cuenta institucional.

Cubre el cambio de clave propio, la obligación de reemplazar la que asignó
otra persona, la edición del perfil y la desactivación.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from instituciones.models import Canton, CuerpoBomberos, Estacion

CLAVE_NUEVA = "Cotopaxi-2026-segura"

class BaseCuentasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="LAT-GC")
        cls.cuerpo = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Bomberos Cuentas",
            sigla="CBC-GC",
            ruc="0596000000201",
            direccion="Centro",
        )
        cls.cuerpo_ajeno = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Bomberos Ajenos Cuentas",
            sigla="CBAC-GC",
            ruc="0596000000202",
            direccion="Sur",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo,
            nombre="Central Cuentas",
            codigo="CC-GC",
            direccion="Centro",
            latitud="-0.930000",
            longitud="-78.610000",
        )
        cls.estacion_ajena = Estacion.objects.create(
            cuerpo_bomberos=cls.cuerpo_ajeno,
            nombre="Central Ajena Cuentas",
            codigo="CAC-GC",
            direccion="Sur",
            latitud="-1.010000",
            longitud="-78.660000",
        )
        cls.operador = cls.crear_cuenta(
            "operador-gc", "0580000001", "Operador de sistemas institucional", cls.estacion
        )
        cls.miembro = cls.crear_cuenta(
            "miembro-gc", "0580000002", "Responsable de estación", cls.estacion
        )
        cls.ajeno = cls.crear_cuenta(
            "ajeno-gc", "0580000003", "Responsable de estación", cls.estacion_ajena
        )

    @classmethod
    def crear_cuenta(cls, username, cedula, grupo, estacion, **extra):
        usuario = get_user_model().objects.create_user(
            username=username, cedula=cedula, password="clave-inicial", estacion=estacion,
            **extra,
        )
        usuario.groups.add(Group.objects.get(name=grupo))
        return usuario

class ClavePropiaTests(BaseCuentasTests):
    def test_una_cuenta_creada_desde_codigo_no_arrastra_la_obligacion(self):
        """El valor por omisión es falso: solo se activa donde alguien la asigna."""
        self.assertFalse(self.miembro.debe_cambiar_clave)

    def test_el_usuario_cambia_su_propia_clave_y_conserva_la_sesion(self):
        self.client.force_login(self.miembro)
        respuesta = self.client.post(reverse("usuarios:cambiar_clave"), {
            "old_password": "clave-inicial",
            "new_password1": CLAVE_NUEVA,
            "new_password2": CLAVE_NUEVA,
        })
        self.assertRedirects(respuesta, reverse("emergencias:lista"))
        self.miembro.refresh_from_db()
        self.assertTrue(self.miembro.check_password(CLAVE_NUEVA))
        self.assertIn("_auth_user_id", self.client.session)

    def test_la_clave_actual_incorrecta_no_cambia_nada(self):
        self.client.force_login(self.miembro)
        respuesta = self.client.post(reverse("usuarios:cambiar_clave"), {
            "old_password": "equivocada",
            "new_password1": CLAVE_NUEVA,
            "new_password2": CLAVE_NUEVA,
        })
        self.assertEqual(respuesta.status_code, 200)
        self.miembro.refresh_from_db()
        self.assertTrue(self.miembro.check_password("clave-inicial"))

    def test_el_menu_ofrece_el_cambio_de_clave(self):
        self.client.force_login(self.miembro)
        respuesta = self.client.get(reverse("emergencias:lista"))
        self.assertContains(respuesta, reverse("usuarios:cambiar_clave"))
        self.assertContains(respuesta, "Cambiar contraseña")

class ObligacionDeCambioTests(BaseCuentasTests):
    def setUp(self):
        self.pendiente = self.crear_cuenta(
            "pendiente-gc", "0580000010", "Responsable de estación", self.estacion,
            debe_cambiar_clave=True,
        )
        self.client.force_login(self.pendiente)

    def test_cualquier_pagina_devuelve_al_cambio_de_clave(self):
        for nombre in ("emergencias:lista", "inventario:lista", "dashboard:principal"):
            respuesta = self.client.get(reverse(nombre))
            self.assertRedirects(respuesta, reverse("usuarios:cambiar_clave"))

    def test_el_formulario_de_cambio_si_responde(self):
        respuesta = self.client.get(reverse("usuarios:cambiar_clave"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Debe cambiar su contraseña")
        self.assertNotContains(respuesta, "Cancelar")

    def test_cerrar_sesion_sigue_disponible(self):
        respuesta = self.client.post(reverse("usuarios:logout"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_la_pagina_sin_conexion_de_la_pwa_no_queda_bloqueada(self):
        self.assertEqual(self.client.get(reverse("core:sin_conexion")).status_code, 200)
        self.assertEqual(self.client.get(reverse("core:service_worker")).status_code, 200)

    def test_al_cambiarla_se_levanta_la_obligacion(self):
        self.client.post(reverse("usuarios:cambiar_clave"), {
            "old_password": "clave-inicial",
            "new_password1": CLAVE_NUEVA,
            "new_password2": CLAVE_NUEVA,
        })
        self.pendiente.refresh_from_db()
        self.assertFalse(self.pendiente.debe_cambiar_clave)
        self.assertEqual(self.client.get(reverse("emergencias:lista")).status_code, 200)

    def test_una_visita_anonima_no_se_ve_afectada(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("usuarios:login")).status_code, 200)

class CreacionDeCuentasTests(BaseCuentasTests):
    def test_la_cuenta_creada_nace_obligada_a_cambiar_la_clave(self):
        self.client.force_login(self.operador)
        respuesta = self.client.post(reverse("usuarios:crear"), {
            "username": "nueva-gc",
            "first_name": "Ana",
            "last_name": "Pérez",
            "cedula": "0580000020",
            "email": "ana@example.com",
            "telefono": "0999999999",
            "cargo_institucional": "Bombera",
            "estacion": self.estacion.pk,
            "grupo": Group.objects.get(name="Responsable de estación").pk,
            "password1": CLAVE_NUEVA,
            "password2": CLAVE_NUEVA,
        })
        self.assertRedirects(respuesta, reverse("usuarios:lista"))
        creada = get_user_model().objects.get(username="nueva-gc")
        self.assertTrue(creada.debe_cambiar_clave)
        self.assertEqual(list(creada.groups.values_list("name", flat=True)),
                         ["Responsable de estación"])

class EdicionDeCuentasTests(BaseCuentasTests):
    def test_el_operador_corrige_datos_y_rol(self):
        self.client.force_login(self.operador)
        respuesta = self.client.post(reverse("usuarios:editar", args=[self.miembro.pk]), {
            "first_name": "Luis",
            "last_name": "Vaca",
            "cedula": self.miembro.cedula,
            "email": "luis@example.com",
            "telefono": "0988888888",
            "cargo_institucional": "Jefe de guardia",
            "estacion": self.estacion.pk,
            "grupo": Group.objects.get(name="Encargado de inventario").pk,
        })
        self.assertRedirects(respuesta, reverse("usuarios:lista"))
        self.miembro.refresh_from_db()
        self.assertEqual(self.miembro.first_name, "Luis")
        self.assertEqual(self.miembro.cargo_institucional, "Jefe de guardia")
        self.assertEqual(list(self.miembro.groups.values_list("name", flat=True)),
                         ["Encargado de inventario"])

    def test_la_edicion_no_expone_el_nombre_de_usuario_ni_la_clave(self):
        self.client.force_login(self.operador)
        respuesta = self.client.get(reverse("usuarios:editar", args=[self.miembro.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'name="username"')
        self.assertNotContains(respuesta, 'name="password1"')

    def test_editar_no_degrada_un_rol_que_el_gestor_no_otorga(self):
        """Corregir un teléfono no puede cambiarle el rol a la cuenta."""
        administrador = self.crear_cuenta(
            "administrador-gc", "0580000030", "Administrador del sistema", self.estacion
        )
        superusuario = get_user_model().objects.create_superuser(
            username="super-gc", cedula="0580000031", password="clave-inicial"
        )
        self.client.force_login(superusuario)
        url = reverse("usuarios:editar", args=[administrador.pk])
        respuesta = self.client.get(url)
        self.assertContains(respuesta, "Administrador del sistema")
        self.client.post(url, {
            "first_name": "Marta",
            "last_name": "Silva",
            "cedula": administrador.cedula,
            "email": "",
            "telefono": "0977777777",
            "cargo_institucional": "",
            "estacion": self.estacion.pk,
            "grupo": Group.objects.get(name="Administrador del sistema").pk,
        })
        administrador.refresh_from_db()
        self.assertEqual(administrador.first_name, "Marta")
        self.assertEqual(list(administrador.groups.values_list("name", flat=True)),
                         ["Administrador del sistema"])

    def test_una_cuenta_de_otra_institucion_no_es_alcanzable(self):
        self.client.force_login(self.operador)
        self.assertEqual(
            self.client.get(reverse("usuarios:editar", args=[self.ajeno.pk])).status_code,
            404,
        )

    def test_un_perfil_sin_gestion_no_entra(self):
        self.client.force_login(self.miembro)
        self.assertEqual(
            self.client.get(reverse("usuarios:editar", args=[self.miembro.pk])).status_code,
            403,
        )

class DesactivacionTests(BaseCuentasTests):
    def test_desactiva_y_reactiva_una_cuenta(self):
        self.client.force_login(self.operador)
        url = reverse("usuarios:cambiar_actividad", args=[self.miembro.pk])
        self.client.post(url)
        self.miembro.refresh_from_db()
        self.assertFalse(self.miembro.is_active)
        self.client.post(url)
        self.miembro.refresh_from_db()
        self.assertTrue(self.miembro.is_active)

    def test_nadie_se_desactiva_a_si_mismo(self):
        self.client.force_login(self.operador)
        respuesta = self.client.post(
            reverse("usuarios:cambiar_actividad", args=[self.operador.pk]), follow=True
        )
        self.operador.refresh_from_db()
        self.assertTrue(self.operador.is_active)
        self.assertContains(respuesta, "No puede desactivar su propia cuenta.")

    def test_la_desactivacion_solo_acepta_post(self):
        self.client.force_login(self.operador)
        self.assertEqual(
            self.client.get(
                reverse("usuarios:cambiar_actividad", args=[self.miembro.pk])
            ).status_code,
            405,
        )

    def test_el_listado_muestra_las_acciones_de_cada_cuenta(self):
        self.client.force_login(self.operador)
        respuesta = self.client.get(reverse("usuarios:lista"))
        self.assertContains(respuesta, reverse("usuarios:editar", args=[self.miembro.pk]))
        self.assertContains(
            respuesta, reverse("usuarios:restablecer_clave", args=[self.miembro.pk])
        )
        self.assertContains(respuesta, "Desactivar")
        # El operador no ve un botón para apagarse a sí mismo.
        self.assertNotContains(
            respuesta, reverse("usuarios:cambiar_actividad", args=[self.operador.pk])
        )

class RestablecerClaveTests(BaseCuentasTests):
    def test_el_operador_restablece_y_obliga_a_reemplazarla(self):
        self.client.force_login(self.operador)
        respuesta = self.client.post(
            reverse("usuarios:restablecer_clave", args=[self.miembro.pk]),
            {"new_password1": CLAVE_NUEVA, "new_password2": CLAVE_NUEVA},
        )
        self.assertRedirects(respuesta, reverse("usuarios:lista"))
        self.miembro.refresh_from_db()
        self.assertTrue(self.miembro.check_password(CLAVE_NUEVA))
        self.assertTrue(self.miembro.debe_cambiar_clave)

    def test_para_la_clave_propia_remite_al_cambio_normal(self):
        self.client.force_login(self.operador)
        respuesta = self.client.get(
            reverse("usuarios:restablecer_clave", args=[self.operador.pk])
        )
        self.assertRedirects(respuesta, reverse("usuarios:cambiar_clave"))

    def test_no_alcanza_a_una_cuenta_de_otra_institucion(self):
        self.client.force_login(self.operador)
        self.assertEqual(
            self.client.get(
                reverse("usuarios:restablecer_clave", args=[self.ajeno.pk])
            ).status_code,
            404,
        )
