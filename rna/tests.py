"""Pruebas del modelo de Red Neuronal Artificial."""

from django.core.management import call_command
from django.test import TestCase

from rna.mlp import MLP
from rna.services import entrenar, generar_dataset, predecir


class MLPTest(TestCase):
    def test_aprende_una_funcion_no_lineal(self):
        """XOR escalado: si la red no aprende esto, la capa oculta no sirve de nada."""
        X = [[0, 0], [0, 1], [1, 0], [1, 1]] * 40
        y = [0.1, 0.9, 0.9, 0.1] * 40
        red = MLP(2, n_ocultas=6, semilla=3)
        red.entrenar(X, y, epocas=400, lr=0.3, validacion=0.0)
        self.assertLess(abs(red.predecir([0, 0]) - 0.1), 0.15)
        self.assertLess(abs(red.predecir([0, 1]) - 0.9), 0.15)

    def test_serializacion_conserva_las_predicciones(self):
        X = [[i / 10, (10 - i) / 10] for i in range(11)]
        y = [i / 10 for i in range(11)]
        red = MLP(2, n_ocultas=4, semilla=5)
        red.entrenar(X, y, epocas=50, lr=0.1, validacion=0.0)
        copia = MLP.desde_dict(red.a_dict())
        self.assertAlmostEqual(red.predecir([0.3, 0.7]), copia.predecir([0.3, 0.7]), places=9)


class SinReferenciasTest(TestCase):
    """Sin referencias L/U justificadas no hay IRR calculable ni etiquetas: no se entrena."""

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_framework", verbosity=0)

    def test_no_entrenable_sin_referencias(self):
        from rna.services import RNANoEntrenable, diagnostico

        self.assertEqual(diagnostico()["dimensiones_sin_referencias"], ["D1", "D2", "D3", "D4"])
        with self.assertRaises(RNANoEntrenable):
            generar_dataset(n_muestras=5)


class ServiciosRNATest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_framework", verbosity=0)
        from framework.pruebas import asignar_referencias_prueba

        asignar_referencias_prueba()

    def test_dataset_simulado_tiene_la_forma_esperada(self):
        X, y, codigos = generar_dataset(n_muestras=40)
        self.assertEqual(len(X), 40)
        self.assertEqual(len(X[0]), len(codigos))
        self.assertTrue(all(0.0 <= v <= 1.0 for v in y))

    def test_entrenamiento_produce_modelo_utilizable(self):
        modelo = entrenar(n_muestras=120, n_ocultas=6, epocas=60, lr=0.1)
        self.assertTrue(modelo.activo)
        self.assertIn("r2", modelo.metricas)
        self.assertEqual(modelo.n_entradas, len(modelo.codigos_entrada))

    def test_prediccion_solo_con_todas_las_entradas(self):
        entrenar(n_muestras=120, n_ocultas=6, epocas=60, lr=0.1)
        from framework.models import Indicador

        completas = {i.codigo: (i.ref_t if i.ref_t is not None else (i.ref_l + i.ref_u) / 2) for i in Indicador.objects.all()}
        r = predecir(completas)
        self.assertTrue(r["aplicable"])
        self.assertAlmostEqual(r["error"], r["prediccion"] - r["analitico"], places=4)
        # Con un faltante no predice ni lo reemplaza por cero
        incompletas = dict(completas)
        incompletas.pop("S9")
        r = predecir(incompletas)
        self.assertFalse(r["aplicable"])
        self.assertEqual(r["faltan"], ["S9"])
