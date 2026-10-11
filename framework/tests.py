"""Pruebas del motor de cálculo del IRR."""

from django.core.management import call_command
from django.test import TestCase

from framework.models import Dimension, Indicador
from framework.services import elasticidad, evaluar, irr_desde_niveles


class EscalaDeNivelesTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_framework")

    def test_indicador_mayor_mejor(self):
        ind = Indicador.objects.get(codigo="ECO_MARGEN")  # cortes 0, 5, 12, 20
        self.assertEqual(ind.nivel(-4), 0)
        self.assertEqual(ind.nivel(2), 1)
        self.assertEqual(ind.nivel(7), 2)
        self.assertEqual(ind.nivel(15), 3)
        self.assertEqual(ind.nivel(25), 4)

    def test_indicador_menor_mejor(self):
        """En 'menor es mejor' los cortes descienden: 200, 0, −100, −300 tCO₂e."""
        ind = Indicador.objects.get(codigo="AMB_CARB")
        self.assertEqual(ind.nivel(400), 0)   # emite mucho
        self.assertEqual(ind.nivel(100), 1)
        self.assertEqual(ind.nivel(-50), 2)   # balance cerca de cero
        self.assertEqual(ind.nivel(-200), 3)
        self.assertEqual(ind.nivel(-400), 4)  # captura neta alta

    def test_nivel_continuo_es_monotono(self):
        ind = Indicador.objects.get(codigo="ECO_ROI")
        valores = [-5, 0, 4, 8, 12, 15, 20, 25, 40]
        niveles = [ind.nivel_continuo(v) for v in valores]
        self.assertEqual(niveles, sorted(niveles))
        self.assertLessEqual(max(niveles), 4.0)
        self.assertGreaterEqual(min(niveles), 0.0)


class AgregacionNoCompensatoriaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_framework")

    def test_una_dimension_en_cero_anula_el_indice(self):
        """La propiedad central del framework: no hay compensación entre dimensiones."""
        niveles = {"D1": 4.0, "D2": 4.0, "D3": 4.0, "D4": 0.0}
        self.assertEqual(irr_desde_niveles(niveles), 0.0)

    def test_geometrico_penaliza_frente_a_aritmetico(self):
        """Con desempeño desigual, el índice geométrico está por debajo del aritmético."""
        mediciones = {i.codigo: i.c4 for i in Indicador.objects.all()}
        # Se degrada una sola dimensión al mínimo.
        for ind in Indicador.objects.filter(variable__dimension__codigo="D3"):
            mediciones[ind.codigo] = ind.c1
        r = evaluar(mediciones)
        self.assertLess(r["irr"], r["media_aritmetica"])
        self.assertLess(r["penalizacion"], 0)

    def test_desempeno_maximo_da_indice_uno(self):
        mediciones = {i.codigo: i.c4 for i in Indicador.objects.all()}
        r = evaluar(mediciones)
        self.assertAlmostEqual(r["irr"], 1.0, places=4)
        self.assertEqual(r["minimo_dimensional"], 4)
        self.assertEqual(r["veredicto"], "Regenerativo pleno")

    def test_umbral_de_calificacion(self):
        """Nivel 2 en todo: buen índice, pero no califica como regenerativo."""
        mediciones = {i.codigo: i.c2 for i in Indicador.objects.all()}
        r = evaluar(mediciones)
        self.assertEqual(r["minimo_dimensional"], 2)
        self.assertEqual(r["veredicto"], "No califica como regenerativo")

    def test_cuello_de_botella_es_la_dimension_mas_debil(self):
        mediciones = {i.codigo: i.c3 for i in Indicador.objects.all()}
        for ind in Indicador.objects.filter(variable__dimension__codigo="D2"):
            mediciones[ind.codigo] = ind.c1
        r = evaluar(mediciones)
        self.assertEqual(r["cuello_de_botella"], "D2")

    def test_elasticidad_prioriza_el_cuello_de_botella(self):
        """Subir un nivel en la dimensión más débil rinde más que en las demás."""
        mediciones = {i.codigo: i.c3 for i in Indicador.objects.all()}
        for ind in Indicador.objects.filter(variable__dimension__codigo="D3"):
            mediciones[ind.codigo] = ind.c1
        base, filas = elasticidad(mediciones)
        self.assertEqual(filas[0]["dimension"].codigo, "D3")
        self.assertGreater(filas[0]["ganancia"], 0)

    def test_dimension_sin_medir_no_se_declara_degenerativa(self):
        """Falta de datos no es lo mismo que nivel 0: no debe anular el índice."""
        mediciones = {
            i.codigo: i.c3
            for i in Indicador.objects.exclude(variable__dimension__codigo="D4")
        }
        r = evaluar(mediciones)
        self.assertGreater(r["irr"], 0)
        self.assertTrue(r["incompleto"])
        self.assertEqual(r["dimensiones_sin_dato"], ["D4"])
        self.assertEqual(r["minimo_dimensional"], 3)
        self.assertEqual(r["veredicto"], "Evaluación incompleta — dimensiones sin dato")
        d4 = next(d for d in r["dimensiones"] if d["dimension"].codigo == "D4")
        self.assertTrue(d4["sin_dato"])
        self.assertNotEqual(r["cuello_de_botella"], "D4")

    def test_elasticidad_omite_dimensiones_sin_dato(self):
        mediciones = {
            i.codigo: i.c2
            for i in Indicador.objects.exclude(variable__dimension__codigo="D4")
        }
        _, filas = elasticidad(mediciones)
        d4 = next(f for f in filas if f["dimension"].codigo == "D4")
        self.assertIsNone(d4["ganancia"])
        self.assertTrue(all(f["ganancia"] > 0 for f in filas if f["dimension"].codigo != "D4"))

    def test_sin_mediciones_no_inventa_resultado(self):
        r = evaluar({})
        self.assertEqual(r["irr"], 0.0)
        self.assertEqual(r["veredicto"], "Sin datos suficientes")


class PesosTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_framework")

    def test_pesos_se_normalizan_aunque_no_sumen_uno(self):
        Dimension.objects.all().update(peso=2.0)  # suman 8, no 1
        mediciones = {i.codigo: i.c4 for i in Indicador.objects.all()}
        self.assertAlmostEqual(evaluar(mediciones)["irr"], 1.0, places=4)
