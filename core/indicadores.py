"""Indicadores del tablero ejecutivo, calculados a partir de los períodos guardados.

Nada se estima ni se completa: si un dato no está en la base, el indicador se
informa como ausente.
"""

from collections import OrderedDict
from statistics import median

from emprendimientos.models import Emprendimiento, Periodo

ORIGENES = [("", "Todas las fuentes"), ("publico", "Fuentes públicas"), ("manual", "Registro manual")]


def filtrar_emprendimientos(sector="", provincia="", origen="", q=""):
    qs = Emprendimiento.objects.all()
    if sector:
        qs = qs.filter(sector=sector)
    if provincia:
        qs = qs.filter(provincia=provincia)
    if origen == "publico":
        qs = qs.exclude(fuente="")
    elif origen == "manual":
        qs = qs.filter(fuente="")
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(nombre__icontains=q) | Q(ruc__icontains=q) | Q(ciudad__icontains=q))
    return qs


def _cifras(periodo):
    ventas = float(periodo.ventas)
    costos = float(periodo.costos_fijos) + float(periodo.costos_variables)
    pe = periodo.punto_equilibrio
    return {
        "periodo": periodo,
        "ventas": ventas,
        "costos": costos,
        "resultado": ventas - costos,
        "margen": ((ventas - costos) / ventas * 100) if ventas > 0 else None,
        "pe": pe,
        "ventas_pe": (ventas / pe) if pe > 0 else None,
    }


def _totales(filas):
    ingresos = sum(f["ventas"] for f in filas)
    costos = sum(f["costos"] for f in filas)
    return {
        "n": len(filas),
        "ingresos": ingresos,
        "costos": costos,
        "resultado": ingresos - costos,
        "margen": ((ingresos - costos) / ingresos * 100) if ingresos > 0 else None,
    }


def _barras(pares, clave_max=None):
    """Normaliza valores no negativos a porcentaje de ancho para las barras."""
    maximo = clave_max or max((v for _, v in pares), default=0) or 1
    return [{"rotulo": r, "valor": v, "ancho": round(max(v, 0) / maximo * 100, 1)} for r, v in pares]


def calcular(anio=None, umbral=1.0, **filtros):
    emprendimientos = filtrar_emprendimientos(**filtros)
    periodos_todos = Periodo.objects.filter(emprendimiento__in=emprendimientos).select_related("emprendimiento")
    anios = sorted({p.anio for p in periodos_todos}, reverse=True)
    if anio not in anios:
        anio = anios[0] if anios else None

    filas = [_cifras(p) for p in periodos_todos if p.anio == anio]
    con_ventas = [f for f in filas if f["ventas"] > 0]
    tot = _totales(filas)

    # Comparación coherente: solo emprendimientos con período en ambos años.
    comparacion = None
    if anio is not None:
        previos = {p.emprendimiento_id: _cifras(p) for p in periodos_todos if p.anio == anio - 1}
        pares = [(f, previos[f["periodo"].emprendimiento_id]) for f in filas
                 if f["periodo"].emprendimiento_id in previos]
        if pares:
            act, ant = _totales([a for a, _ in pares]), _totales([b for _, b in pares])
            comparacion = {
                "n": len(pares), "anio": anio - 1,
                "ingresos": ((act["ingresos"] - ant["ingresos"]) / ant["ingresos"] * 100) if ant["ingresos"] else None,
                "resultado_ant": ant["resultado"], "resultado_act": act["resultado"],
            }

    ratios = [f["ventas_pe"] for f in con_ventas if f["ventas_pe"] is not None]
    sobre_pe = sum(1 for r in ratios if r >= 1)
    rentables = [f for f in con_ventas if f["resultado"] > 0]
    alertas = [
        f for f in filas
        if f["ventas"] <= 0 or f["resultado"] <= 0 or (f["ventas_pe"] is not None and f["ventas_pe"] < umbral)
    ]
    alertas.sort(key=lambda f: (f["ventas_pe"] if f["ventas_pe"] is not None else -1, f["resultado"]))

    # Gráficos
    por_sector = OrderedDict()
    for f in filas:
        clave = f["periodo"].emprendimiento.get_sector_display()
        acc = por_sector.setdefault(clave, {"ingresos": 0.0, "costos": 0.0, "n": 0})
        acc["ingresos"] += f["ventas"]
        acc["costos"] += f["costos"]
        acc["n"] += 1
    maximo = max([v["ingresos"] for v in por_sector.values()] + [v["costos"] for v in por_sector.values()] + [1])
    ingresos_costos = [
        {"rotulo": k, "n": v["n"], "ingresos": v["ingresos"], "costos": v["costos"],
         "ancho_i": round(v["ingresos"] / maximo * 100, 1), "ancho_c": round(v["costos"] / maximo * 100, 1)}
        for k, v in sorted(por_sector.items(), key=lambda kv: -kv[1]["ingresos"])
    ]

    sectores = OrderedDict()
    for e in emprendimientos:
        sectores[e.get_sector_display()] = sectores.get(e.get_sector_display(), 0) + 1
    provincias = OrderedDict()
    for e in emprendimientos:
        clave = e.provincia.title() if e.provincia else "Sin provincia registrada"
        provincias[clave] = provincias.get(clave, 0) + 1

    tramos = OrderedDict([("Negativo (< 0 %)", 0), ("0 – 10 %", 0), ("10 – 20 %", 0), ("Más de 20 %", 0)])
    for f in con_ventas:
        m = f["margen"]
        clave = ("Negativo (< 0 %)" if m < 0 else "0 – 10 %" if m < 10 else "10 – 20 %" if m < 20 else "Más de 20 %")
        tramos[clave] += 1

    evolucion = []
    for a in sorted(anios):
        t = _totales([_cifras(p) for p in periodos_todos if p.anio == a])
        evolucion.append({"anio": a, **t})
    max_evo = max([abs(e["resultado"]) for e in evolucion] + [e["ingresos"] for e in evolucion] + [1])
    for e in evolucion:
        e["ancho_i"] = round(e["ingresos"] / max_evo * 100, 1)
        e["ancho_r"] = round(abs(e["resultado"]) / max_evo * 100, 1)

    return {
        "anio": anio,
        "anios": anios,
        "total_emprendimientos": emprendimientos.count(),
        "periodos_anio": len(filas),
        "totales": tot,
        "comparacion": comparacion,
        "sobre_pe": sobre_pe,
        "con_pe": len(ratios),
        "mediana_ventas_pe": median(ratios) if ratios else None,
        "rentables": len(rentables),
        "con_ventas": len(con_ventas),
        "alertas": alertas,
        "ingresos_costos": ingresos_costos,
        "sectores": _barras(sorted(sectores.items(), key=lambda kv: -kv[1])),
        "provincias": _barras(sorted(provincias.items(), key=lambda kv: -kv[1])[:8]),
        "tramos_margen": _barras(list(tramos.items())),
        "evolucion": evolucion,
    }
