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
        call_command("cargar_demo")

    def test_ordenamiento_de_escenarios(self):
        periodo = Periodo.objects.first()
        resultados = {r["tipo"]: r["resultado"]["irr"] for r in simular(periodo.mediciones_dict())}
        self.assertGreater(resultados["OPT"], resultados["ESP"])
        self.assertGreater(resultados["ESP"], resultados["PES"])

    def test_factor_respeta_la_direccion_del_indicador(self):
        """Un escenario optimista debe reducir los residuos, no aumentarlos."""
        periodo = Periodo.objects.first()
        mediciones = periodo.mediciones_dict()
        base = mediciones["AMB_RESID"]
        from escenarios.services import _aplicar_factor, _indice_indicadores
        from framework.models import Dimension

        indicadores = _indice_indicadores(
            Dimension.objects.prefetch_related("variables__indicadores").all()
        )
        ajustadas = _aplicar_factor(mediciones, 1.15, indicadores)
        self.assertLess(ajustadas["AMB_RESID"], base)     # menor es mejor
        self.assertGreater(ajustadas["ECO_ROI"], mediciones["ECO_ROI"])  # mayor es mejor

    def test_factor_mejora_tambien_valores_negativos(self):
        """Margen negativo y captura neta de carbono (valor negativo) deben mejorar."""
        from escenarios.services import _aplicar_factor, _indice_indicadores
        from framework.models import Dimension

        indicadores = _indice_indicadores(
            Dimension.objects.prefetch_related("variables__indicadores").all()
        )
        base = {"ECO_MARGEN": -4.0, "AMB_CARB": -200.0}
        for factor, sentido in ((1.15, 1), (0.85, -1)):
            ajustadas = _aplicar_factor(base, factor, indicadores)
            for codigo, valor in base.items():
                with self.subTest(codigo=codigo, factor=factor):
                    ind = indicadores[codigo]
                    delta = ind.nivel_continuo(ajustadas[codigo]) - ind.nivel_continuo(valor)
                    self.assertGreater(delta * sentido, 0)

    def test_sensibilidad_con_valores_negativos_tiene_amplitud_positiva(self):
        periodo = Periodo.objects.first()
        mediciones = periodo.mediciones_dict()
        mediciones["ECO_MARGEN"] = -4.0
        mediciones["ECO_ROI"] = -6.0
        mediciones["AMB_CARB"] = -200.0
        _, filas = sensibilidad(mediciones)
        self.assertTrue(all(f["amplitud"] >= 0 for f in filas))

    def test_sensibilidad_ordena_por_amplitud(self):
        periodo = Periodo.objects.first()
        _, filas = sensibilidad(periodo.mediciones_dict())
        amplitudes = [f["amplitud"] for f in filas]
        self.assertEqual(amplitudes, sorted(amplitudes, reverse=True))


class DatasetPublicoTest(TestCase):
    """Construcción del dataset desde archivos con el formato de la SCVS y B Lab."""

    CABECERA_RANKING = (
        "anio,expediente,ingresos_ventas,ingresos_totales,n_empleados,"
        "costos_ventas_prod,gastos_admin_ventas,roa,ciiu_n1,ciiu_n6\n"
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
            + "2025,1,200000,210000,5,90000,60000,0.08,M,M7110.01\n"
            + "2025,2,500000,500000,3,100000,50000,0.10,I,I5510.01\n"
            + "2025,3,100000,100000,4,50000,20000,0.05,C,C1079.01\n"
            + "2025,4,900000,900000,120,1,1,0.05,C,C1079.01\n"
            + "2024,3,90000,90000,4,50000,20000,0.05,C,C1079.01\n",
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
            self.assertEqual(float(atuk["OPE_PROD"]), 40000.0)
            self.assertEqual(float(atuk["OPE_COSTO"]), 75.0)
            self.assertEqual(float(atuk["ECO_ROI"]), 8.0)
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
        resultado = __import__("framework.services", fromlist=["evaluar"]).evaluar(
            periodo.mediciones_dict()
        )
        self.assertTrue(resultado["incompleto"])
        self.assertNotIn("degenerativa", resultado["veredicto"])
        self.assertFalse(Emprendimiento.objects.get(nombre="Montemar").periodos.exists())


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
