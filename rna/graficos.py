"""Gráficas SVG del módulo RNA, generadas en el servidor (sin dependencias externas)."""

from django.utils.html import escape
from django.utils.safestring import mark_safe

AZUL, NARANJA, GRIS = "#2F5597", "#C55A11", "#9AA3AE"
W, H, M = 520, 300, {"i": 58, "d": 16, "s": 16, "inf": 46}


def _num(v, dec=2):
    return f"{v:.{dec}f}".replace(".", ",")


def _lienzo(contenido, titulo, ancho=W, alto=H):
    return mark_safe(
        f'<svg viewBox="0 0 {ancho} {alto}" role="img" aria-label="{escape(titulo)}" '
        f'style="width:100%;height:auto;font:12px system-ui,sans-serif;color:inherit">'
        f"<title>{escape(titulo)}</title>{contenido}</svg>"
    )


def _ejes(xmin, xmax, ymin, ymax, etq_x, etq_y, dec_x=2, dec_y=3):
    """Ejes con 5 marcas; devuelve (svg, función x→px, función y→px)."""
    ax, ay = W - M["i"] - M["d"], H - M["s"] - M["inf"]
    px = lambda x: M["i"] + (x - xmin) / ((xmax - xmin) or 1) * ax
    py = lambda y: M["s"] + ay - (y - ymin) / ((ymax - ymin) or 1) * ay
    s = [f'<line x1="{M["i"]}" y1="{M["s"] + ay}" x2="{M["i"] + ax}" y2="{M["s"] + ay}" stroke="currentColor" stroke-opacity=".5"/>',
         f'<line x1="{M["i"]}" y1="{M["s"]}" x2="{M["i"]}" y2="{M["s"] + ay}" stroke="currentColor" stroke-opacity=".5"/>']
    for k in range(5):
        vx, vy = xmin + (xmax - xmin) * k / 4, ymin + (ymax - ymin) * k / 4
        s.append(f'<line x1="{M["i"]}" y1="{py(vy):.1f}" x2="{M["i"] + ax}" y2="{py(vy):.1f}" stroke="{GRIS}" stroke-opacity=".25"/>')
        s.append(f'<text x="{M["i"] - 6}" y="{py(vy) + 4:.1f}" text-anchor="end" fill="currentColor">{_num(vy, dec_y)}</text>')
        s.append(f'<text x="{px(vx):.1f}" y="{M["s"] + ay + 16}" text-anchor="middle" fill="currentColor">{_num(vx, dec_x)}</text>')
    s.append(f'<text x="{M["i"] + ax / 2}" y="{H - 8}" text-anchor="middle" fill="currentColor">{escape(etq_x)}</text>')
    s.append(f'<text transform="translate(14 {M["s"] + ay / 2}) rotate(-90)" text-anchor="middle" fill="currentColor">{escape(etq_y)}</text>')
    return "".join(s), px, py


