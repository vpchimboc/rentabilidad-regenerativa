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


def generar_dataset(n_muestras=600, semilla=7):
    """Escenarios simulados: KPI sorteados alrededor de sus referencias; etiqueta = IRR del FRR."""
    rng = random.Random(semilla)
    dimensiones = cargar_dimensiones()
    entradas = indicadores_entrada()
    X, y = [], []
    for _ in range(n_muestras):
        mediciones = {ind.codigo: rng.uniform(*_rango(ind)) for ind in entradas}
        irr = evaluar(mediciones, dimensiones)["irr"]
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
