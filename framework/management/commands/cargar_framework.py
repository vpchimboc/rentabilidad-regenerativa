"""Carga el catálogo del FRR 1.0: 4 dimensiones y 42 KPI candidatos (Fase 2, §2.6–2.9).

Las referencias de normalización (L/U o T/H) NO se cargan aquí: la especificación
prohíbe límites arbitrarios (§2.5). Se fijan después con sustento documentado
(por ejemplo, `manage.py calcular_referencias`) o por acuerdo experto.

También elimina los 17 indicadores de la plataforma preliminar (v0), cuya
correspondencia con el catálogo queda en el campo `equivalencia_v0` y en
CORRESPONDENCIA_V0 (matriz 17 → 42, DIREC 1 prioridad 1).

Uso:  python manage.py cargar_framework
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from delphi.models import Item
from framework.models import Dimension, Indicador, ParametrosFRR, Variable

BEN, COS, OBJ = "BEN", "COS", "OBJ"
PROP = "proporción (0–1)"

# (código, nombre, fórmula, componentes, unidad, tipo, rol)
ESTRUCTURA = [
    ("D1", "Rentabilidad económica",
     "Equilibrio, márgenes, liquidez, flujos y capacidad de reinversión.",
     "Condición de viabilidad y resultado económico", [
        ("V-D1-1", "Viabilidad y holgura sobre el break-even", [
            ("E1", "Margen de seguridad", "(V − PE)/V",
             "V: ventas netas del periodo; PE: ventas de equilibrio = CF/(1 − CV/V), con CF costos fijos y "
             "CV costos variables del mismo periodo. Requiere clasificación de costos válida.", PROP, BEN, "SAL"),
        ]),
        ("V-D1-2", "Rentabilidad", [
            ("E2", "Margen neto", "UN/V", "UN: utilidad neta después de gastos e impuestos; V: ventas netas.", PROP, BEN, "NUC"),
            ("E3", "ROA", "UN/A_prom",
             "UN: utilidad neta; A_prom = (A_inicio + A_fin)/2, activos totales al inicio y al final del periodo.",
             PROP, BEN, "COM"),
        ]),
        ("V-D1-3", "Liquidez, crecimiento y flujo", [
            ("E4", "Razón corriente", "AC/PC",
             "AC: activo corriente; PC: pasivo corriente a la misma fecha de corte. Si PC = 0, situación especial.",
             "veces", BEN, "NUC"),
            ("E5", "Crecimiento de ingresos", "(V_t − V_t−1)/V_t−1",
             "V_t: ventas del periodo; V_t−1: ventas del periodo anterior equivalente.", PROP, BEN, "COM"),
            ("E6", "Margen de flujo operativo", "FCO/V",
             "FCO: flujo neto de efectivo de actividades de operación; V: ventas netas. La utilidad no reemplaza FCO.",
             PROP, BEN, "NUC"),
        ]),
        ("V-D1-4", "Reinversión", [
            ("E7", "Tasa de reinversión", "RI/B",
             "RI: monto reinvertido verificable; B: base financiera definida y positiva (p. ej., flujo de caja disponible).",
             PROP, BEN, "NUC"),
        ]),
    ]),
    ("D2", "Regeneración ambiental",
     "Presiones, circularidad y resultados ecológicos netos frente a línea base.",
     "Resultado socioecológico; requiere evidencia positiva para declarar regeneración", [
        ("V-D2-1", "Presiones y ecoeficiencia", [
            ("A1", "Intensidad material", "M/Q", "M: masa de materiales consumidos (kg); Q: unidades funcionales.", "kg/unidad", COS, "PEN"),
            ("A3", "Intensidad energética", "EN/Q", "EN: energía consumida (kWh o MJ); Q: unidad funcional.", "kWh/unidad", COS, "PEN"),
            ("A5", "Intensidad hídrica", "AG/Q", "AG: agua captada/consumida según alcance (m³); Q: unidad funcional.", "m³/unidad", COS, "PEN"),
            ("A6", "Intensidad GEI", "CO2e/Q",
             "CO2e: emisiones GEI (kg CO₂e) = Σ actividad × factor de emisión, con alcance documentado; Q: unidad funcional.",
             "kg CO₂e/unidad", COS, "PEN"),
            ("A7", "Intensidad de residuos", "RS/Q", "RS: residuos generados (kg); Q: unidad funcional.", "kg/unidad", COS, "PEN"),
        ]),
        ("V-D2-2", "Circularidad y compras", [
            ("A2", "Contenido recuperado", "MR/MT", "MR: material secundario recuperado incorporado (kg); MT: material total (kg).", PROP, BEN, "PEN"),
            ("A4", "Energía renovable", "ER/ET", "ER: energía renovable verificable; ET: energía total, misma unidad.", PROP, BEN, "PEN"),
            ("A8", "Valorización de residuos", "RV/RS", "RV: residuos valorizados documentados (kg); RS: residuos generados (kg).", PROP, BEN, "PEN"),
            ("A9", "Compras ambientales", "CA/CT", "CA: compras con criterio ambiental verificado; CT: compras totales elegibles.", PROP, BEN, "PEN"),
        ]),
        ("V-D2-3", "Resultado ecológico", [
            ("A10", "Resultado ecológico neto", "Y_t − Y_0",
             "Y_t: indicador de estado ecológico actual; Y_0: línea base comparable; orientación positiva definida. "
             "No se infiere de reducción de emisiones ni de reciclaje.", "unidad del indicador", BEN, "SAL"),
        ]),
    ]),
    ("D3", "Valor social",
     "Trabajo digno, seguridad, bienestar, equidad y resultados comunitarios.",
     "Salvaguardas de derechos y creación de valor social verificable", [
        ("V-D3-1", "Trabajo digno y seguridad", [
            ("S1", "Empleo formal/estable", "EF/ET", "EF: empleos formales/estables; ET: empleo total.", PROP, BEN, "PEN"),
            ("S2", "Rotación voluntaria", "BV/EP", "BV: bajas voluntarias; EP: plantilla promedio.", PROP, COS, "PEN"),
            ("S3", "Brecha salarial ajustada", "(SR − SC)/SR",
             "SR: salario de referencia comparable; SC: salario del grupo evaluado, ajustado por jornada, cargo y antigüedad.",
             PROP, COS, "PEN"),
            ("S4", "Incidencia de accidentes", "AT×K/HT",
             "AT: accidentes registrables; HT: horas trabajadas; K: factor de escala declarado (p. ej., 200 000 h).",
             "accidentes/K h", COS, "SAL"),
            ("S5", "Bienestar laboral", "Σpuntajes/(N×Pmax)", "N: respuestas válidas; Pmax: puntuación máxima por respuesta.", PROP, BEN, "PEN"),
            ("S6", "Representación inclusiva", "GI/ET",
             "GI: integrantes del grupo pertinente; ET: plantilla. Interpretar según contexto (no siempre «más es mejor»).",
             PROP, OBJ, "PEN"),
            ("S7", "Cobertura de formación", "PF/PE", "PF: personas formadas; PE: personas elegibles.", PROP, BEN, "PEN"),
        ]),
        ("V-D3-2", "Cadena de valor y comunidad", [
            ("S8", "Debida diligencia social", "PR/PT", "PR: proveedores revisados; PT: proveedores pertinentes.", PROP, BEN, "SAL"),
            ("S9", "Resolución de quejas", "QR/QT", "QR: quejas resueltas en plazo; QT: quejas recibidas.", PROP, BEN, "SAL"),
            ("S10", "Participación de stakeholders", "PI/PE", "PI: participantes efectivos; PE: participantes elegibles.", PROP, BEN, "PEN"),
            ("S11", "Resultado comunitario", "ΔYC = YC_t − YC_0", "YC: indicador verificable de resultado comunitario y su línea base.", "unidad del indicador", BEN, "PEN"),
            ("S12", "Compras locales", "CL/CT", "CL: compras a proveedores locales; CT: compras totales elegibles.", PROP, BEN, "PEN"),
            ("S13", "Cobertura de proveedores críticos", "PCV/PCT", "PCV: proveedores críticos verificados; PCT: proveedores críticos totales.", PROP, BEN, "PEN"),
        ]),
    ]),
    ("D4", "Excelencia operacional",
     "Productividad física, calidad, continuidad, resiliencia y mejora (aporte de Ingeniería Industrial).",
     "Capacidad habilitadora y dimensión medible, sin duplicar D1", [
        ("V-D4-1", "Productividad y calidad", [
            ("O1", "Productividad del recurso crítico", "Q/R", "Q: salida conforme; R: recurso crítico (horas-persona, horas-máquina).", "unidades/recurso", BEN, "HAB"),
            ("O2", "Eficiencia de tiempo", "TV/TT", "TV: tiempo que agrega valor; TT: tiempo total del proceso.", PROP, BEN, "HAB"),
            ("O3", "OEE", "D×P×C", "D: disponibilidad; P: rendimiento; C: calidad, cada factor entre 0 y 1.", PROP, BEN, "HAB"),
            ("O4", "First Pass Yield", "UC1/UT", "UC1: unidades conformes a primera pasada; UT: unidades procesadas.", PROP, BEN, "HAB"),
            ("O5", "Fallas/reclamaciones", "NF/UT", "NF: fallas o reclamaciones válidas; UT: unidades o servicios.", PROP, COS, "HAB"),
        ]),
        ("V-D4-2", "Continuidad y resiliencia", [
            ("O6", "Tiempo de recuperación", "ΣTR/NE", "TR: tiempo hasta recuperar la operación; NE: eventos. Si NE = 0, no inferir cero.", "horas", COS, "HAB"),
            ("O7", "Continuidad probada", "PP/PT", "PP: procesos críticos con plan probado; PT: procesos críticos.", PROP, BEN, "HAB"),
            ("O8", "Respuesta al cambio", "ΣTC/NC", "TC: tiempo de respuesta; NC: cambios observados.", "horas", COS, "HAB"),
        ]),
        ("V-D4-3", "Mejora e innovación", [
            ("O9", "Innovación implementada", "II/IP", "II: innovaciones implementadas verificadas; IP: iniciativas propuestas.", PROP, BEN, "HAB"),
            ("O10", "Acciones de mejora cerradas", "AM/AT", "AM: acciones cerradas con eficacia; AT: acciones comprometidas vencidas.", PROP, BEN, "HAB"),
            ("O11", "Participación en mejora", "PM/PE", "PM: personas participantes; PE: personas elegibles.", PROP, BEN, "HAB"),
            ("O12", "Procesos controlados", "PC/PT", "PC: procesos estandarizados y controlados; PT: procesos pertinentes.", PROP, BEN, "HAB"),
        ]),
    ]),
]

# Matriz de correspondencia 17 (plataforma v0) → 42 (catálogo Fase 2)
CORRESPONDENCIA_V0 = [
    ("ECO_MARGEN", "Margen neto ajustado por externalidades", "E2", "Parcial: E2 no descuenta externalidades"),
    ("ECO_ROI", "Retorno sobre la inversión (ROI)", "E3", "Equivalente: se calculaba como ROA"),
    ("ECO_PE", "Ventas sobre el punto de equilibrio", "E1", "Transformación: E1 = 1 − PE/V"),
    ("ECO_REINV", "Utilidad reinvertida en capitales no financieros", "E7", "Parcial: E7 exige base B definida"),
    ("ECO_AUTON", "Autonomía financiera", None, "Excluido: sin correspondencia en el catálogo"),
    ("OPE_EFIC", "Eficiencia operativa global (OEE)", "O3", "Equivalente"),
    ("OPE_PROD", "Productividad por trabajador (USD/empleado)", None, "Excluido: medida financiera; D4 exige variables físicas (§2.9)"),
    ("OPE_COSTO", "Costos operativos sobre ventas", None, "Excluido: duplica D1 algebraicamente (§2.9)"),
    ("OPE_ENER", "Consumo energético por unidad producida", "A3", "Equivalente: pasa de D2 operativa a D2 ambiental"),
    ("SOC_INGRESO", "Incremento del ingreso de proveedores y trabajadores", "S11", "Parcial: S11 exige línea base comunitaria"),
    ("SOC_CADENA", "Participación del primer eslabón en el precio final", None, "Excluido: sin correspondencia; candidato a evaluación experta"),
    ("SOC_CAPAC", "Horas de capacitación por trabajador", "S7", "Parcial: S7 mide cobertura, no horas"),
    ("SOC_AUTON", "Autonomía del efecto social a 24 meses", None, "Excluido: sin fórmula verificable en el catálogo"),
    ("AMB_CIRC", "Tasa de circularidad efectiva", "A2", "Equivalente"),
    ("AMB_RESID", "Residuos no valorizados por unidad", "A7", "Parcial: A7 mide residuos totales por unidad"),
    ("AMB_CARB", "Balance neto de carbono (tCO₂e)", "A6", "Parcial: A6 es intensidad por unidad funcional"),
    ("AMB_AGUA", "Eficiencia en el uso del agua (L/unidad)", "A5", "Equivalente: cambia la unidad a m³/unidad"),
]
CODIGOS_V0 = [c[0] for c in CORRESPONDENCIA_V0]

ITEMS_DELPHI = [
    ("I01", "CLA", "Definición del constructo",
     "La definición de rentabilidad regenerativa (viabilidad económica, valor social, mejora ecológica neta "
     "verificable y capacidades operacionales, sin incumplir salvaguardas) es clara y no ambigua."),
    ("I02", "PER", "Arquitectura de cuatro dimensiones",
     "Las dimensiones D1 económica, D2 ambiental, D3 social y D4 operacional son pertinentes para evaluar "
     "emprendimientos de triple impacto."),
    ("I03", "COH", "Salvaguardas no compensatorias",
     "Exigir las condiciones G1–G5 (R = G1×G2×G3×G4×G5) antes de declarar «regeneración» es coherente con el constructo."),
    ("I04", "COH", "Agregación geométrica",
     "El índice IRR = Π(ε + (1−ε)·S)^α es apropiado como resultado descriptivo y no sustituye a las salvaguardas."),
    ("I05", "PER", "Indicadores económicos (E1–E7)",
     "Los indicadores E1–E7 capturan viabilidad, rentabilidad, liquidez y reinversión más allá del break-even."),
    ("I06", "PER", "Indicadores ambientales (A1–A10)",
     "Los indicadores A1–A10 distinguen presiones ambientales de resultados ecológicos netos."),
    ("I07", "PER", "Indicadores sociales (S1–S13)",
     "Los indicadores S1–S13 distinguen cumplimiento y prevención de daños de resultados sociales positivos."),
    ("I08", "PER", "Indicadores operacionales (O1–O12)",
     "Los indicadores O1–O12 miden la capacidad operacional sin duplicar los resultados financieros de D1."),
    ("I09", "CLA", "Fórmulas y normalización",
     "Las fórmulas de los KPI y la normalización z con referencias L/U son comprensibles y técnicamente correctas."),
    ("I10", "FAC", "Medibilidad y cobertura",
     "Un emprendimiento pequeño o mediano puede obtener la evidencia requerida y alcanzar la cobertura mínima por dimensión."),
    ("I11", "APL", "Aplicabilidad en Ecuador",
     "El framework es aplicable a emprendimientos ecuatorianos de los sectores agroindustrial, manufacturero y de servicios."),
    ("I12", "APL", "Utilidad para decidir",
     "Los resultados (clasificación a–e, cobertura, salvaguardas y cuello de botella) son útiles para la toma de decisiones."),
]


class Command(BaseCommand):
    help = "Carga el catálogo FRR 1.0 (4 dimensiones, 42 KPI candidatos) y el cuestionario Delphi."

    @transaction.atomic
    def handle(self, *args, **opciones):
        # Elimina el catálogo preliminar v0 (sus mediciones se reimportan con los nuevos códigos).
        eliminados, _ = Indicador.objects.filter(codigo__in=CODIGOS_V0).delete()
        Variable.objects.filter(indicadores__isnull=True).exclude(codigo__startswith="V-D").delete()

        mapa_v0 = {}
        for v0, nombre_v0, destino, decision in CORRESPONDENCIA_V0:
            if destino:
                mapa_v0.setdefault(destino, []).append(f"{v0} ({nombre_v0}): {decision}")

        for orden_d, (cod, nombre, desc, funcion, variables) in enumerate(ESTRUCTURA, start=1):
            dim, _ = Dimension.objects.update_or_create(
                codigo=cod,
                defaults={"nombre": nombre, "descripcion": desc, "funcion": funcion, "orden": orden_d},
            )
            for cod_var, nombre_var, kpis in variables:
                var, _ = Variable.objects.update_or_create(codigo=cod_var, defaults={"dimension": dim, "nombre": nombre_var})
                for orden, (codigo, nom, formula, comp, unidad, tipo, rol) in enumerate(kpis):
                    ind, creado = Indicador.objects.get_or_create(
                        codigo=codigo,
                        defaults={"variable": var, "nombre": nom, "formula": formula, "componentes": comp,
                                  "unidad": unidad, "tipo": tipo, "rol": rol, "orden": orden},
                    )
                    if not creado:
                        # No pisa referencias, pesos ni estado ajustados por la investigación.
                        for campo, valor in {"variable": var, "nombre": nom, "formula": formula,
                                             "componentes": comp, "unidad": unidad, "rol": rol, "orden": orden}.items():
                            setattr(ind, campo, valor)
                    ind.equivalencia_v0 = "; ".join(mapa_v0.get(codigo, []))
                    ind.save()

        # Pesos dimensionales iguales hasta la validación experta (§2.5: 30/25/22/23 no es consenso).
        Dimension.objects.filter(peso__in=[0.30, 0.25, 0.22, 0.23]).update(peso=0.25)
        Variable.objects.filter(indicadores__isnull=True).delete()
        ParametrosFRR.vigentes()

        for orden, (codigo, criterio, componente, enunciado) in enumerate(ITEMS_DELPHI):
            Item.objects.update_or_create(
                codigo=codigo,
                defaults={"criterio": criterio, "componente": componente, "enunciado": enunciado, "orden": orden},
            )

        self.stdout.write(self.style.SUCCESS(
            f"Framework FRR 1.0 cargado: {Dimension.objects.count()} dimensiones, "
            f"{Indicador.objects.count()} KPI candidatos, {Item.objects.count()} ítems Delphi"
            + (f" · eliminados {eliminados} registros del catálogo v0" if eliminados else "") + "."
        ))
