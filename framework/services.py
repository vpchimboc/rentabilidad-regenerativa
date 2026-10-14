"""Motor de cálculo del FRR 1.0 (especificación Fase 2, §2.4–2.5 y §2.12.2).

Dos niveles:
1. Condiciones habilitantes y salvaguardas G1–G5 → R = G1×G2×G3×G4×G5.
   Si alguna Gk es desconocida, R es «indeterminado» (nunca 0 por falta de datos).
2. Puntuaciones descriptivas, solo con cobertura suficiente:
   z      = normalización acotada [0, 1] con referencias L/U o T/H del indicador
   S(d)   = Σ w·z / Σ w            (KPI observados y puntuables de la dimensión d)
   C(d)   = Σ w(observados) / Σ w(aplicables)   (NA documentados fuera del denominador)
   IRR    = Π (ε + (1−ε)·S(d))^α(d)              (Σ α = 1)
   IRR₀   = Π S(d)^α(d)                          (alternativa sin suavizado)
El índice solo se publica junto con G1–G5 y la cobertura C.

Clasificación (§2.2): (a) información insuficiente · (b) inviabilidad económica ·
(c) viabilidad sin evidencia regenerativa · (d) desempeño sostenible o de transición ·
(e) regeneración verificable.
"""

from framework.models import Dimension, Indicador, ParametrosFRR

CLASIFICACIONES = {
    "a": ("Información insuficiente", "vacio"),
    "b": ("Inviabilidad económica", "l0"),
    "c": ("Viabilidad sin evidencia regenerativa", "l2"),
    "d": ("Desempeño sostenible o de transición", "l3"),
    "e": ("Regeneración verificable", "l4"),
}
NOMBRES_G = {
    "G1": "Viabilidad económica",
    "G2": "No daño social crítico",
    "G3": "Resultado ambiental positivo",
    "G4": "Trazabilidad y cobertura",
    "G5": "Persistencia temporal",
}
INCREMENTO_ELASTICIDAD = 0.10


def cargar_dimensiones():
    return list(Dimension.objects.prefetch_related("variables__indicadores").all())


def _indicadores_aplicables(dim):
    """KPI de la versión operativa; si aún no hay selección, todos los candidatos no excluidos."""
    todos = [i for v in dim.variables.all() for i in v.indicadores.all() if i.estado != Indicador.EXCLUIDO]
    activos = [i for i in todos if i.estado == Indicador.ACTIVO]
    return activos or todos


def _alfas(dimensiones):
    total = sum(max(d.peso, 0) for d in dimensiones) or 1.0
    return {d.codigo: max(d.peso, 0) / total for d in dimensiones}


def _agregar(puntajes, alfas, epsilon):
    """IRR suavizado e IRR₀ a partir de {código: S}. None si falta alguna dimensión."""
    if any(s is None for s in puntajes.values()):
        return None, None
    irr, irr0 = 1.0, 1.0
    for cod, s in puntajes.items():
        a = alfas[cod]
        irr *= (epsilon + (1 - epsilon) * s) ** a
        irr0 *= (s ** a) if s > 0 else (0.0 if a > 0 else 1.0)
    return irr, irr0


def _g(valor, origen, detalle):
    return {"valor": valor, "origen": origen, "detalle": detalle}


