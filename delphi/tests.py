"""Pruebas de la estadística Delphi: IVC y W de Kendall."""

from django.test import SimpleTestCase, TestCase

from delphi.stats import ivc_item, kendall_w


class IVCTest(SimpleTestCase):
    def test_todos_de_acuerdo(self):
        self.assertEqual(ivc_item([5, 4, 5, 4]), 1.0)

    def test_ninguno_de_acuerdo(self):
        self.assertEqual(ivc_item([1, 2, 3, 3]), 0.0)

    def test_proporcion_parcial(self):
        self.assertAlmostEqual(ivc_item([5, 5, 3, 2]), 0.5)

    def test_sin_respuestas(self):
        self.assertEqual(ivc_item([]), 0.0)


class KendallWTest(SimpleTestCase):
    def test_acuerdo_perfecto_da_w_uno(self):
        """Tres jueces que ordenan los ítems exactamente igual: W = 1."""
        matriz = [[1, 2, 3, 4, 5]] * 3
        resultado = kendall_w(matriz)
        self.assertAlmostEqual(resultado["w"], 1.0, places=4)
        self.assertEqual(resultado["gl"], 4)
        self.assertEqual(resultado["m"], 3)

    def test_desacuerdo_maximo_da_w_cercano_a_cero(self):
        matriz = [[1, 2, 3, 4], [4, 3, 2, 1]]
        self.assertAlmostEqual(kendall_w(matriz)["w"], 0.0, places=4)

    def test_empates_totales_no_dividen_por_cero(self):
        """Si todos califican todo con 5, la corrección por empates anula el denominador."""
        matriz = [[5, 5, 5, 5]] * 3
        resultado = kendall_w(matriz)
        self.assertEqual(resultado["w"], 0.0)

    def test_chi_cuadrado_coherente_con_w(self):
        matriz = [[1, 2, 3, 4, 5], [1, 3, 2, 4, 5], [2, 1, 3, 5, 4]]
        r = kendall_w(matriz)
        self.assertAlmostEqual(r["chi2"], r["m"] * (r["n"] - 1) * r["w"], places=4)

    def test_un_solo_juez_no_produce_concordancia(self):
        self.assertEqual(kendall_w([[1, 2, 3]])["w"], 0.0)


class ReporteYExpertosTest(TestCase):
    """Reporte de evaluación (mediana, rango, % 4-5, I-CVI) y administración de expertos con permisos."""

    def setUp(self):
        from io import StringIO
        from django.core.management import call_command
        call_command("cargar_framework", stdout=StringIO())

    def test_reporte_calcula_indicadores(self):
        import datetime
        from delphi.models import Dictamen, Experto, Item, Respuesta, Ronda
        from delphi.views import datos_reporte
        ronda = Ronda.objects.create(numero=9, fecha=datetime.date(2026, 11, 11))
        e1, e2, e3 = (Experto.objects.create(nombre=n) for n in ("A", "B", "C"))
        p04 = Item.objects.get(codigo="P04")
        for e, v in ((e1, 5), (e2, 4), (e3, 2)):
            Respuesta.objects.create(ronda=ronda, experto=e, item=p04, valor=v)
        Dictamen.objects.create(ronda=ronda, experto=e1, recomendacion="AJU", cambio_prioritario="A10: definir línea base")
        f = next(x for x in datos_reporte(ronda)["filas"] if x["item"].codigo == "P04")
        self.assertEqual((f["mediana"], f["minimo"], f["maximo"]), (4, 2, 5))
        self.assertEqual(f["pct_favorable"], 66.7)
        self.assertEqual(f["icvi"], 0.667)
        r = self.client.get(f"/delphi/ronda/{ronda.pk}/reporte/")
        self.assertContains(r, "A10: definir línea base")
        self.assertContains(self.client.get(f"/delphi/ronda/{ronda.pk}/reporte/?formato=csv"), "P04")

    def test_crear_experto_exige_permiso(self):
        from django.contrib.auth import get_user_model
        from delphi.models import Experto
        datos = {"nombre": "Dra. Nueva", "grado": "PHD", "pais": "Ecuador", "anios_experiencia": 8, "publicaciones": 3,
                 "activo": "on"}
        self.assertEqual(self.client.post("/delphi/expertos/nuevo/", datos).status_code, 302)  # al login
        self.assertFalse(Experto.objects.exists())
        admin = get_user_model().objects.create_superuser("adm", "a@a.test", "x-prueba-123")
        self.client.force_login(admin)
        self.client.post("/delphi/expertos/nuevo/", datos)
        e = Experto.objects.get()
        self.assertTrue(e.cumple_criterios)
        self.client.post(f"/delphi/expertos/{e.pk}/eliminar/")
        self.assertFalse(Experto.objects.exists())


class RondasTest(TestCase):
    def test_crear_y_editar_fecha(self):
        import datetime
        from django.contrib.auth import get_user_model
        from delphi.models import Ronda
        self.assertEqual(self.client.post("/delphi/rondas/nueva/", {}).status_code, 302)  # sin sesión → login
        self.client.force_login(get_user_model().objects.create_superuser("adm", "a@a.test", "x-prueba-123"))
        self.client.post("/delphi/rondas/nueva/", {"numero": 3, "fecha": "2026-11-20", "estado": "ABI"})
        r = Ronda.objects.get(numero=3)
        self.client.post(f"/delphi/rondas/{r.pk}/editar/", {"numero": 3, "fecha": "2026-12-01", "estado": "CER"})
        r.refresh_from_db()
        self.assertEqual((r.fecha, r.estado), (datetime.date(2026, 12, 1), "CER"))
