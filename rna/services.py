"""Generación de datos, entrenamiento y predicción con la RNA."""

import random

from framework.models import Dimension
from framework.services import evaluar
from rna.mlp import MLP
from rna.models import ModeloRNA


def indicadores_entrada():
    """Indicadores marcados como entrada de la red, en orden estable."""
    return [
        ind
        for dim in Dimension.objects.prefetch_related("variables__indicadores").all()
        for var in dim.variables.all()
        for ind in var.indicadores.all()
        if ind.es_entrada_rna
    ]


def generar_dataset(n_muestras=600, semilla=7):
    """Escenarios simulados derivados del Framework.

    El protocolo prevé expresamente esta vía: "en caso de no disponer de
    grandes volúmenes de datos se utilizarán escenarios simulados derivados
    del Framework propuesto". Cada muestra es un emprendimiento sintético cuyos
    indicadores se sortean dentro de rangos plausibles y cuya etiqueta es el
    IRR calculado por el motor de agregación.
    """
    rng = random.Random(semilla)
    dimensiones = list(Dimension.objects.prefetch_related("variables__indicadores").all())
    entradas = indicadores_entrada()

    X, y = [], []
    for _ in range(n_muestras):
        mediciones = {}
        for ind in entradas:
            bajo, alto = min(ind.cortes), max(ind.cortes)
            rango = (alto - bajo) or 1.0
            valor = rng.uniform(bajo - 0.35 * rango, alto + 0.35 * rango)
            mediciones[ind.codigo] = valor
        resultado = evaluar(mediciones, dimensiones)
        X.append([mediciones[ind.codigo] for ind in entradas])
        y.append(resultado["irr"])
    return X, y, [ind.codigo for ind in entradas]


def entrenar(n_muestras=600, n_ocultas=8, epocas=300, lr=0.05, semilla=7):
    X, y, codigos = generar_dataset(n_muestras, semilla)
    red = MLP(len(codigos), n_ocultas=n_ocultas, semilla=semilla)
    resultado = red.entrenar(X, y, epocas=epocas, lr=lr, semilla=semilla)

    ModeloRNA.objects.update(activo=False)
    modelo = ModeloRNA.objects.create(
        n_entradas=len(codigos),
        n_ocultas=n_ocultas,
        epocas=epocas,
        tasa_aprendizaje=lr,
        n_muestras=n_muestras,
        codigos_entrada=codigos,
        pesos=red.a_dict(),
        metricas=resultado["metricas"],
        historial=resultado["historial"],
        activo=True,
    )
    return modelo


def modelo_activo():
    return ModeloRNA.objects.filter(activo=True).first()


def predecir(mediciones, modelo=None):
    """Predice el IRR con la red y lo compara contra el cálculo analítico."""
    modelo = modelo or modelo_activo()
    if modelo is None:
        return None
    x = [float(mediciones.get(codigo, 0.0) or 0.0) for codigo in modelo.codigos_entrada]
    red = MLP.desde_dict(modelo.pesos)
    prediccion = red.predecir(x)
    analitico = evaluar(mediciones)["irr"]
    return {
        "prediccion": round(prediccion, 4),
        "analitico": round(analitico, 4),
        "error": round(prediccion - analitico, 4),
        "modelo": modelo,
    }
