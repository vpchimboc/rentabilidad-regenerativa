"""Simulación de escenarios y análisis de sensibilidad del FRR (objetivo 4, Fase 4).

Los escenarios son declarados («qué pasaría si…») sobre las mediciones reales de un
período; no constituyen evidencia de validación (§2.10.3).
"""

from framework.models import Indicador
from framework.services import _agregar, cargar_dimensiones, evaluar

FACTORES_POR_DEFECTO = {"OPT": 1.15, "ESP": 1.00, "PES": 0.85}


def _mejorar(valor, factor, ind):
    """Mueve un valor en el sentido de «mejor» (factor > 1) o «peor» (factor < 1).

    Beneficio: aumenta el desempeño; costo: lo reduce; objetivo: lo acerca o aleja de T.
    Se trabaja sobre el desempeño con signo para que los valores negativos (pérdidas,
    resultados netos) mejoren en la dirección correcta.
    """
    if not factor or factor <= 0:
        return valor
    if ind.tipo == Indicador.OBJETIVO:
        if ind.ref_t is None:
            return valor
        return ind.ref_t + (valor - ind.ref_t) / factor
    desempeno = -valor if ind.tipo == Indicador.COSTO else valor
    desempeno = desempeno * factor if desempeno > 0 else desempeno / factor
    return -desempeno if ind.tipo == Indicador.COSTO else desempeno


def _indice_indicadores(dimensiones):
    return {ind.codigo: ind for dim in dimensiones for var in dim.variables.all() for ind in var.indicadores.all()}


def _aplicar_factor(mediciones, factor, indicadores):
    return {
        codigo: (_mejorar(valor, factor, indicadores[codigo]) if codigo in indicadores and valor is not None else valor)
        for codigo, valor in mediciones.items()
    }


def simular(mediciones, factores=None, **contexto):
    factores = factores or FACTORES_POR_DEFECTO
    dimensiones = cargar_dimensiones()
    indicadores = _indice_indicadores(dimensiones)
    resultados = []
    for tipo in ("OPT", "ESP", "PES"):
        factor = float(factores.get(tipo, FACTORES_POR_DEFECTO[tipo]))
        res = evaluar(_aplicar_factor(mediciones, factor, indicadores), dimensiones, **contexto)
        resultados.append({"tipo": tipo, "factor": factor, "resultado": res})
    return resultados


def sensibilidad(mediciones, delta=0.10, **contexto):
    """Sensibilidad del IRR ante el desempeño de cada dimensión (±delta en sus KPI)."""
    dimensiones = cargar_dimensiones()
    indicadores = _indice_indicadores(dimensiones)
    base = evaluar(mediciones, dimensiones, **contexto)
    filas = []
    for dim in dimensiones:
        codigos = {i.codigo for v in dim.variables.all() for i in v.indicadores.all()}
        arriba, abajo = dict(mediciones), dict(mediciones)
        for codigo in codigos & set(mediciones):
            arriba[codigo] = _mejorar(mediciones[codigo], 1 + delta, indicadores[codigo])
            abajo[codigo] = _mejorar(mediciones[codigo], 1 / (1 + delta), indicadores[codigo])
        irr_mas = evaluar(arriba, dimensiones, **contexto)["irr"]
        irr_menos = evaluar(abajo, dimensiones, **contexto)["irr"]
        amplitud = (irr_mas - irr_menos) if irr_mas is not None and irr_menos is not None else None
        filas.append({"dimension": dim, "irr_menos": irr_menos, "irr_base": base["irr"],
                      "irr_mas": irr_mas, "amplitud": None if amplitud is None else round(amplitud, 4)})
    filas.sort(key=lambda f: (f["amplitud"] is None, -(f["amplitud"] or 0)))
    return base, filas


def sensibilidad_pesos(base, variacion=0.05):
    """Sensibilidad del IRR ante cambios de los pesos α (Fase 4: pesos y umbrales)."""
    if not base["irr_calculable"]:
        return []
    puntajes = {d["dimension"].codigo: d["S"] for d in base["dimensiones"]}
    alfas = {d["dimension"].codigo: d["alfa"] for d in base["dimensiones"]}
    filas = []
    for cod in alfas:
        resultado = {}
        for signo in (-1, 1):
            nuevos = dict(alfas)
            nuevos[cod] = max(0.0, alfas[cod] + signo * variacion)
            total = sum(nuevos.values()) or 1.0
            nuevos = {k: v / total for k, v in nuevos.items()}
            resultado[signo], _ = _agregar(puntajes, nuevos, base["epsilon"])
        filas.append({"codigo": cod, "irr_menos": round(resultado[-1], 4), "irr_mas": round(resultado[1], 4),
                      "amplitud": round(abs(resultado[1] - resultado[-1]), 4)})
    return sorted(filas, key=lambda f: -f["amplitud"])

