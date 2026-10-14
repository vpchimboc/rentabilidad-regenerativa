"""Pruebas de break-even, escenarios y vistas."""

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from emprendimientos.models import Emprendimiento, Evaluacion, Periodo
from escenarios.services import sensibilidad, simular


class PuntoDeEquilibrioTest(TestCase):
    def test_calculo_del_break_even(self):
        emp = Emprendimiento.objects.create(nombre="Prueba")
        p = Periodo.objects.create(
            emprendimiento=emp, anio=2025,
            ventas=1000, costos_fijos=300, costos_variables=500,
        )
        # Margen de contribución = 1 − 500/1000 = 0,5  →  PE = 300 / 0,5 = 600
        self.assertAlmostEqual(p.punto_equilibrio, 600.0)
        self.assertAlmostEqual(p.margen_sobre_break_even, 1000 / 600)

    def test_sin_margen_de_contribucion_no_hay_break_even(self):
        emp = Emprendimiento.objects.create(nombre="Prueba 2")
        p = Periodo.objects.create(
            emprendimiento=emp, anio=2025,
            ventas=1000, costos_fijos=300, costos_variables=1200,
        )
        self.assertEqual(p.punto_equilibrio, 0.0)


class EscenariosTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        from framework.pruebas import asignar_referencias_prueba

        asignar_referencias_prueba()

    def _indicadores(self):
        from escenarios.services import _indice_indicadores
        from framework.services import cargar_dimensiones

        return _indice_indicadores(cargar_dimensiones())

    def test_ordenamiento_de_escenarios(self):
        periodo = Periodo.objects.get(emprendimiento__nombre="Raíz Andina S.A.S.")
        resultados = {r["tipo"]: r["resultado"]["irr"] for r in simular(periodo.mediciones_dict(), periodo=periodo)}
        self.assertIsNotNone(resultados["ESP"])
        self.assertGreater(resultados["OPT"], resultados["ESP"])
        self.assertGreater(resultados["ESP"], resultados["PES"])

    def test_factor_respeta_el_tipo_de_indicador(self):
        """Optimista: los de costo bajan (residuos), los de beneficio suben, los de objetivo se acercan a T."""
        from escenarios.services import _aplicar_factor

        ind = self._indicadores()
        base = {"A7": 0.4, "E2": 0.1, "S6": 0.9}
        ajust = _aplicar_factor(base, 1.15, ind)
        self.assertLess(ajust["A7"], base["A7"])
        self.assertGreater(ajust["E2"], base["E2"])
        self.assertLess(abs(ajust["S6"] - ind["S6"].ref_t), abs(base["S6"] - ind["S6"].ref_t))

    def test_factor_mejora_tambien_valores_negativos(self):
        """Margen negativo y resultado ecológico negativo deben mejorar en el optimista."""
        from escenarios.services import _aplicar_factor

        ind = self._indicadores()
        base = {"E2": -0.04, "A10": -3.0}
        for factor, sentido in ((1.15, 1), (0.85, -1)):
            ajust = _aplicar_factor(base, factor, ind)
            for codigo, valor in base.items():
                with self.subTest(codigo=codigo, factor=factor):
                    self.assertGreater((ajust[codigo] - valor) * sentido, 0)

    def test_sensibilidad_ordena_por_amplitud(self):
        periodo = Periodo.objects.get(emprendimiento__nombre="Raíz Andina S.A.S.")
        _, filas = sensibilidad(periodo.mediciones_dict(), periodo=periodo)
        amplitudes = [f["amplitud"] for f in filas]
        self.assertTrue(all(a is not None and a >= 0 for a in amplitudes))
        self.assertEqual(amplitudes, sorted(amplitudes, reverse=True))

    def test_sensibilidad_a_los_pesos(self):
        from escenarios.services import sensibilidad_pesos

        periodo = Periodo.objects.get(emprendimiento__nombre="Raíz Andina S.A.S.")
        base, _ = sensibilidad(periodo.mediciones_dict(), periodo=periodo)
        filas = sensibilidad_pesos(base)
        self.assertEqual(len(filas), 4)
        self.assertTrue(all(f["amplitud"] >= 0 for f in filas))


