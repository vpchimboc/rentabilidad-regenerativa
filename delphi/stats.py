"""Estadística del método Delphi: IVC, S-CVI y W de Kendall.

Implementado en Python puro. Las fórmulas son las estándar en validación de
instrumentos (Lawshe/Polit-Beck para el IVC; Kendall 1939 con corrección por
empates para W).
"""

UMBRAL_IVC = 0.80          # Polit & Beck: I-CVI aceptable con 3+ expertos
UMBRAL_W = 0.50            # Concordancia moderada o superior


def ivc_item(valores):
    """Índice de Validez de Contenido de un ítem.

    Proporción de expertos que lo califican como pertinente (4 o 5 en Likert).
    """
    if not valores:
        return 0.0
    return sum(1 for v in valores if v >= 4) / len(valores)


def _rangos_con_empates(valores):
    """Rangos promediados: a los empates se les asigna el rango medio."""
    indexados = sorted(range(len(valores)), key=lambda i: valores[i])
    rangos = [0.0] * len(valores)
    i = 0
    empates = []
    while i < len(indexados):
        j = i
        while j + 1 < len(indexados) and valores[indexados[j + 1]] == valores[indexados[i]]:
            j += 1
        promedio = (i + j) / 2 + 1
        for k in range(i, j + 1):
            rangos[indexados[k]] = promedio
        if j > i:
            empates.append(j - i + 1)
        i = j + 1
    return rangos, empates


def kendall_w(matriz):
    """W de Kendall con corrección por empates.

    `matriz` es una lista por experto, cada una con sus valoraciones sobre los
    mismos ítems y en el mismo orden.

    W = 12·S / (m²·(n³ − n) − m·ΣT)
    """
    m = len(matriz)                       # número de jueces
    if m < 2:
        return {"w": 0.0, "chi2": 0.0, "gl": 0, "m": m, "n": 0}
    n = len(matriz[0])                    # número de ítems
    if n < 2:
        return {"w": 0.0, "chi2": 0.0, "gl": 0, "m": m, "n": n}

    suma_rangos = [0.0] * n
    correccion = 0.0
    for valoraciones in matriz:
        rangos, empates = _rangos_con_empates(valoraciones)
        for i in range(n):
            suma_rangos[i] += rangos[i]
        correccion += sum(t ** 3 - t for t in empates)

    media = sum(suma_rangos) / n
    s = sum((r - media) ** 2 for r in suma_rangos)
    denominador = (m ** 2) * (n ** 3 - n) - m * correccion
    w = round((12 * s / denominador) if denominador > 0 else 0.0, 4)
    # El chi² se deriva del W ya redondeado para que ambos valores sean
    # aritméticamente coherentes en el informe que ve el usuario.
    chi2 = round(m * (n - 1) * w, 4)
    return {"w": w, "chi2": chi2, "gl": n - 1, "m": m, "n": n}


def interpretar_w(w):
    if w < 0.20:
        return "Concordancia muy débil"
    if w < 0.40:
        return "Concordancia débil"
    if w < 0.60:
        return "Concordancia moderada"
    if w < 0.80:
        return "Concordancia fuerte"
    return "Concordancia muy fuerte"


def analizar_ronda(respuestas):
    """Consolida una ronda a partir de sus respuestas.

    `respuestas` es un iterable de objetos con .experto_id, .item_id y .valor.
    """
    por_item = {}
    por_experto = {}
    for r in respuestas:
        por_item.setdefault(r.item_id, []).append(r.valor)
        por_experto.setdefault(r.experto_id, {})[r.item_id] = r.valor

    items_ordenados = sorted(por_item.keys())
    detalle_items = []
    for item_id in items_ordenados:
        valores = por_item[item_id]
        media = sum(valores) / len(valores)
        varianza = sum((v - media) ** 2 for v in valores) / len(valores)
        detalle_items.append(
            {
                "item_id": item_id,
                "n": len(valores),
                "media": round(media, 2),
                "desviacion": round(varianza ** 0.5, 2),
                "minimo": min(valores),
                "maximo": max(valores),
                "ivc": round(ivc_item(valores), 3),
                "aprobado": ivc_item(valores) >= UMBRAL_IVC,
            }
        )

    s_cvi = (
        sum(d["ivc"] for d in detalle_items) / len(detalle_items) if detalle_items else 0.0
    )

    matriz = [
        [por_experto[e][i] for i in items_ordenados if i in por_experto[e]]
        for e in sorted(por_experto)
    ]
    matriz = [fila for fila in matriz if len(fila) == len(items_ordenados)]
    kw = kendall_w(matriz) if matriz else {"w": 0.0, "chi2": 0.0, "gl": 0, "m": 0, "n": 0}

    # El W de Kendall mide concordancia en el ORDENAMIENTO de los ítems. Cuando los
    # expertos coinciden en calificar casi todo con el máximo, los rangos se vuelven
    # empates masivos y el W cae aunque el acuerdo sea total: es el efecto techo de la
    # escala Likert. En ese caso la baja dispersión es la evidencia válida de consenso,
    # y así se declara de forma explícita en lugar de reportar un falso desacuerdo.
    dispersion_baja = bool(detalle_items) and all(
        d["desviacion"] <= 0.8 and d["media"] >= 4.0 for d in detalle_items
    )
    consenso_por_w = kw["w"] >= UMBRAL_W
    consenso = s_cvi >= UMBRAL_IVC and (consenso_por_w or dispersion_baja)

    if consenso_por_w:
        criterio = "W de Kendall por encima del umbral"
    elif dispersion_baja:
        criterio = ("Efecto techo de la escala: el W pierde interpretabilidad con empates "
                    "masivos, pero la dispersión entre expertos es mínima (σ ≤ 0,8 en todos "
                    "los ítems) y el S-CVI es suficiente")
    else:
        criterio = "No se alcanza concordancia suficiente"

    return {
        "items": detalle_items,
        "s_cvi": round(s_cvi, 3),
        "kendall": kw,
        "interpretacion_w": interpretar_w(kw["w"]),
        "dispersion_baja": dispersion_baja,
        "criterio_consenso": criterio,
        "consenso": consenso,
        "items_a_revisar": [d["item_id"] for d in detalle_items if not d["aprobado"]],
    }