def evaluar(mediciones, dimensiones=None, *, periodo=None, no_aplicables=(), salvaguardas=None, parametros=None):
    """Evalúa un conjunto de mediciones {código KPI: valor observado}.

    `periodo` (opcional) aporta ventas y costos para G1 (E1), las fuentes para G4 y
    el historial para G5. `salvaguardas` son verificaciones manuales {G: 0/1}.
    """
    dimensiones = dimensiones if dimensiones is not None else cargar_dimensiones()
    parametros = parametros or ParametrosFRR.vigentes()
    eps, cmin = parametros.epsilon, parametros.cobertura_minima
    alfas = _alfas(dimensiones)
    no_aplicables = set(no_aplicables)
    manuales = dict(salvaguardas or {})
    derivados = set()
    if periodo is not None:
        no_aplicables |= periodo.no_aplicables()
        manuales = {**periodo.salvaguardas_manuales(), **manuales}
        # E1 = (V − PE)/V depende solo de ventas y costos del período: se deriva si no se registró.
        if mediciones.get("E1") is None and periodo.margen_seguridad is not None:
            mediciones = {**mediciones, "E1": periodo.margen_seguridad}
            derivados.add("E1")

    detalle_dims, puntajes = [], {}
    for dim in dimensiones:
        aplicables = [i for i in _indicadores_aplicables(dim) if i.codigo not in no_aplicables]
        filas, peso_obs, peso_apl, suma_wz, suma_w = [], 0.0, 0.0, 0.0, 0.0
        for ind in aplicables:
            x = mediciones.get(ind.codigo)
            peso_apl += ind.peso
            z = ind.normalizar(x) if x is not None else None
            if x is not None:
                peso_obs += ind.peso
            if z is not None:
                suma_wz += ind.peso * z
                suma_w += ind.peso
            filas.append({
                "indicador": ind, "valor": x, "z": z,
                "estado": "OBS" if x is not None else "ND",
                "puntuable": ind.puntuable, "derivado": ind.codigo in derivados,
            })
        for codigo in sorted(no_aplicables):
            ind = next((i for v in dim.variables.all() for i in v.indicadores.all() if i.codigo == codigo), None)
            if ind is not None:
                filas.append({"indicador": ind, "valor": None, "z": None, "estado": "NA", "puntuable": ind.puntuable, "derivado": False})

        cobertura = (peso_obs / peso_apl) if peso_apl > 0 else 0.0
        s = (suma_wz / suma_w) if suma_w > 0 else None
        suficiente = cobertura >= cmin and s is not None
        puntajes[dim.codigo] = s if suficiente else None
        if not peso_obs:
            motivo = "Sin mediciones observadas"
        elif cobertura < cmin:
            motivo = f"Cobertura {cobertura:.0%} menor al mínimo {cmin:.0%}"
        elif s is None:
            motivo = "Indicadores observados sin referencias L/U justificadas"
        else:
            motivo = ""
        detalle_dims.append({
            "dimension": dim, "alfa": round(alfas[dim.codigo], 4),
            "S": None if s is None else round(s, 4), "C": round(cobertura, 4),
            "suficiente": suficiente, "motivo": motivo, "filas": filas,
            "n_obs": sum(1 for f in filas if f["estado"] == "OBS"),
            "n_aplicables": len(aplicables),
        })

    # ---------- salvaguardas G1–G5 ----------
    g = {}
    e1 = mediciones.get("E1")
    if e1 is None and periodo is not None:
        e1 = periodo.margen_seguridad
    if "G1" in manuales:
        g["G1"] = _g(manuales["G1"], "verificación", "Verificación documentada")
    elif e1 is None:
        g["G1"] = _g(None, "regla", "Sin ventas y costos conciliados para calcular el punto de equilibrio")
    else:
        texto = f"Margen de seguridad E1 = {e1:.1%}"
        liquidez = mediciones.get("E4")
        if liquidez is not None and liquidez < 1:
            texto += f" · revisar liquidez: razón corriente {liquidez:.2f} < 1"
        g["G1"] = _g(1 if e1 >= 0 else 0, "regla", texto)

    g["G2"] = (_g(manuales["G2"], "verificación", "Verificación documentada") if "G2" in manuales else
               _g(None, "pendiente", "Requiere verificación de seguridad, derechos laborales y quejas (S4, S8, S9)"))

    a10 = mediciones.get("A10")
    if "G3" in manuales:
        g["G3"] = _g(manuales["G3"], "verificación", "Verificación documentada")
    elif a10 is None:
        g["G3"] = _g(None, "regla", "Sin resultado ecológico neto (A10) frente a línea base")
    else:
        g["G3"] = _g(1 if a10 > 0 else 0, "regla", f"A10 = {a10:g} (Y_t − Y_0)")

    if "G4" in manuales:
        g["G4"] = _g(manuales["G4"], "verificación", "Verificación documentada")
    else:
        insuficientes = [d["dimension"].codigo for d in detalle_dims if d["C"] < cmin]
        sin_fuente = 0
        if periodo is not None:
            sin_fuente = periodo.mediciones.filter(estado="OBS", fuente="").count()
        if insuficientes:
            g["G4"] = _g(0, "regla", "Faltantes críticos: cobertura insuficiente en " + ", ".join(insuficientes))
        elif sin_fuente:
            g["G4"] = _g(0, "regla", f"{sin_fuente} mediciones observadas sin fuente")
        else:
            g["G4"] = _g(1, "regla", "Cobertura suficiente en D1–D4 y fuentes registradas")

    if "G5" in manuales:
        g["G5"] = _g(manuales["G5"], "verificación", "Verificación documentada")
    elif periodo is not None:
        n = periodo.emprendimiento.periodos.filter(mediciones__estado="OBS").distinct().count()
        g["G5"] = (_g(1, "regla", f"{n} períodos con mediciones comparables") if n >= 2 else
                   _g(None, "regla", "En revisión: una sola medición temporal"))
    else:
        g["G5"] = _g(None, "regla", "Sin historial de períodos")

    valores_g = [x["valor"] for x in g.values()]
    if any(v == 0 for v in valores_g):
        r = 0
    elif any(v is None for v in valores_g):
        r = None
    else:
        r = 1

    irr, irr0 = _agregar(puntajes, alfas, eps)
    media = (sum(alfas[c] * s for c, s in puntajes.items()) if irr is not None else None)

    # ---------- clasificación ----------
    g1, g2 = g["G1"]["valor"], g["G2"]["valor"]
    todas_suficientes = all(d["suficiente"] for d in detalle_dims)
    if g1 is None:
        clase = "a"
    elif g1 == 0:
        clase = "b"
    elif r == 1:
        clase = "e"
    elif todas_suficientes and g2 != 0:
        clase = "d"
    else:
        clase = "c"
    veredicto, css = CLASIFICACIONES[clase]
    if g2 == 0:
        veredicto += " · salvaguarda social incumplida"

    con_s = [d for d in detalle_dims if d["S"] is not None]
    cuello = min(con_s, key=lambda d: d["S"])["dimension"].codigo if con_s else None

    return {
        "version": parametros.version, "epsilon": eps, "cobertura_minima": cmin,
        "dimensiones": detalle_dims,
        "salvaguardas": g,
        "R": r, "R_texto": {1: "Elegible (R = 1)", 0: "No elegible (R = 0)", None: "Indeterminado"}[r],
        "irr": None if irr is None else round(irr, 4),
        "irr0": None if irr0 is None else round(irr0, 4),
        "media_aritmetica": None if media is None else round(media, 4),
        "irr_calculable": irr is not None,
        "motivo_irr": "" if irr is not None else "IRR no calculable: alguna dimensión no alcanza la cobertura mínima o carece de referencias",
        "clasificacion": clase, "veredicto": veredicto, "clase": css,
        "cuello_de_botella": cuello,
        "cobertura_global": round(sum(d["C"] for d in detalle_dims) / len(detalle_dims), 4) if detalle_dims else 0.0,
    }


