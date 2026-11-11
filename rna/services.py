"""Red neuronal del FRR (objetivo 3): carácter exploratorio.

Reglas de la especificación (Fase 2, §2.10.1 y §2.10.3):
* Las entradas son los KPI con referencias de normalización justificadas.
* La red solo predice si todas sus entradas están observadas: los faltantes nunca
  se reemplazan por cero.
* Las muestras simuladas sirven para explorar la capacidad del modelo de reproducir el
  FRR; no constituyen validación empírica. El entrenamiento con datos reales requiere
  una base depurada con D1–D4 suficientes.
"""

import random

from framework.models import Indicador
from framework.services import cargar_dimensiones, evaluar
from rna.mlp import MLP
from rna.models import ModeloRNA


class RNANoEntrenable(Exception):
    """El catálogo no permite generar etiquetas IRR (faltan referencias o cobertura)."""


def indicadores_entrada():
    """KPI puntuables (con L/U o T/H) y no excluidos, en orden estable."""
    return [
        ind
        for dim in cargar_dimensiones()
        for var in dim.variables.all()
        for ind in var.indicadores.all()
        if ind.estado != Indicador.EXCLUIDO and ind.puntuable
    ]


def diagnostico():
    """Qué falta para poder entrenar: dimensiones sin KPI puntuables."""
    entradas = indicadores_entrada()
    por_dim = {}
    for ind in entradas:
        por_dim.setdefault(ind.variable.dimension.codigo, []).append(ind.codigo)
    faltantes = [d.codigo for d in cargar_dimensiones() if d.codigo not in por_dim]
    return {"entradas": entradas, "por_dimension": por_dim, "dimensiones_sin_referencias": faltantes}


def _rango(ind):
    if ind.tipo == Indicador.OBJETIVO:
        return ind.ref_t - 1.35 * ind.ref_h, ind.ref_t + 1.35 * ind.ref_h
    ancho = ind.ref_u - ind.ref_l
    return ind.ref_l - 0.35 * ancho, ind.ref_u + 0.35 * ancho


def _presencia(dimensiones, solo=None):
    """KPI sin L/U: no puntúan, pero en la simulación se dan por registrados para la cobertura."""
    return {
        i.codigo: 1.0 for dim in dimensiones if solo is None or dim.codigo in solo
        for var in dim.variables.all() for i in var.indicadores.all()
        if i.estado != Indicador.EXCLUIDO and not i.puntuable
    }


def generar_dataset(n_muestras=600, semilla=7):
    """Escenarios simulados: KPI sorteados alrededor de sus referencias; etiqueta = IRR del FRR."""
    rng = random.Random(semilla)
    dimensiones = cargar_dimensiones()
    entradas = indicadores_entrada()
    presencia = _presencia(dimensiones)
    X, y = [], []
    for _ in range(n_muestras):
        mediciones = {ind.codigo: rng.uniform(*_rango(ind)) for ind in entradas}
        irr = evaluar({**mediciones, **presencia}, dimensiones)["irr"]
        if irr is None:
            raise RNANoEntrenable(
                "Los KPI con referencias no alcanzan la cobertura mínima en todas las dimensiones: "
                "el IRR no es calculable y no hay etiquetas para entrenar."
            )
        X.append([mediciones[ind.codigo] for ind in entradas])
        y.append(irr)
    return X, y, [ind.codigo for ind in entradas]


def entrenar(n_muestras=600, n_ocultas=8, epocas=300, lr=0.05, semilla=7):
    X, y, codigos = generar_dataset(n_muestras, semilla)
    red = MLP(len(codigos), n_ocultas=n_ocultas, semilla=semilla)
    resultado = red.entrenar(X, y, epocas=epocas, lr=lr, semilla=semilla)
    ModeloRNA.objects.update(activo=False)
    return ModeloRNA.objects.create(
        n_entradas=len(codigos), n_ocultas=n_ocultas, epocas=epocas, tasa_aprendizaje=lr,
        n_muestras=n_muestras, codigos_entrada=codigos, pesos=red.a_dict(),
        metricas=resultado["metricas"], historial=resultado["historial"], activo=True,
    )


def modelo_activo():
    """Modelo activo compatible con el catálogo vigente (sus entradas deben existir)."""
    modelo = ModeloRNA.objects.filter(activo=True).first()
    if modelo and not set(modelo.codigos_entrada) <= set(Indicador.objects.values_list("codigo", flat=True)):
        return None
    return modelo


def predecir(mediciones, modelo=None):
    """Predicción de la red frente al cálculo analítico; solo con todas las entradas observadas."""
    modelo = modelo or modelo_activo()
    if modelo is None:
        return None
    faltan = [c for c in modelo.codigos_entrada if mediciones.get(c) is None]
    if faltan:
        return {"modelo": modelo, "aplicable": False, "faltan": faltan}
    red = MLP.desde_dict(modelo.pesos)
    prediccion = red.predecir([float(mediciones[c]) for c in modelo.codigos_entrada])
    analitico = evaluar(mediciones)["irr"]
    return {
        "modelo": modelo, "aplicable": True,
        "prediccion": round(prediccion, 4),
        "analitico": analitico,
        "error": None if analitico is None else round(prediccion - analitico, 4),
    }


