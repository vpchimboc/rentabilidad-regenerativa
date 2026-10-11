"""Pruebas de la estadística Delphi: IVC y W de Kendall."""

from django.test import SimpleTestCase

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