def elasticidad(mediciones, dimensiones=None, **kwargs):
    """Ganancia de IRR si la puntuación S de cada dimensión aumentara 0,10 (§2.5, Fase 4)."""
    base = evaluar(mediciones, dimensiones, **kwargs)
    filas = []
    if base["irr_calculable"]:
        alfas = {d["dimension"].codigo: d["alfa"] for d in base["dimensiones"]}
        puntajes = {d["dimension"].codigo: d["S"] for d in base["dimensiones"]}
        for d in base["dimensiones"]:
            cod = d["dimension"].codigo
            if d["S"] >= 1:
                filas.append({"dimension": d["dimension"], "S": d["S"], "objetivo": 1.0, "ganancia": None})
                continue
            alt = dict(puntajes, **{cod: min(1.0, d["S"] + INCREMENTO_ELASTICIDAD)})
            irr_alt, _ = _agregar(alt, alfas, base["epsilon"])
            filas.append({
                "dimension": d["dimension"], "S": d["S"], "objetivo": round(alt[cod], 4),
                "ganancia": round(irr_alt - base["irr"], 4), "es_cuello": cod == base["cuello_de_botella"],
            })
        filas.sort(key=lambda f: (f["ganancia"] is None, -(f["ganancia"] or 0)))
    return base, filas


def irr_desde_puntajes(puntajes, dimensiones=None, epsilon=None):
    """IRR a partir de {código: S ∈ [0,1]} (uso en simulación y pruebas)."""
    dimensiones = dimensiones if dimensiones is not None else list(Dimension.objects.all())
    epsilon = ParametrosFRR.vigentes().epsilon if epsilon is None else epsilon
    irr, _ = _agregar({d.codigo: puntajes.get(d.codigo) for d in dimensiones}, _alfas(dimensiones), epsilon)
    return irr


def serializar(resultado):
    """Versión JSON del resultado, con la configuración usada (trazabilidad de versiones)."""
    return {
        "version": resultado["version"], "epsilon": resultado["epsilon"],
        "cobertura_minima": resultado["cobertura_minima"],
        "R": resultado["R"],
        "salvaguardas": {k: {"valor": v["valor"], "origen": v["origen"], "detalle": v["detalle"]}
                         for k, v in resultado["salvaguardas"].items()},
        "dimensiones": [
            {
                "codigo": d["dimension"].codigo, "alfa": d["alfa"], "S": d["S"], "C": d["C"],
                "suficiente": d["suficiente"],
                "indicadores": [
                    {"codigo": f["indicador"].codigo, "estado": f["estado"], "valor": f["valor"],
                     "z": None if f["z"] is None else round(f["z"], 4),
                     "tipo": f["indicador"].tipo, "L": f["indicador"].ref_l, "U": f["indicador"].ref_u,
                     "T": f["indicador"].ref_t, "H": f["indicador"].ref_h, "peso": f["indicador"].peso}
                    for f in d["filas"] if f["estado"] != "ND"
                ],
            }
            for d in resultado["dimensiones"]
        ],
    }
