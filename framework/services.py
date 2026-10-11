"""Motor de cálculo del Índice de Rentabilidad Regenerativa (IRR).

Reglas de agregación
--------------------
1. Cada indicador se traduce a la escala 0–4 mediante sus cortes.
2. Dentro de una dimensión los indicadores se promedian de forma ponderada
   (aritmética): son sustituibles entre sí porque miden el mismo capital.
3. Entre dimensiones la agregación es GEOMÉTRICA ponderada: no compensatoria.
   Si una dimensión colapsa (nivel 0), el índice se anula.
4. Regla de umbral: ningún emprendimiento califica como regenerativo si su
   mínimo dimensional discreto es menor a 3.
"""

import math

from framework.models import NIVELES, Dimension

UMBRAL_CALIFICACION = 3


def _discreto(nivel):
    """Piso del nivel continuo, tolerante al ruido de coma flotante (2.9999999 → 3)."""
    return int(min(4, max(0, math.floor(nivel + 1e-9))))


def _pesos_normalizados(dimensiones):
    total = sum(d.peso for d in dimensiones) or 1.0
    return {d.id: d.peso / total for d in dimensiones}


def evaluar(mediciones, dimensiones=None):
    """Calcula el IRR a partir de un dict {codigo_indicador: valor}.

    Devuelve un diccionario con el detalle completo del cálculo, apto para
    renderizar en pantalla, guardar como JSON o alimentar la RNA.
    """
    if dimensiones is None:
        dimensiones = list(
            Dimension.objects.prefetch_related("variables__indicadores").all()
        )

    # Solo agregan las dimensiones con al menos una medición. Una dimensión sin
    # datos no es una dimensión degenerativa: se informa como faltante y sus
    # pesos se redistribuyen entre las medidas, pero el caso no puede calificar.
    medidas = [
        dim for dim in dimensiones
        if any(
            mediciones.get(ind.codigo) is not None
            for var in dim.variables.all() for ind in var.indicadores.all()
        )
    ]
    pesos = _pesos_normalizados(medidas)
    detalle_dimensiones = []
    producto = 1.0
    suma_aritmetica = 0.0
    hay_datos = bool(medidas)

    for dim in dimensiones:
        indicadores = [
            ind for var in dim.variables.all() for ind in var.indicadores.all()
        ]
        filas, suma_pesos, suma_niveles = [], 0.0, 0.0
        for ind in indicadores:
            if ind.codigo not in mediciones or mediciones[ind.codigo] is None:
                filas.append({"indicador": ind, "valor": None, "nivel": None})
                continue
            valor = float(mediciones[ind.codigo])
            nivel_c = ind.nivel_continuo(valor)
            filas.append(
                {
                    "indicador": ind,
                    "valor": valor,
                    "nivel": round(nivel_c, 2),
                    "nivel_discreto": _discreto(nivel_c),
                    "etiqueta": NIVELES[_discreto(nivel_c)],
                }
            )
            suma_pesos += ind.peso
            suma_niveles += ind.peso * nivel_c

        sin_dato = dim.id not in pesos
        nivel_dim = (suma_niveles / suma_pesos) if suma_pesos else 0.0
        w = pesos.get(dim.id, 0.0)
        ratio = nivel_dim / 4.0
        if not sin_dato:
            producto *= ratio ** w if ratio > 0 else 0.0
            suma_aritmetica += w * ratio

        detalle_dimensiones.append(
            {
                "dimension": dim,
                "sin_dato": sin_dato,
                "peso": round(w, 4),
                "nivel": round(nivel_dim, 3),
                "nivel_discreto": _discreto(nivel_dim),
                "etiqueta": NIVELES[_discreto(nivel_dim)],
                "ratio": round(ratio, 4),
                "aporte": round(ratio ** w, 4) if ratio > 0 and not sin_dato else 0.0,
                "filas": filas,
            }
        )

    con_dato = [d for d in detalle_dimensiones if not d["sin_dato"]]
    sin_dato = [d["dimension"].codigo for d in detalle_dimensiones if d["sin_dato"]]
    irr = producto if hay_datos else 0.0
    minimo = min((d["nivel_discreto"] for d in con_dato), default=0)
    cuello = min(con_dato, key=lambda d: d["nivel"]) if con_dato else None

    if not hay_datos:
        veredicto, clase = "Sin datos suficientes", "vacio"
    elif minimo == 0:
        veredicto, clase = "Índice anulado — dimensión degenerativa", "l0"
    elif sin_dato:
        veredicto, clase = "Evaluación incompleta — dimensiones sin dato", "vacio"
    elif minimo < UMBRAL_CALIFICACION:
        veredicto, clase = "No califica como regenerativo", "l2"
    elif minimo == 3:
        veredicto, clase = "Regenerativo verificable", "l3"
    else:
        veredicto, clase = "Regenerativo pleno", "l4"

    return {
        "irr": round(irr, 4),
        "media_aritmetica": round(suma_aritmetica, 4),
        "penalizacion": round(irr - suma_aritmetica, 4),
        "minimo_dimensional": minimo,
        "veredicto": veredicto,
        "clase": clase,
        "cuello_de_botella": cuello["dimension"].codigo if cuello else None,
        "incompleto": hay_datos and bool(sin_dato),
        "dimensiones_sin_dato": sin_dato,
        "dimensiones": detalle_dimensiones,
    }


