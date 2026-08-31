from io import StringIO

from django.core.management import call_command
from django.template.loader import render_to_string
from django.test import TestCase

from instituciones.models import Canton, CuerpoBomberos, Estacion
from inventario.models import CategoriaRecurso, Recurso, TipoRecurso

class CargaInventarioBomberilTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        canton = Canton.objects.create(nombre="Latacunga", codigo="INV-REF")
        cuerpo = CuerpoBomberos.objects.create(
            canton=canton,
            nombre="Cuerpo de Bomberos de Latacunga",
            sigla="CB-REF",
            ruc="0597000000001",
            direccion="Latacunga",
        )
        cls.estacion = Estacion.objects.create(
            cuerpo_bomberos=cuerpo,
            nombre="Estación Central",
            codigo="REF-01",
            direccion="Latacunga",
            latitud="-0.935000",
            longitud="-78.615000",
        )

    def test_carga_catalogo_y_recursos_por_estacion(self):
        call_command("cargar_inventario_bomberil", stdout=StringIO())

        self.assertEqual(CategoriaRecurso.objects.count(), 6)
        self.assertEqual(TipoRecurso.objects.count(), 15)
        self.assertEqual(Recurso.objects.filter(estacion=self.estacion).count(), 12)
        self.assertTrue(Recurso.objects.filter(codigo_interno="AB-01", tipo__codigo="AUT").exists())
        self.assertFalse(Recurso.objects.get(codigo_interno="AB-01").disponibilidad_actualizada)

    def test_cada_tipo_principal_usa_un_icono_acorde(self):
        call_command("cargar_inventario_bomberil", stdout=StringIO())
        recursos = Recurso.objects.filter(
            estacion=self.estacion,
            codigo_interno__in=("AB-01", "AMB-01", "ERA-01", "EPP-E-01", "CT-01", "RAD-01"),
        ).select_related("tipo", "tipo__categoria", "estacion__cuerpo_bomberos")

        html = render_to_string(
            "inventario/_resultados.html",
            {"recursos": recursos, "puede_gestionar": False},
        )

        for icono in ("ti-firetruck", "ti-ambulance", "ti-scuba-diving-tank", "ti-shield-check", "ti-camera", "ti-radio"):
            self.assertIn(icono, html)

    def test_comando_es_idempotente_y_conserva_registros_existentes(self):
        call_command("cargar_inventario_bomberil", stdout=StringIO())
        recurso = Recurso.objects.get(estacion=self.estacion, codigo_interno="AB-01")
        recurso.nombre = "Autobomba validada por la institución"
        recurso.save(update_fields=["nombre"])

        call_command("cargar_inventario_bomberil", stdout=StringIO())

        self.assertEqual(Recurso.objects.filter(estacion=self.estacion).count(), 12)
        recurso.refresh_from_db()
        self.assertEqual(recurso.nombre, "Autobomba validada por la institución")
