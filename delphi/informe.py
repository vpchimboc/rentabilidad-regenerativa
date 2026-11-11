"""Informe Delphi en Word (Anexo S1) generado con las respuestas registradas en la plataforma.

Sigue la estructura del «Anexo de resultados Delphi del framework regenerativo»: identificación,
objetivo, panel, reglas de decisión, ronda 1, cambios entre rondas, ronda 2 y consenso, figuras,
síntesis por componente, limitaciones y material complementario. Nunca rellena datos: lo que no
existe en la plataforma se marca como pendiente.
"""

import datetime
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt, RGBColor  # noqa: E402

from delphi.models import CambioItem, Dictamen, Experto, Item, Respuesta, Ronda  # noqa: E402

# Reglas de decisión (Tabla S2). Se declaran antes de analizar y se imprimen en el informe.
UMBRAL_ACUERDO = 80.0   # % de respuestas 4–5
MEDIANA_MIN = 4.0
RIC_MAX = 1.0
UMBRAL_MODIFICAR = 50.0  # por debajo: excluir

PENDIENTE = "Pendiente"
AZUL, NARANJA = "#2F5597", "#C55A11"

# Componentes del framework (Tabla S6) → preguntas del cuestionario que los evalúan.
COMPONENTES = [
    ("Constructo y arquitectura (D1–D4)", ["P01", "P02", "P03"]),
    ("Dimensión económica", ["P04"]),
    ("Dimensión ambiental", ["P05"]),
    ("Dimensión social", ["P06"]),
    ("Dimensión operacional", ["P07"]),
    ("Medibilidad y normalización", ["P08", "P09"]),
    ("Salvaguardas y agregación (IRR)", ["P10"]),
    ("Aplicabilidad e implementación", ["P11", "P12"]),
]


# ---------------- estadística ----------------
def _cuantil(v, q):
    v = sorted(v)
    if not v:
        return None
    pos = (len(v) - 1) * q
    i = int(pos)
    return v[i] + (v[min(i + 1, len(v) - 1)] - v[i]) * (pos - i)


def estadisticos(valores):
    if not valores:
        return {"n": 0, "mediana": None, "ric": None, "acuerdo": None}
    return {
        "n": len(valores),
        "mediana": _cuantil(valores, 0.5),
        "ric": _cuantil(valores, 0.75) - _cuantil(valores, 0.25),
        "acuerdo": 100 * sum(1 for x in valores if x >= 4) / len(valores),
    }


def decision(e):
    if not e["n"]:
        return "Sin datos"
    if e["acuerdo"] >= UMBRAL_ACUERDO and e["mediana"] >= MEDIANA_MIN and e["ric"] <= RIC_MAX:
        return "Aceptar"
    return "Modificar" if e["acuerdo"] >= UMBRAL_MODIFICAR else "Excluir"


def _f(v, dec=1, suf=""):
    return PENDIENTE if v is None else f"{v:.{dec}f}".replace(".", ",") + suf


def recopilar():
    rondas = [r for r in Ronda.objects.order_by("numero") if r.respuestas.exists()][:2]
    items = list(Item.objects.filter(activo=True))
    invitados = list(Experto.objects.filter(activo=True))
    por_ronda = []
    for r in rondas:
        resp = list(Respuesta.objects.filter(ronda=r).select_related("experto"))
        participantes = {x.experto_id for x in resp}
        exp = [e for e in Experto.objects.filter(pk__in=participantes)]
        filas = {}
        for it in items:
            vals = [x.valor for x in resp if x.item_id == it.id]
            com = [x.comentario.strip() for x in resp if x.item_id == it.id and x.comentario.strip()]
            e = estadisticos(vals)
            filas[it.codigo] = {**e, "comentarios": com, "decision": decision(e)}
        por_ronda.append({
            "ronda": r, "participantes": len(participantes), "filas": filas,
            "experiencia": _cuantil([e.anios_experiencia for e in exp], 0.5) if exp else None,
            "areas": sorted({e.area.split("·")[0].strip() for e in exp if e.area}),
        })
    return {"rondas": por_ronda, "items": items, "invitados": invitados,
            "cambios": list(CambioItem.objects.select_related("item", "ronda")),
            "dictamenes": list(Dictamen.objects.filter(ronda__in=rondas).select_related("experto"))}