def elasticidad(mediciones, dimensiones=None):
    """Ganancia de IRR al subir un nivel completo cada dimensión (fase 4).

    Responde a la pregunta operativa: ¿dónde conviene intervenir primero?
    """
    base = evaluar(mediciones, dimensiones)
    resultados = []
    for det in base["dimensiones"]:
        nivel_actual = det["nivel"]
        if det["sin_dato"]:
            resultados.append({"dimension": det["dimension"], "ganancia": None, "nivel_actual": None})
            continue
        if nivel_actual >= 4:
            resultados.append({"dimension": det["dimension"], "ganancia": None, "nivel_actual": 4.0})
            continue
        niveles = {d["dimension"].codigo: d["nivel"] for d in base["dimensiones"]}
        niveles[det["dimension"].codigo] = min(4.0, nivel_actual + 1.0)
        irr_alt = _irr_desde_niveles(niveles, base["dimensiones"])
        resultados.append(
            {
                "dimension": det["dimension"],
                "nivel_actual": round(nivel_actual, 2),
                "nivel_objetivo": round(min(4.0, nivel_actual + 1.0), 2),
                "ganancia": round(irr_alt - base["irr"], 4),
                "es_cuello": det["dimension"].codigo == base["cuello_de_botella"],
            }
        )
    resultados.sort(key=lambda r: (r["ganancia"] is None, -(r["ganancia"] or 0)))
    return base, resultados


def _irr_desde_niveles(niveles_por_codigo, detalle_dimensiones):
    """IRR recalculado a partir de niveles de dimensión ya conocidos."""
    producto = 1.0
    for det in detalle_dimensiones:
        if det["sin_dato"]:
            continue
        nivel = niveles_por_codigo[det["dimension"].codigo]
        ratio = nivel / 4.0
        producto *= ratio ** det["peso"] if ratio > 0 else 0.0
    return producto


def irr_desde_niveles(niveles_por_codigo, dimensiones=None):
    """Versión pública: recibe {codigo_dimension: nivel 0-4} y devuelve el IRR."""
    if dimensiones is None:
        dimensiones = list(Dimension.objects.all())
    pesos = _pesos_normalizados(dimensiones)
    producto = 1.0
    for dim in dimensiones:
        ratio = niveles_por_codigo.get(dim.codigo, 0.0) / 4.0
        producto *= ratio ** pesos[dim.id] if ratio > 0 else 0.0
    return producto
