"""Simulación de escenarios y análisis de sensibilidad."""

from framework.models import Dimension
from framework.services import evaluar

FACTORES_POR_DEFECTO = {"OPT": 1.15, "ESP": 1.00, "PES": 0.85}


def _mejorar(valor, factor, ind):
    """Escala un valor en el sentido de "mejor" (factor > 1) o "peor" (factor < 1).

    Se trabaja sobre el desempeño con signo: positivo cuando el valor ya es
    favorable. Así un margen negativo mejora acercándose a cero y una captura
    neta de carbono (valor negativo en un indicador de "menor es mejor") mejora
    capturando más, en lugar de invertirse el sentido del escenario.
    """
    if not factor or factor <= 0:
        return valor
    desempeno = -valor if ind.direccion == ind.MENOR_MEJOR else valor
    desempeno = desempeno * factor if desempeno > 0 else desempeno / factor
    return -desempeno if ind.direccion == ind.MENOR_MEJOR else desempeno


def _aplicar_factor(mediciones, factor, indicadores):
    """Aplica el factor respetando la dirección del indicador.

    En un indicador de "menor es mejor" (residuos, consumo energético) un
    escenario optimista implica reducir el valor, no aumentarlo.
    """
    ajustadas = {}
    for codigo, valor in mediciones.items():
        ind = indicadores.get(codigo)
        if ind is None or valor is None:
            ajustadas[codigo] = valor
            continue
        ajustadas[codigo] = _mejorar(valor, factor, ind)
    return ajustadas


def _indice_indicadores(dimensiones):
    return {
        ind.codigo: ind
        for dim in dimensiones
        for var in dim.variables.all()
        for ind in var.indicadores.all()
    }


def simular(mediciones, factores=None):
    """Corre los tres escenarios y devuelve sus resultados."""
    factores = factores or FACTORES_POR_DEFECTO
    dimensiones = list(Dimension.objects.prefetch_related("variables__indicadores").all())
    indicadores = _indice_indicadores(dimensiones)

    resultados = []
    for tipo in ("OPT", "ESP", "PES"):
        factor = float(factores.get(tipo, FACTORES_POR_DEFECTO[tipo]))
        ajustadas = _aplicar_factor(mediciones, factor, indicadores)
        res = evaluar(ajustadas, dimensiones)
        resultados.append({"tipo": tipo, "factor": factor, "resultado": res})
    return resultados


def sensibilidad(mediciones, delta=0.10):
    """Análisis de sensibilidad: efecto sobre el IRR de variar ±delta cada dimensión.

    Devuelve las dimensiones ordenadas por amplitud del efecto, que es la
    medida de cuáles variables gobiernan el comportamiento del framework.
    """
    dimensiones = list(Dimension.objects.prefetch_related("variables__indicadores").all())
    indicadores = _indice_indicadores(dimensiones)
    base = evaluar(mediciones, dimensiones)

    filas = []
    for dim in dimensiones:
        codigos = {
            ind.codigo
            for var in dim.variables.all()
            for ind in var.indicadores.all()
        }
        arriba = dict(mediciones)
        abajo = dict(mediciones)
        for codigo in codigos:
            if mediciones.get(codigo) is None:
                continue
            ind = indicadores[codigo]
            arriba[codigo] = _mejorar(mediciones[codigo], 1 + delta, ind)
            abajo[codigo] = _mejorar(mediciones[codigo], 1 / (1 + delta), ind)

        irr_arriba = evaluar(arriba, dimensiones)["irr"]
        irr_abajo = evaluar(abajo, dimensiones)["irr"]
        filas.append(
            {
                "dimension": dim,
                "irr_menos": round(irr_abajo, 4),
                "irr_base": base["irr"],
                "irr_mas": round(irr_arriba, 4),
                "amplitud": round(irr_arriba - irr_abajo, 4),
            }
        )

    filas.sort(key=lambda f: -f["amplitud"])
    return base, filas
