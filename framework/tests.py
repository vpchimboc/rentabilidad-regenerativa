"""Pruebas del motor FRR 1.0 contra la especificación Fase 2 (§2.4, §2.5, §2.12)."""

from django.core.management import call_command
from django.test import TestCase

from emprendimientos.models import Emprendimiento, Medicion, Periodo, VerificacionSalvaguarda
from framework.models import Dimension, Indicador, ParametrosFRR
from framework.pruebas import asignar_referencias_prueba
from framework.services import elasticidad, evaluar, irr_desde_puntajes


def _todos(valor_fn):
    return {i.codigo: valor_fn(i) for i in Indicador.objects.all()}


def _medio(i):
    """Valor que normaliza a z = 0,5 con las referencias de prueba."""
    if i.tipo == Indicador.OBJETIVO:
        return i.ref_t + i.ref_h / 2
    return (i.ref_l + i.ref_u) / 2


class CatalogoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_framework", verbosity=0)

    def test_cuatro_dimensiones_con_codigos_semanticos(self):
        nombres = dict(Dimension.objects.values_list("codigo", "nombre"))
        self.assertEqual(nombres, {"D1": "Rentabilidad económica", "D2": "Regeneración ambiental",
                                   "D3": "Valor social", "D4": "Excelencia operacional"})

    def test_cuarenta_y_dos_kpi_candidatos(self):
        conteo = {d: Indicador.objects.filter(variable__dimension__codigo=d).count() for d in ("D1", "D2", "D3", "D4")}
        self.assertEqual(conteo, {"D1": 7, "D2": 10, "D3": 13, "D4": 12})
        self.assertTrue(all(i.formula and i.componentes for i in Indicador.objects.all()))

    def test_pesos_iguales_hasta_validacion_experta(self):
        self.assertEqual(set(Dimension.objects.values_list("peso", flat=True)), {0.25})

    def test_sin_referencias_arbitrarias(self):
        self.assertFalse(any(i.puntuable for i in Indicador.objects.all()))

    def test_correspondencia_con_catalogo_preliminar(self):
        self.assertIn("ECO_ROI", Indicador.objects.get(codigo="E3").equivalencia_v0)
        self.assertIn("OPE_ENER", Indicador.objects.get(codigo="A3").equivalencia_v0)


class NormalizacionTest(TestCase):
    """Ejemplos didácticos de la §2.12.2."""

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_framework", verbosity=0)

    def test_beneficio_costo_objetivo(self):
        ind = Indicador(tipo=Indicador.BENEFICIO, ref_l=50, ref_u=90)
        self.assertAlmostEqual(ind.normalizar(70), 0.5)
        self.assertEqual(ind.normalizar(200), 1.0)
        self.assertEqual(ind.normalizar(-5), 0.0)
        self.assertAlmostEqual(Indicador(tipo=Indicador.COSTO, ref_l=2, ref_u=10).normalizar(6), 0.5)
        self.assertAlmostEqual(Indicador(tipo=Indicador.OBJETIVO, ref_t=10, ref_h=4).normalizar(8), 0.5)

    def test_sin_referencias_no_se_puntua(self):
        self.assertIsNone(Indicador(tipo=Indicador.BENEFICIO).normalizar(5))
        self.assertIsNone(Indicador(tipo=Indicador.BENEFICIO, ref_l=5, ref_u=5).normalizar(5))


class AgregacionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_framework", verbosity=0)
        asignar_referencias_prueba()

    def test_puntuacion_y_cobertura(self):
        r = evaluar(_todos(_medio))
        for d in r["dimensiones"]:
            self.assertAlmostEqual(d["S"], 0.5, places=6)
            self.assertEqual(d["C"], 1.0)

    def test_formula_del_irr_suavizado_y_sin_suavizado(self):
        eps = ParametrosFRR.vigentes().epsilon
        r = evaluar(_todos(_medio))
        esperado = (eps + (1 - eps) * 0.5) ** 1.0  # α suman 1 y S = 0,5 en todas
        self.assertAlmostEqual(r["irr"], round(esperado, 4), places=4)
        self.assertAlmostEqual(r["irr0"], 0.5, places=4)

    def test_dimension_en_cero_anula_irr0_pero_no_el_suavizado(self):
        med = _todos(_medio)
        for i in Indicador.objects.filter(variable__dimension__codigo="D2"):
            med[i.codigo] = i.ref_u if i.tipo == Indicador.COSTO else (i.ref_l if i.tipo == Indicador.BENEFICIO else i.ref_t + 2 * i.ref_h)
        r = evaluar(med)
        self.assertEqual(r["irr0"], 0.0)
        self.assertGreater(r["irr"], 0.0)
        self.assertLess(r["irr"], 0.2)

    def test_cobertura_insuficiente_no_calcula_irr_ni_imputa_ceros(self):
        med = {c: v for c, v in _todos(_medio).items() if not c.startswith("S")}
        r = evaluar(med)
        self.assertIsNone(r["irr"])
        d3 = next(d for d in r["dimensiones"] if d["dimension"].codigo == "D3")
        self.assertEqual(d3["C"], 0.0)
        self.assertFalse(d3["suficiente"])
        self.assertNotEqual(r["clasificacion"], "b")

    def test_no_aplicable_sale_del_denominador(self):
        med = {c: v for c, v in _todos(_medio).items() if c != "O3"}
        sin_na = evaluar(med)
        con_na = evaluar(med, no_aplicables={"O3"})
        d4 = lambda r: next(d for d in r["dimensiones"] if d["dimension"].codigo == "D4")
        self.assertLess(d4(sin_na)["C"], 1.0)
        self.assertEqual(d4(con_na)["C"], 1.0)

    def test_elasticidad_prioriza_la_dimension_mas_debil(self):
        med = _todos(_medio)
        for i in Indicador.objects.filter(variable__dimension__codigo="D3"):
            med[i.codigo] = i.ref_l + 0.1 * (i.ref_u - i.ref_l) if i.tipo == Indicador.BENEFICIO else med[i.codigo]
        _, filas = elasticidad(med)
        self.assertEqual(filas[0]["dimension"].codigo, "D3")
        self.assertGreater(filas[0]["ganancia"], 0)

    def test_irr_desde_puntajes(self):
        self.assertAlmostEqual(irr_desde_puntajes({"D1": 1, "D2": 1, "D3": 1, "D4": 1}), 1.0)


class SalvaguardasYClasificacionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_framework", verbosity=0)
        asignar_referencias_prueba()
        cls.emp = Emprendimiento.objects.create(nombre="Caso", fuente="prueba")

    def _periodo(self, anio=2025, ventas=1000, cf=200, cv=400):
        return Periodo.objects.create(emprendimiento=self.emp, anio=anio, ventas=ventas,
                                      costos_fijos=cf, costos_variables=cv)

    def test_a_sin_datos_financieros(self):
        r = evaluar({"E2": 0.1})
        self.assertEqual(r["clasificacion"], "a")
        self.assertIsNone(r["salvaguardas"]["G1"]["valor"])

    def test_b_inviabilidad_economica(self):
        p = self._periodo(ventas=1000, cf=700, cv=500)  # PE = 1400 > V
        r = evaluar({}, periodo=p)
        self.assertEqual(r["salvaguardas"]["G1"]["valor"], 0)
        self.assertEqual(r["clasificacion"], "b")
        self.assertEqual(r["R"], 0)

    def test_c_solo_informacion_financiera(self):
        p = self._periodo()
        r = evaluar({"E2": 0.1, "E4": 1.5, "E5": 0.05}, periodo=p)
        self.assertEqual(r["salvaguardas"]["G1"]["valor"], 1)
        self.assertEqual(r["clasificacion"], "c")
        self.assertIsNone(r["irr"])
        # E1 se deriva del período y se marca
        e1 = next(f for f in r["dimensiones"][0]["filas"] if f["indicador"].codigo == "E1")
        self.assertTrue(e1["derivado"])

    def test_d_sostenible_sin_evidencia_ecologica_verificada(self):
        p = self._periodo()
        med = {c: v for c, v in _todos(_medio).items() if c != "A10"}
        r = evaluar(med, periodo=p)
        self.assertEqual(r["clasificacion"], "d")
        self.assertIsNone(r["R"])  # G2/G3/G5 indeterminadas

    def test_e_regeneracion_verificable_solo_con_todas_las_salvaguardas(self):
        p = self._periodo()
        self._periodo(anio=2024)
        for cod in ("G2", "G5"):
            VerificacionSalvaguarda.objects.create(periodo=p, codigo=cod, estado="1", evidencia="Auditoría documentada")
        med = _todos(_medio)
        med["A10"] = 5.0  # resultado ecológico neto positivo
        for i in Indicador.objects.all():
            Medicion.objects.create(periodo=p, indicador=i, valor=med[i.codigo], fuente="registro")
        r = evaluar(p.mediciones_dict(), periodo=p)
        self.assertEqual({k: v["valor"] for k, v in r["salvaguardas"].items()}, {"G1": 1, "G2": 1, "G3": 1, "G4": 1, "G5": 1})
        self.assertEqual(r["R"], 1)
        self.assertEqual(r["clasificacion"], "e")

    def test_salvaguarda_incumplida_impide_regeneracion(self):
        p = self._periodo()
        VerificacionSalvaguarda.objects.create(periodo=p, codigo="G2", estado="0", evidencia="Accidente grave")
        r = evaluar({**_todos(_medio), "A10": 5.0}, periodo=p)
        self.assertEqual(r["R"], 0)
        self.assertNotEqual(r["clasificacion"], "e")
        self.assertIn("salvaguarda social incumplida", r["veredicto"])


class MatrizReferenciasTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_framework", verbosity=0)

    def _csv(self, tmp, filas):
        import csv

        from framework.management.commands.matriz_referencias import COLUMNAS

        ruta = tmp / "matriz.csv"
        with ruta.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNAS, delimiter=";")
            w.writeheader()
            for f in filas:
                w.writerow({"estado_kpi": "CAND", "estado_referencia": "PROP", **f})
        return ruta

    def test_exporta_los_42_e_importa_con_ficha_completa(self):
        import csv
        import tempfile
        from io import StringIO
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            salida = tmp / "export.csv"
            call_command("matriz_referencias", "exportar", str(salida), stdout=StringIO())
            with salida.open(encoding="utf-8-sig") as fh:
                self.assertEqual(len(list(csv.DictReader(fh, delimiter=";"))), 42)

            ruta = self._csv(tmp, [{"codigo": "A2", "L": "0", "U": "1", "tipo_fuente": "MAT",
                                    "fuente": "Límites naturales de una proporción", "periodo": "2026",
                                    "evidencia": "Definición del KPI", "estado_referencia": "JUST", "estado_kpi": "ACT"}])
            call_command("matriz_referencias", "importar", str(ruta), stdout=StringIO())  # simulación
            self.assertFalse(Indicador.objects.get(codigo="A2").puntuable)
            call_command("matriz_referencias", "importar", str(ruta), aplicar=True, stdout=StringIO())
        a2 = Indicador.objects.get(codigo="A2")
        self.assertTrue(a2.puntuable)
        self.assertEqual((a2.tipo_fuente_referencia, a2.estado_referencia, a2.estado), ("MAT", "JUST", "ACT"))
        self.assertTrue(a2.referencia_provisional)  # solo «Validado» deja de ser provisional
        self.assertEqual(Indicador.objects.count(), 42)

    def test_rechaza_referencias_sin_fuente_o_invalidas(self):
        import tempfile
        from io import StringIO
        from pathlib import Path

        from django.core.management.base import CommandError

        with tempfile.TemporaryDirectory() as tmp:
            sin_fuente = self._csv(Path(tmp), [{"codigo": "A3", "L": "0.5", "U": "3"}])
            with self.assertRaises(CommandError):
                call_command("matriz_referencias", "importar", str(sin_fuente), aplicar=True, stdout=StringIO())
            invertida = self._csv(Path(tmp), [{"codigo": "A3", "L": "3", "U": "0.5", "tipo_fuente": "SEC", "fuente": "x"}])
            with self.assertRaises(CommandError):
                call_command("matriz_referencias", "importar", str(invertida), aplicar=True, stdout=StringIO())
        self.assertFalse(Indicador.objects.get(codigo="A3").puntuable)


class MedicionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_framework", verbosity=0)

    def test_cociente_y_denominador_cero(self):
        p = Periodo.objects.create(emprendimiento=Emprendimiento.objects.create(nombre="X"), anio=2025)
        ok = Medicion.objects.create(periodo=p, indicador=Indicador.objects.get(codigo="S7"), numerador=8, denominador=10)
        self.assertAlmostEqual(ok.valor, 0.8)
        nd = Medicion.objects.create(periodo=p, indicador=Indicador.objects.get(codigo="S9"), numerador=3, denominador=0)
        self.assertEqual(nd.estado, Medicion.ND)
        self.assertIsNone(nd.valor)
        self.assertNotIn("S9", p.mediciones_dict())