# ---------------- figuras ----------------
def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def figura_flujo(n_rondas):
    pasos = ["Selección y\ninvitación de expertos", "Ronda 1:\ncuestionario 1–5", "Análisis: mediana,\nRIC y % de acuerdo",
             "Retroalimentación\nanónima y ajustes", "Ronda 2:\nreevaluación", "Decisión final:\naceptar, modificar\no excluir"]
    if n_rondas < 2:
        pasos = pasos[:3] + ["Decisión:\naceptar, modificar\no excluir"]
    fig, ax = plt.subplots(figsize=(10, 1.9))
    ax.axis("off")
    n = len(pasos)
    for i, t in enumerate(pasos):
        x = i / n
        ax.add_patch(plt.Rectangle((x + 0.005, 0.15), 1 / n - 0.03, 0.7, fc="#D9E2F3", ec=AZUL, lw=1.2,
                                   transform=ax.transAxes))
        ax.text(x + 0.5 / n - 0.01, 0.5, t, ha="center", va="center", fontsize=8.5, transform=ax.transAxes)
        if i < n - 1:
            ax.annotate("", xy=(x + 1 / n + 0.003, 0.5), xytext=(x + 1 / n - 0.024, 0.5),
                        xycoords="axes fraction", arrowprops=dict(arrowstyle="->", color=AZUL, lw=1.4))
    return _png(fig)


def figura_acuerdo(datos):
    codigos = [i.codigo for i in datos["items"]]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ancho = 0.38 if len(datos["rondas"]) > 1 else 0.6
    for k, (r, col) in enumerate(zip(datos["rondas"], (AZUL, NARANJA))):
        vals = [r["filas"][c]["acuerdo"] or 0 for c in codigos]
        desplaz = (k - (len(datos["rondas"]) - 1) / 2) * ancho
        ax.bar([i + desplaz for i in range(len(codigos))], vals, ancho, color=col, label=f"Ronda {r['ronda'].numero}")
    ax.axhline(UMBRAL_ACUERDO, color="#7F7F7F", ls="--", lw=1)
    ax.text(len(codigos) - 0.5, UMBRAL_ACUERDO + 2, f"Umbral {UMBRAL_ACUERDO:.0f} %", ha="right", fontsize=8, color="#555")
    ax.set_xticks(range(len(codigos)), codigos)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Acuerdo (%)")
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    return _png(fig)


def figura_decisiones(final):
    cats = ["Aceptar", "Modificar", "Excluir", "Sin datos"]
    n = [sum(1 for f in final.values() if f["decision"] == c) for c in cats]
    fig, ax = plt.subplots(figsize=(6, 2.8))
    barras = ax.bar(cats, n, color=["#548235", "#BF9000", "#C00000", "#A6A6A6"])
    ax.bar_label(barras)
    ax.set_ylabel("Número de ítems")
    ax.spines[["top", "right"]].set_visible(False)
    return _png(fig)


# ---------------- documento ----------------
def _sombrear(celda, color="D9E2F3"):
    tc = celda._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:color"), "auto")
    sh.set(qn("w:fill"), color)
    tc.append(sh)


def _tabla(doc, cabecera, filas, anchos=None):
    t = doc.add_table(rows=1, cols=len(cabecera))
    t.style = "Table Grid"
    for c, txt in zip(t.rows[0].cells, cabecera):
        c.text = ""
        c.paragraphs[0].add_run(txt).bold = True
        _sombrear(c)
    for fila in filas:
        celdas = t.add_row().cells
        for c, txt in zip(celdas, fila):
            c.text = str(txt)
    for fila in t.rows:
        for k, c in enumerate(fila.cells):
            for p in c.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(9.5)
            if anchos:
                c.width = Cm(anchos[k])
    doc.add_paragraph()
    return t


def _titulo_tabla(doc, txt):
    p = doc.add_paragraph()
    p.add_run(txt).bold = True