class DatasetPublicoTest(TestCase):
    """Construcción del dataset desde archivos con el formato de la SCVS y B Lab."""

    CABECERA_RANKING = (
        "anio,expediente,ingresos_ventas,ingresos_totales,n_empleados,costos_ventas_prod,"
        "gastos_admin_ventas,utilidad_neta,activos,liquidez_corriente,ciiu_n1,ciiu_n6\n"
    )

    def _archivos(self, tmp):
        import json
        from pathlib import Path

        tmp = Path(tmp)
        (tmp / "cias.csv").write_text(
            "expediente,ruc,nombre,tipo,pro_codigo,provincia\n"
            "1,0190000001001,ATUK CIA.LTDA.,RESPONSABILIDAD LIMITADA ,01,AZUAY \n"
            "2,1390000002001,MONTEMAR S.A.,ANÓNIMA ,13,MANABI \n"
            "3,0190000003001,CAFE NUEVO S.A.S.,SOCIEDAD POR ACCIONES SIMPLIFICADA ,01,AZUAY \n"
            "4,0190000004001,GRANDE S.A.S.,SOCIEDAD POR ACCIONES SIMPLIFICADA ,01,AZUAY \n",
            encoding="utf-8",
        )
        (tmp / "ranking.csv").write_text(
            self.CABECERA_RANKING
            + "2025,1,200000,210000,5,100000,60000,16000,90000,1.8,M,M7110.01\n"
            + "2024,1,160000,160000,5,80000,50000,9000,70000,1.5,M,M7110.01\n"
            + "2025,2,500000,500000,3,100000,50000,50000,300000,2.0,I,I5510.01\n"
            + "2025,3,100000,100000,4,50000,20000,5000,40000,1.1,C,C1079.01\n"
            + "2025,4,900000,900000,120,1,1,1,1,1,C,C1079.01\n",
            encoding="utf-8",
        )
        (tmp / "blab.json").write_text(json.dumps({
            "campos": ["nombre", "slug", "ciudad", "provincia", "industria", "sector",
                       "tamano", "puntaje_bia", "certificada_desde", "certificada"],
            "empresas": [
                ["ATUK", "atuk-ca-ltda", "Cuenca", "Azuay Province", "Environmental consulting",
                 "Service with Minor Environmental Footprint", "1-9", "80.3", "2022-03-30", True],
                ["Montemar", "montemar", "El Carmen", "Galápagos Province", "Accommodation",
                 "Service with Significant Environmental Footprint", "1-9", "105.4", "2024-07-02", True],
            ],
        }), encoding="utf-8")
        return tmp

    def test_construye_e_importa_sin_inventar_datos(self):
        import csv
        import tempfile
        from io import StringIO

        with tempfile.TemporaryDirectory() as tmp:
            tmp = self._archivos(tmp)
            salida = tmp / "salida.csv"
            call_command(
                "preparar_dataset_publico", companias=str(tmp / "cias.csv"),
                ranking=str(tmp / "ranking.csv"), blab=str(tmp / "blab.json"),
                total=3, salida=str(salida), stdout=StringIO(),
            )
            filas = {f["nombre"]: f for f in csv.DictReader(salida.open(encoding="utf-8"))}

            # B Lab + SCVS: RUC e indicadores derivados de estados financieros.
            atuk = filas["ATUK"]
            self.assertEqual(atuk["ruc"], "0190000001001")
            # E1 = (V − PE)/V; PE = 60000/(1 − 100000/200000) = 120000 → 0,40
            self.assertAlmostEqual(float(atuk["E1"]), 0.40)
            self.assertAlmostEqual(float(atuk["E2"]), 0.08)                  # 16000/200000
            self.assertAlmostEqual(float(atuk["E3"]), 16000 / 80000)         # A_prom = (90000 + 70000)/2
            self.assertAlmostEqual(float(atuk["E4"]), 1.8)
            self.assertAlmostEqual(float(atuk["E5"]), 0.25)                  # (200000 − 160000)/160000
            # Sin año anterior: E3 y E5 no calculables (vacíos, no cero)
            self.assertEqual(filas["CAFE NUEVO S.A.S."]["E3"], "")
            # Homónimo en otra provincia: no se asocia el RUC.
            self.assertEqual(filas["Montemar"]["ruc"], "")
            # Complemento SAS: solo micro/pequeñas (1–49 empleados).
            self.assertIn("CAFE NUEVO S.A.S.", filas)
            self.assertNotIn("GRANDE S.A.S.", filas)

            call_command("importar_emprendimientos", str(salida), stdout=StringIO())
            call_command("importar_emprendimientos", str(salida), stdout=StringIO())

        self.assertEqual(Emprendimiento.objects.count(), 3)  # idempotente
        emp = Emprendimiento.objects.get(ruc="0190000001001")
        self.assertIn("bcorporation.net", emp.fuente_url)
        periodo = emp.periodos.get(anio=2025)
        from framework.services import evaluar

        self.assertEqual(set(periodo.mediciones_dict()), {"E1", "E2", "E3", "E4", "E5"})
        resultado = evaluar(periodo.mediciones_dict(), periodo=periodo)
        self.assertEqual(resultado["clasificacion"], "c")  # viable, sin evidencia regenerativa
        self.assertIsNone(resultado["irr"])                 # D2–D4 sin cobertura: no se imputa cero
        cafe = Emprendimiento.objects.get(ruc="0190000003001").periodos.get()
        e3 = cafe.mediciones.get(indicador__codigo="E3")
        self.assertEqual((e3.estado, e3.valor), ("ND", None))
        self.assertFalse(Emprendimiento.objects.get(nombre="Montemar").periodos.exists())