def curva_aprendizaje(historial):
    if not historial:
        return ""
    xs, ys = [h["epoca"] for h in historial], [h["mse"] for h in historial]
    ejes, px, py = _ejes(0, max(xs), 0, max(ys) * 1.05, "Época", "MSE", dec_x=0, dec_y=4)
    puntos = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in zip(xs, ys))
    marcas = "".join(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="3" fill="{AZUL}"/>' for x, y in zip(xs, ys))
    return _lienzo(ejes + f'<polyline points="{puntos}" fill="none" stroke="{AZUL}" stroke-width="2"/>' + marcas,
                   "Curva de aprendizaje: error cuadrático medio por época")


def dispersion(prueba, r2=None, mae=None):
    if not prueba:
        return ""
    todos = [v for par in prueba for v in par]
    lo, hi = min(todos) - 0.02, max(todos) + 0.02
    ejes, px, py = _ejes(lo, hi, lo, hi, "IRR analítico (Framework)", "IRR predicho (RNA)", dec_y=2)
    diag = f'<line x1="{px(lo):.1f}" y1="{py(lo):.1f}" x2="{px(hi):.1f}" y2="{py(hi):.1f}" stroke="{NARANJA}" stroke-dasharray="5 4" stroke-width="1.5"/>'
    pts = "".join(f'<circle cx="{px(r):.1f}" cy="{py(p):.1f}" r="3" fill="{AZUL}" fill-opacity=".65"/>' for p, r in prueba)
    nota = ""
    if r2 is not None:
        nota = (f'<text x="{W - M["d"] - 6}" y="{H - M["inf"] - 24}" text-anchor="end" fill="currentColor">R² = {_num(r2)}</text>'
                f'<text x="{W - M["d"] - 6}" y="{H - M["inf"] - 8}" text-anchor="end" fill="currentColor">MAE = {_num(mae, 3)}</text>')
    leyenda = (f'<line x1="{M["i"] + 10}" y1="{M["s"] + 10}" x2="{M["i"] + 34}" y2="{M["s"] + 10}" stroke="{NARANJA}" stroke-dasharray="5 4" stroke-width="1.5"/>'
               f'<text x="{M["i"] + 40}" y="{M["s"] + 14}" fill="currentColor">Predicción perfecta</text>')
    return _lienzo(ejes + diag + pts + nota + leyenda, "IRR predicho frente al IRR analítico en empresas no vistas")


def residuos(prueba, clases=16):
    if not prueba:
        return ""
    errores = [p - r for p, r in prueba]
    lo, hi = min(errores), max(errores)
    ancho = ((hi - lo) / clases) or 1
    cuentas = [0] * clases
    for e in errores:
        cuentas[min(clases - 1, int((e - lo) / ancho))] += 1
    ejes, px, py = _ejes(lo, hi, 0, max(cuentas) * 1.1, "Error (predicho − analítico)", "Frecuencia", dec_x=3, dec_y=0)
    barras = "".join(
        f'<rect x="{px(lo + k * ancho) + 1:.1f}" y="{py(c):.1f}" width="{max(1, px(lo + ancho) - px(lo) - 2):.1f}" '
        f'height="{py(0) - py(c):.1f}" fill="{AZUL}"/>' for k, c in enumerate(cuentas))
    cero = f'<line x1="{px(0):.1f}" y1="{M["s"]}" x2="{px(0):.1f}" y2="{py(0):.1f}" stroke="{NARANJA}" stroke-dasharray="5 4"/>' if lo < 0 < hi else ""
    return _lienzo(ejes + barras + cero, "Distribución de los errores de predicción")


def entradas_por_dimension(por_dimension):
    dims = [("D1", "Económica"), ("D2", "Ambiental"), ("D3", "Social"), ("D4", "Operacional")]
    n = [len(por_dimension.get(c, [])) for c, _ in dims]
    tope = max(n + [1])
    s, ancho = [], (W - 80) / 4
    for k, ((cod, nom), v) in enumerate(zip(dims, n)):
        x, alto = 50 + k * ancho, (H - 90) * v / tope
        s.append(f'<rect x="{x + 18:.1f}" y="{H - 50 - alto:.1f}" width="{ancho - 36:.1f}" height="{alto:.1f}" fill="{AZUL}" rx="3"/>')
        s.append(f'<text x="{x + ancho / 2:.1f}" y="{H - 56 - alto:.1f}" text-anchor="middle" fill="currentColor" font-weight="600">{v}</text>')
        s.append(f'<text x="{x + ancho / 2:.1f}" y="{H - 32}" text-anchor="middle" fill="currentColor">{cod}</text>')
        s.append(f'<text x="{x + ancho / 2:.1f}" y="{H - 16}" text-anchor="middle" fill="currentColor" fill-opacity=".7">{nom}</text>')
    s.append(f'<line x1="40" y1="{H - 50}" x2="{W - 20}" y2="{H - 50}" stroke="currentColor" stroke-opacity=".5"/>')
    return _lienzo("".join(s), "Número de KPI de entrada por dimensión")


def arquitectura(n_entradas, n_ocultas):
    mostrar = min(n_entradas, 10)
    capas = [(80, mostrar, "#9DC3E6", f"Entradas · {n_entradas} KPI"),
             (W / 2, min(n_ocultas, 12), AZUL, f"Capa oculta · {n_ocultas} (tanh)"),
             (W - 80, 1, NARANJA, "Salida · IRR (sigmoide)")]
    pos = [[(x, 150) if n == 1 else (x, 30 + 200 * i / (n - 1)) for i in range(n)] for x, n, _, _ in capas]
    lineas = "".join(f'<line x1="{a[0]}" y1="{a[1]:.1f}" x2="{b[0]}" y2="{b[1]:.1f}" stroke="{GRIS}" stroke-opacity=".45" stroke-width=".6"/>'
                     for c1, c2 in zip(pos, pos[1:]) for a in c1 for b in c2)
    nodos = "".join(f'<circle cx="{x}" cy="{y:.1f}" r="8" fill="{col}"/>' for capa, (_, _, col, _) in zip(pos, capas) for x, y in capa)
    textos = "".join(f'<text x="{x}" y="{H - 30}" text-anchor="middle" fill="currentColor">{escape(t)}</text>' for x, _, _, t in capas)
    nota = (f'<text x="80" y="{H - 12}" text-anchor="middle" fill="currentColor" fill-opacity=".7" font-size="10">'
            f'(se dibujan {mostrar} de {n_entradas})</text>') if mostrar < n_entradas else ""
    return _lienzo(lineas + nodos + textos + nota, f"Arquitectura del perceptrón multicapa {n_entradas}-{n_ocultas}-1")