def generar(titulo_articulo="", responsable="", version_framework="FRR 1.0 (42 KPI candidatos)"):
    d = recopilar()
    rondas = d["rondas"]
    r1 = rondas[0] if rondas else None
    r2 = rondas[1] if len(rondas) > 1 else None
    final = (r2 or r1)["filas"] if rondas else {i.codigo: {"decision": "Sin datos"} for i in d["items"]}

    doc = Document()
    estilo = doc.styles["Normal"]
    estilo.font.name = "Times New Roman"
    estilo.font.size = Pt(11)
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(2.5)

    p = doc.add_paragraph()
    p.add_run("ANEXO CIENTÍFICO").bold = True
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_heading("Resultados de la validación de contenido mediante el método Delphi del framework de "
                    "rentabilidad regenerativa para emprendimientos", level=1)
    hoy = datetime.date.today().strftime("%d/%m/%Y")
    estado = (f"Generado desde la plataforma FRR el {hoy} con {len(rondas)} ronda(s) y "
              f"{sum(r['participantes'] for r in rondas)} participaciones de expertos registradas." if rondas else
              f"Generado desde la plataforma FRR el {hoy}. SIN RESPUESTAS REGISTRADAS: las tablas de resultados "
              "quedan pendientes y el documento no constituye evidencia de validación.")
    q = doc.add_paragraph()
    q.add_run("Estado: ").bold = True
    run = q.add_run(estado)
    if not rondas:
        run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

    # 1. Identificación
    doc.add_heading("1. Identificación del estudio", level=2)
    fechas = "; ".join(f"Ronda {r['ronda'].numero}: {r['ronda'].fecha:%d/%m/%Y}" for r in rondas) or PENDIENTE
    _tabla(doc, ["Campo", "Información"], [
        ["Título del artículo", titulo_articulo or "Más allá del Break-even: Propuesta de un Framework de Rentabilidad "
         "Regenerativa para la Evaluación de Emprendimientos de Triple Impacto"],
        ["Código de anexo", "Anexo S1"],
        ["Rondas ejecutadas", str(len(rondas)) if rondas else PENDIENTE],
        ["Fechas de ejecución", fechas],
        ["Responsable del análisis", responsable or PENDIENTE],
        ["Versión del framework evaluada", version_framework],
    ], [5, 11])

    # 2. Objetivo
    doc.add_heading("2. Objetivo y alcance de la validación", level=2)
    doc.add_paragraph("Objetivo: evaluar mediante juicio estructurado de expertos la pertinencia, coherencia, claridad, "
                      "medibilidad, aplicabilidad y rigor técnico de las dimensiones, el catálogo de 42 KPI candidatos, "
                      "la normalización, las salvaguardas y la agregación del IRR del framework.")
    doc.add_paragraph("Alcance: el consenso aporta evidencia de validez de contenido; no equivale a validación predictiva "
                      "ni prueba de efectividad empírica del framework.")

    # 3. Panel
    doc.add_heading("3. Panel de expertos y participación", level=2)
    _titulo_tabla(doc, "Tabla S1. Caracterización del panel de expertos")
    inv = len(d["invitados"])
    col = lambda r, f: f(r) if r else "—"
    _tabla(doc, ["Variable", "Ronda 1", "Ronda 2"], [
        ["Invitados", str(inv), str(inv) if r2 else "—"],
        ["Participantes que respondieron", col(r1, lambda r: str(r["participantes"])), col(r2, lambda r: str(r["participantes"]))],
        ["Tasa de respuesta", col(r1, lambda r: _f(100 * r["participantes"] / inv if inv else None, 1, " %")),
         col(r2, lambda r: _f(100 * r["participantes"] / inv if inv else None, 1, " %"))],
        ["Experiencia (mediana de años)", col(r1, lambda r: _f(r["experiencia"], 0)), col(r2, lambda r: _f(r["experiencia"], 0))],
        ["Áreas de especialidad", col(r1, lambda r: "; ".join(r["areas"]) or PENDIENTE),
         col(r2, lambda r: "; ".join(r["areas"]) or PENDIENTE)],
    ], [5.5, 5.25, 5.25])
    doc.add_paragraph("Criterios de elegibilidad: maestría o doctorado, al menos 5 años de experiencia y publicaciones "
                      "científicas en áreas afines (ingeniería industrial, sostenibilidad, emprendimiento, finanzas). "
                      "Las respuestas individuales se presentan de forma anónima.")

    # 4. Procedimiento
    doc.add_heading("4. Procedimiento y criterios de consenso", level=2)
    doc.add_paragraph(f"Instrumento: cuestionario de {len(d['items'])} afirmaciones (P1–P12) en escala Likert 1–5 "
                      "(1 muy deficiente … 5 excelente) y dos preguntas abiertas (P13 cambio prioritario; P14 recomendación). "
                      "Las respuestas «No evaluable» se excluyen del denominador. Las reglas se fijaron antes del análisis.")
    _titulo_tabla(doc, "Tabla S2. Reglas de decisión definidas para el análisis")
    _tabla(doc, ["Indicador", "Definición operacional", "Criterio de aceptación"], [
        ["Mediana", "Mediana de calificaciones por ítem", f"≥ {MEDIANA_MIN:.0f}"],
        ["Rango intercuartílico (RIC)", "Q3 − Q1", f"≤ {RIC_MAX:.0f}"],
        ["Porcentaje de acuerdo", "(Respuestas 4 o 5 / respuestas válidas) × 100", f"≥ {UMBRAL_ACUERDO:.0f} %"],
        ["Decisión", "Combinación de los criterios anteriores",
         f"Aceptar: cumple los tres · Modificar: acuerdo ≥ {UMBRAL_MODIFICAR:.0f} % sin cumplir todos · Excluir: acuerdo < {UMBRAL_MODIFICAR:.0f} %"],
        ["Estabilidad entre rondas", "Diferencia de acuerdo R2 − R1 por ítem", "Informativa (no decide)"],
    ], [4, 6, 6])

    # 5. Ronda 1
    doc.add_heading("5. Resultados de la primera ronda", level=2)
    _titulo_tabla(doc, "Tabla S3. Resultados desagregados por ítem: ronda 1")
    filas = []
    for it in d["items"]:
        f = r1["filas"][it.codigo] if r1 else None
        filas.append([f"{it.codigo} · {it.componente}", str(f["n"]) if f else PENDIENTE,
                      _f(f["mediana"]) if f else PENDIENTE, _f(f["ric"]) if f else PENDIENTE,
                      _f(f["acuerdo"], 1, " %") if f else PENDIENTE,
                      " / ".join(f["comentarios"]) if f and f["comentarios"] else "—"])
    _tabla(doc, ["Código / componente", "n válido", "Mediana", "RIC", "Acuerdo (%)", "Observaciones"], filas,
           [4.5, 1.5, 1.6, 1.4, 2, 5])
    if r1:
        ok = [c for c, f in r1["filas"].items() if f["decision"] == "Aceptar"]
        doc.add_paragraph(f"Interpretación: {len(ok)} de {len(d['items'])} ítems alcanzaron el criterio de aceptación en la "
                          f"ronda 1{(' (' + ', '.join(ok) + ')') if ok else ''}.")

    # 6. Cambios
    doc.add_heading("6. Retroalimentación y modificaciones entre rondas", level=2)
    _titulo_tabla(doc, "Tabla S4. Trazabilidad de ajustes del framework")
    _tabla(doc, ["Código", "Hallazgo de ronda 1", "Cambio aplicado", "Justificación", "Reevaluado en R2"],
           [[c.item.codigo, c.hallazgo, c.cambio or "—", c.justificacion or "—", "Sí" if c.reevaluado else "No"]
            for c in d["cambios"]] or [["—", "Sin cambios registrados en la plataforma", "—", "—", "—"]],
           [1.6, 4, 4, 4, 2.4])

    # 7. Ronda 2
    doc.add_heading("7. Resultados de la segunda ronda y consenso final", level=2)
    _titulo_tabla(doc, "Tabla S5. Comparación de indicadores de consenso entre rondas")
    filas = []
    for it in d["items"]:
        a = r1["filas"][it.codigo] if r1 else None
        b = r2["filas"][it.codigo] if r2 else None
        filas.append([it.codigo, _f(a["acuerdo"], 1, " %") if a else PENDIENTE,
                      _f(b["acuerdo"], 1, " %") if b else "—", _f(b["mediana"]) if b else "—",
                      _f(b["ric"]) if b else "—", final[it.codigo]["decision"]])
    _tabla(doc, ["Ítem", "Acuerdo R1 (%)", "Acuerdo R2 (%)", "Mediana R2", "RIC R2", "Decisión"], filas,
           [1.6, 2.8, 2.8, 2.4, 2, 4.4])
    if rondas:
        cuenta = {c: sum(1 for f in final.values() if f["decision"] == c) for c in ("Aceptar", "Modificar", "Excluir")}
        texto = (f"Resultados: con base en la ronda {(r2 or r1)['ronda'].numero}, {cuenta['Aceptar']} ítems se aceptan, "
                 f"{cuenta['Modificar']} requieren modificación y {cuenta['Excluir']} se excluyen.")
        if not r2:
            texto += " Solo se ejecutó una ronda: los resultados no se presentan como consenso Delphi iterativo."
        elif r1["participantes"] > r2["participantes"]:
            texto += f" Pérdida de seguimiento: {r1['participantes'] - r2['participantes']} experto(s) entre rondas."
        doc.add_paragraph(texto)

    # 8. Figuras
    doc.add_heading("8. Figuras y gráficos de resultados", level=2)
    doc.add_picture(figura_flujo(len(rondas)), width=Cm(16))
    doc.add_paragraph("Figura S1. Flujo metodológico de la evaluación Delphi. Fuente: elaboración propia.")
    if rondas:
        doc.add_picture(figura_acuerdo(d), width=Cm(16))
        doc.add_paragraph("Figura S2. Comparación del acuerdo por ítem entre rondas. Fuente: respuestas registradas en la plataforma.")
        doc.add_picture(figura_decisiones(final), width=Cm(11))
        doc.add_paragraph("Figura S3. Distribución de decisiones finales.")
    else:
        doc.add_paragraph("Figuras S2 y S3: pendientes; se generan automáticamente cuando existan respuestas registradas.")

    # 9. Síntesis
    doc.add_heading("9. Síntesis de validación y discusión", level=2)
    _titulo_tabla(doc, "Tabla S6. Síntesis final por componente del framework")
    filas = []
    for nombre, cods in COMPONENTES:
        cods = [c for c in cods if c in final]
        acep = [c for c in cods if final[c]["decision"] == "Aceptar"]
        camb = [c.item.codigo for c in d["cambios"] if c.item.codigo in cods]
        res = (PENDIENTE if not rondas else "Retenido" if len(acep) == len(cods)
               else "Retenido con ajustes" if acep or any(final[c]["decision"] == "Modificar" for c in cods) else "Revisar")
        filas.append([nombre, f"{len(cods)} ({', '.join(cods)})", str(len(acep)) if rondas else PENDIENTE,
                      ", ".join(camb) or "—", res])
    _tabla(doc, ["Componente", "Ítems evaluados", "Ítems con consenso", "Cambios principales", "Resultado"], filas,
           [4.4, 3.4, 2.4, 2.8, 3])
    if d["dictamenes"]:
        rec = {etq: sum(1 for x in d["dictamenes"] if x.recomendacion == c) for c, etq in Dictamen.RECOMENDACIONES}
        doc.add_paragraph("P14. Recomendación de mantener el FRR para evaluación exploratoria: "
                          + "; ".join(f"{k}: {v}" for k, v in rec.items()) + ".")
        doc.add_paragraph("P13. Cambios prioritarios propuestos (síntesis anónima):")
        for x in d["dictamenes"]:
            if x.cambio_prioritario:
                doc.add_paragraph(x.cambio_prioritario, style="List Bullet")

    # 10. Limitaciones
    doc.add_heading("10. Limitaciones, conclusión y reproducibilidad", level=2)
    doc.add_paragraph(f"Limitaciones: panel de {inv} expertos; con paneles pequeños el porcentaje de acuerdo solo toma pocos "
                      "valores posibles. La valoración del catálogo es global por dimensión (P4–P7) y no valida "
                      "individualmente cada KPI. El consenso no prueba la efectividad empírica del framework.")
    doc.add_paragraph("Conclusión: " + (PENDIENTE + ": redactar con los resultados finales." if not rondas else
                      "indicar el grado de consenso demostrado, los componentes retenidos y los cambios realizados, "
                      "sin afirmar validación total."))
    doc.add_paragraph("Disponibilidad de datos: la matriz anonimizada de respuestas y los cálculos se exportan desde la "
                      "plataforma (reporte por ronda, formato CSV).")

    doc.add_heading("11. Material complementario recomendado", level=2)
    doc.add_paragraph("Anexo S1-A: cuestionario de la primera ronda. Anexo S1-B: cuestionario y retroalimentación de la "
                      "segunda ronda. Anexo S1-C: matriz de respuestas anonimizada. Anexo S1-D: versión del framework "
                      "antes y después de la evaluación.")

    salida = io.BytesIO()
    doc.save(salida)
    salida.seek(0)
    return salida