# ---------- Modo híbrido: D1 real + D2–D4 simulado (solo para entrenar y probar la red) ----------
# Las mediciones simuladas viven únicamente en memoria: nunca se guardan en las empresas
# ni se muestran como datos de ellas. El modelo queda etiquetado como híbrido/simulado.

DIMENSIONES_SIMULADAS = ("D2", "D3", "D4")


def _d1_reales(periodo, entradas_d1):
    """Valores D1 observados del período (E1 se deriva de ventas y costos); None si falta alguno."""
    obs = periodo.mediciones_dict()
    if obs.get("E1") is None and periodo.margen_seguridad is not None:
        obs["E1"] = periodo.margen_seguridad
    valores = {ind.codigo: obs.get(ind.codigo) for ind in entradas_d1}
    return None if any(v is None for v in valores.values()) else valores


def generar_dataset_hibrido(repeticiones=10, semilla=7):
    """Por cada empresa real: sus KPI D1 observados + `repeticiones` escenarios simulados de D2–D4.

    Los KPI de D2–D4 con L/U se sortean alrededor de sus referencias. Los que no tienen L/U
    no puntúan; en la simulación se dan por registrados para que la cobertura refleje un
    levantamiento completo. Etiqueta = IRR del FRR. Devuelve también el grupo (empresa)
    de cada fila para separar entrenamiento y prueba por empresa.
    """
    from emprendimientos.models import Periodo

    rng = random.Random(semilla)
    dimensiones = cargar_dimensiones()
    entradas = indicadores_entrada()
    entradas_d1 = [i for i in entradas if i.variable.dimension.codigo not in DIMENSIONES_SIMULADAS]
    entradas_sim = [i for i in entradas if i.variable.dimension.codigo in DIMENSIONES_SIMULADAS]
    presencia = _presencia(dimensiones, DIMENSIONES_SIMULADAS)
    if not entradas_sim:
        raise RNANoEntrenable("D2–D4 no tienen KPI con referencias L/U para simular.")
    X, y, grupos, omitidas = [], [], [], 0
    for periodo in Periodo.objects.filter(emprendimiento__isnull=False).prefetch_related("mediciones__indicador"):
        d1 = _d1_reales(periodo, entradas_d1)
        if d1 is None:
            omitidas += 1
            continue
        for _ in range(repeticiones):
            sim = {i.codigo: rng.uniform(*_rango(i)) for i in entradas_sim}
            irr = evaluar({**d1, **sim, **presencia}, dimensiones)["irr"]
            if irr is None:
                raise RNANoEntrenable("El IRR no es calculable ni con D2–D4 simulados: revise la cobertura de D1.")
            X.append([{**d1, **sim}[i.codigo] for i in entradas])
            y.append(irr)
            grupos.append(periodo.pk)
    if not X:
        raise RNANoEntrenable("Ninguna empresa tiene completos sus KPI económicos (D1) observados.")
    return X, y, grupos, [i.codigo for i in entradas], omitidas


def entrenar_hibrido(repeticiones=10, n_ocultas=8, epocas=300, lr=0.05, semilla=7, prueba=0.2):
    """Entrena con D1 real + D2–D4 simulado y evalúa con empresas que la red no vio."""
    X, y, grupos, codigos, omitidas = generar_dataset_hibrido(repeticiones, semilla)
    empresas = sorted(set(grupos))
    random.Random(semilla).shuffle(empresas)
    reservadas = set(empresas[: max(1, int(len(empresas) * prueba))])
    ent = [(x, t) for x, t, g in zip(X, y, grupos) if g not in reservadas]
    pru = [(x, t) for x, t, g in zip(X, y, grupos) if g in reservadas]
    red = MLP(len(codigos), n_ocultas=n_ocultas, semilla=semilla)
    resultado = red.entrenar([x for x, _ in ent], [t for _, t in ent], epocas=epocas, lr=lr, semilla=semilla)
    pred = [red.predecir(x) for x, _ in pru]
    reales = [t for _, t in pru]
    media = sum(reales) / len(reales)
    ss_res = sum((p - t) ** 2 for p, t in zip(pred, reales))
    ss_tot = sum((t - media) ** 2 for t in reales) or 1e-12
    metricas = {
        **resultado["metricas"],
        "origen": "híbrido: D1 real + D2–D4 simulado",
        "empresas_entrenamiento": len(empresas) - len(reservadas),
        "empresas_prueba": len(reservadas),
        "empresas_omitidas_d1_incompleto": omitidas,
        "r2_empresas_no_vistas": round(1 - ss_res / ss_tot, 4),
        "mae_empresas_no_vistas": round(sum(abs(p - t) for p, t in zip(pred, reales)) / len(reales), 4),
        "prueba": [[round(p, 4), round(t, 4)] for p, t in zip(pred, reales)],  # para las gráficas
    }
    ModeloRNA.objects.update(activo=False)
    return ModeloRNA.objects.create(
        nombre="MLP híbrido (D1 real + D2–D4 simulado)", n_entradas=len(codigos), n_ocultas=n_ocultas,
        epocas=epocas, tasa_aprendizaje=lr, n_muestras=len(X), codigos_entrada=codigos, pesos=red.a_dict(),
        metricas=metricas, historial=resultado["historial"], activo=True,
    )