class LimpiezaTest(TestCase):
    def test_elimina_ficticios_y_sin_datos_y_conserva_utilizables(self):
        from io import StringIO

        call_command("cargar_demo", stdout=StringIO())
        util = Emprendimiento.objects.create(nombre="Real SAS", fuente="SCVS", ruc="0190000001001")
        Periodo.objects.create(emprendimiento=util, anio=2025, ventas=1000, costos_fijos=100, costos_variables=400)
        sin_periodo = Emprendimiento.objects.create(nombre="Sin datos", fuente="B Lab")
        sin_ventas = Emprendimiento.objects.create(nombre="Sin ventas", fuente="SCVS")
        Periodo.objects.create(emprendimiento=sin_ventas, anio=2025, ventas=0, costos_fijos=10, costos_variables=0)
        perdida = Emprendimiento.objects.create(nombre="Costos > ventas", fuente="SCVS")
        Periodo.objects.create(emprendimiento=perdida, anio=2025, ventas=100, costos_fijos=10, costos_variables=150)

        call_command("limpiar_datos", stdout=StringIO())  # simulación: no borra
        self.assertEqual(Emprendimiento.objects.count(), 7)

        call_command("limpiar_datos", aplicar=True, stdout=StringIO())
        self.assertEqual(list(Emprendimiento.objects.values_list("nombre", flat=True)), ["Real SAS"])
        self.assertFalse(Emprendimiento.objects.filter(pk=sin_periodo.pk).exists())


class VistasTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo")

    def test_todas_las_paginas_responden(self):
        rutas = [
            reverse("tablero"),
            reverse("framework_matriz"),
            reverse("emprendimiento_lista"),
            reverse("escenario_lista"),
            reverse("rna_panel"),
            reverse("rna_predecir"),
            reverse("delphi_panel"),
            reverse("bibliometria_matriz"),
        ]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 200)

    def test_factores_de_escenario_no_se_localizan(self):
        """En español Django escribe 1,15; un <input type=number> lo rechaza y queda vacío."""
        periodo = Periodo.objects.first()
        html = self.client.get(reverse("escenario_simular", args=[periodo.pk])).content.decode()
        self.assertIn('name="factor_OPT" value="1.15"', html)
        self.assertIn('name="factor_PES" value="0.85"', html)

    def test_evaluacion_se_guarda_al_confirmar(self):
        periodo = Periodo.objects.first()
        url = reverse("evaluar_periodo", args=[periodo.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(Evaluacion.objects.filter(periodo=periodo).count(), 1)

    def test_cuestionario_delphi_registra_respuestas(self):
        from delphi.models import Experto, Item, Respuesta, Ronda

        ronda = Ronda.objects.get(numero=1)
        experto = Experto.objects.first()
        item = Item.objects.get(codigo="I01")
        url = reverse("delphi_cuestionario", args=[ronda.pk])

        self.assertEqual(self.client.get(url, {"experto": experto.pk}).status_code, 200)
        datos = {"experto": experto.pk, "guardar": "1", f"item_{item.id}": "5"}
        self.assertEqual(self.client.post(url, datos).status_code, 302)
        self.assertEqual(
            Respuesta.objects.get(ronda=ronda, experto=experto, item=item).valor, 5
        )

    def test_bibliometria_filtra_por_base(self):
        url = reverse("bibliometria_matriz")
        respuesta = self.client.get(url, {"base": "SCO"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(
            all(r.base == "SCO" for r in respuesta.context["referencias"])
        )

    def test_resultado_delphi_calcula_y_persiste(self):
        from delphi.models import Ronda

        ronda = Ronda.objects.get(numero=2)
        respuesta = self.client.get(reverse("delphi_resultado", args=[ronda.pk]))
        self.assertEqual(respuesta.status_code, 200)
        ronda.refresh_from_db()
        self.assertTrue(hasattr(ronda, "resultado"))
        self.assertGreater(ronda.resultado.s_cvi, 0)
