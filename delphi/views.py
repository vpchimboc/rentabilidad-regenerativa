from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from delphi.models import Dictamen, Experto, Item, ResultadoRonda, Respuesta, Ronda
from delphi.stats import UMBRAL_IVC, UMBRAL_W, analizar_ronda


def panel(request):
    rondas = Ronda.objects.prefetch_related("respuestas")
    return render(
        request,
        "delphi/panel.html",
        {
            "rondas": rondas,
            "expertos": Experto.objects.all(),
            "items": Item.objects.filter(activo=True),
            "umbral_ivc": UMBRAL_IVC,
            "umbral_w": UMBRAL_W,
        },
    )


def cuestionario(request, pk):
    """Captura de las valoraciones Likert de un experto en una ronda."""
    ronda = get_object_or_404(Ronda, pk=pk)
    items = Item.objects.filter(activo=True)
    expertos = Experto.objects.filter(activo=True)
    experto_id = request.POST.get("experto") or request.GET.get("experto")
    experto = Experto.objects.filter(pk=experto_id).first() if experto_id else None

    if request.method == "POST" and experto and request.POST.get("guardar"):
        guardadas = 0
        for item in items:
            valor = request.POST.get(f"item_{item.id}")
            if not valor:
                continue
            Respuesta.objects.update_or_create(
                ronda=ronda,
                experto=experto,
                item=item,
                defaults={
                    "valor": int(valor),
                    "comentario": request.POST.get(f"comentario_{item.id}", ""),
                },
            )
            guardadas += 1
        Dictamen.objects.update_or_create(
            ronda=ronda, experto=experto,
            defaults={"cambio_prioritario": request.POST.get("cambio_prioritario", "").strip(),
                      "recomendacion": request.POST.get("recomendacion", "")
                      if request.POST.get("recomendacion") in dict(Dictamen.RECOMENDACIONES) else ""},
        )
        messages.success(request, f"{guardadas} valoraciones registradas para {experto.nombre}.")
        return redirect("delphi_resultado", pk=ronda.pk)

    previas = {}
    if experto:
        previas = {
            r.item_id: r
            for r in Respuesta.objects.filter(ronda=ronda, experto=experto)
        }

    filas = [
        {
            "item": item,
            "valor": previas[item.id].valor if item.id in previas else None,
            "comentario": previas[item.id].comentario if item.id in previas else "",
            "opciones": [
                {"n": n, "marcado": item.id in previas and previas[item.id].valor == n}
                for n in range(1, 6)
            ],
        }
        for item in items
    ]

    return render(
        request,
        "delphi/cuestionario.html",
        {"ronda": ronda, "filas": filas, "expertos": expertos, "experto": experto,
         "dictamen": Dictamen.objects.filter(ronda=ronda, experto=experto).first() if experto else None,
         "recomendaciones": Dictamen.RECOMENDACIONES},
    )


def resultado(request, pk):
    """Calcula IVC por ítem, S-CVI global y W de Kendall para la ronda."""
    ronda = get_object_or_404(Ronda, pk=pk)
    respuestas = Respuesta.objects.filter(ronda=ronda)
    if not respuestas.exists():
        messages.warning(request, "La ronda aún no tiene respuestas registradas.")
        return redirect("delphi_panel")

    analisis = analizar_ronda(respuestas)
    items = {i.id: i for i in Item.objects.all()}
    for fila in analisis["items"]:
        fila["item"] = items.get(fila["item_id"])

    ResultadoRonda.objects.update_or_create(
        ronda=ronda,
        defaults={
            "s_cvi": analisis["s_cvi"],
            "kendall_w": analisis["kendall"]["w"],
            "chi_cuadrado": analisis["kendall"]["chi2"],
            "gl": analisis["kendall"]["gl"],
            "consenso": analisis["consenso"],
            "detalle": {
                "items": [
                    {k: v for k, v in f.items() if k != "item"} for f in analisis["items"]
                ]
            },
        },
    )

    return render(
        request,
        "delphi/resultado.html",
        {
            "ronda": ronda,
            "a": analisis,
            "umbral_ivc": UMBRAL_IVC,
            "umbral_w": UMBRAL_W,
            "n_expertos": respuestas.values("experto").distinct().count(),
            "dictamenes": ronda.dictamenes.select_related("experto"),
        },
    )


# ---------------- Administración del panel de expertos ----------------
from django import forms  # noqa: E402

from administracion.models import registrar  # noqa: E402
from administracion.permisos import requiere_permiso  # noqa: E402


class ExpertoForm(forms.ModelForm):
    class Meta:
        model = Experto
        fields = ["nombre", "grado", "institucion", "pais", "area", "anios_experiencia", "publicaciones",
                  "correo", "activo"]
        labels = {"anios_experiencia": "Años de experiencia", "publicaciones": "Publicaciones científicas",
                  "area": "Especialidad / formación", "institucion": "Institución y cargo", "pais": "País"}
        widgets = {"area": forms.Textarea(attrs={"rows": 2}), "institucion": forms.TextInput(attrs={"size": 60})}


@requiere_permiso("delphi.add_experto")
def experto_nuevo(request):
    return _experto_form(request, None)


@requiere_permiso("delphi.change_experto")
def experto_editar(request, pk):
    return _experto_form(request, get_object_or_404(Experto, pk=pk))


def _experto_form(request, experto):
    form = ExpertoForm(request.POST or None, instance=experto)
    if request.method == "POST" and form.is_valid():
        e = form.save()
        registrar("CONFIG", request.user, "Experto", f"{'Editado' if experto else 'Registrado'}: {e.nombre}")
        messages.success(request, f"Experto {'actualizado' if experto else 'registrado'}: {e.nombre}.")
        return redirect("delphi_panel")
    return render(request, "delphi/experto_form.html", {"form": form, "experto": experto})


@requiere_permiso("delphi.delete_experto")
def experto_eliminar(request, pk):
    experto = get_object_or_404(Experto, pk=pk)
    if request.method == "POST":
        nombre, n = experto.nombre, experto.respuestas.count()
        experto.delete()
        ResultadoRonda.objects.all().delete()  # los resultados calculados con este experto ya no son válidos
        registrar("CONFIG", request.user, "Experto", f"Eliminado: {nombre} ({n} respuestas)")
        messages.success(request, f"Experto eliminado: {nombre} y sus {n} respuestas.")
        return redirect("delphi_panel")
    return render(request, "delphi/experto_eliminar.html", {"experto": experto})


# ---------------- Reporte de evaluación experta ----------------
ITEMS_ICVI = ("P04", "P05", "P06", "P07")  # valoración global por dimensión (guía §4)


def _mediana(v):
    v = sorted(v)
    n = len(v)
    return None if not n else (v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2)


def datos_reporte(ronda):
    expertos = list(Experto.objects.filter(respuestas__ronda=ronda).distinct()
                    | Experto.objects.filter(dictamenes__ronda=ronda).distinct())
    expertos = sorted(set(expertos), key=lambda e: e.nombre)
    resp = {(r.item_id, r.experto_id): r for r in Respuesta.objects.filter(ronda=ronda)}
    filas = []
    for item in Item.objects.filter(activo=True):
        valores = [resp[(item.id, e.id)].valor if (item.id, e.id) in resp else None for e in expertos]
        obs = [v for v in valores if v is not None]
        favorables = sum(1 for v in obs if v >= 4)
        filas.append({
            "item": item, "valores": valores,
            "comentarios": [(e.nombre, resp[(item.id, e.id)].comentario) for e in expertos
                            if (item.id, e.id) in resp and resp[(item.id, e.id)].comentario],
            "n": len(obs), "mediana": _mediana(obs),
            "minimo": min(obs) if obs else None, "maximo": max(obs) if obs else None,
            "pct_favorable": round(100 * favorables / len(obs), 1) if obs else None,
            "icvi": round(favorables / len(obs), 3) if obs and item.codigo in ITEMS_ICVI else None,
        })
    dictamenes = list(Dictamen.objects.filter(ronda=ronda).select_related("experto"))
    p14 = {etq: sum(1 for d in dictamenes if d.recomendacion == cod) for cod, etq in Dictamen.RECOMENDACIONES}
    return {"ronda": ronda, "expertos": expertos, "filas": filas, "dictamenes": dictamenes, "p14": p14}


def reporte(request, pk):
    ronda = get_object_or_404(Ronda, pk=pk)
    datos = datos_reporte(ronda)
    if request.GET.get("formato") == "csv":
        import csv
        from django.http import HttpResponse
        r = HttpResponse(content_type="text/csv; charset=utf-8")
        r["Content-Disposition"] = f'attachment; filename="reporte_expertos_ronda{ronda.numero}.csv"'
        r.write("﻿")
        w = csv.writer(r, delimiter=";")
        w.writerow(["Pregunta", "Criterio", "Afirmación"] + [e.nombre for e in datos["expertos"]]
                   + ["n", "Mediana", "Mínimo", "Máximo", "% respuestas 4-5", "I-CVI exploratorio"])
        fmt = lambda v: "" if v is None else str(v).replace(".", ",")
        for f in datos["filas"]:
            w.writerow([f["item"].codigo, f["item"].get_criterio_display(), f["item"].enunciado]
                       + [fmt(v) for v in f["valores"]]
                       + [f["n"], fmt(f["mediana"]), fmt(f["minimo"]), fmt(f["maximo"]),
                          fmt(f["pct_favorable"]), fmt(f["icvi"])])
        w.writerow([])
        w.writerow(["Experto", "P14. ¿Mantener el FRR para evaluación exploratoria?", "P13. Cambio prioritario"])
        for d in datos["dictamenes"]:
            w.writerow([d.experto.nombre, d.get_recomendacion_display(), d.cambio_prioritario])
        return r
    return render(request, "delphi/reporte.html", datos)


# ---------------- Administración de rondas ----------------
class RondaForm(forms.ModelForm):
    class Meta:
        model = Ronda
        fields = ["numero", "fecha", "estado", "observaciones"]
        labels = {"numero": "Número de ronda", "fecha": "Fecha de aplicación"}
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "observaciones": forms.Textarea(attrs={"rows": 3})}


@requiere_permiso("delphi.add_ronda")
def ronda_nueva(request):
    return _ronda_form(request, None)


@requiere_permiso("delphi.change_ronda")
def ronda_editar(request, pk):
    return _ronda_form(request, get_object_or_404(Ronda, pk=pk))


def _ronda_form(request, ronda):
    import datetime
    from django.db.models import Max
    inicial = None if ronda else {"numero": (Ronda.objects.aggregate(m=Max("numero"))["m"] or 0) + 1,
                                  "fecha": datetime.date.today()}
    form = RondaForm(request.POST or None, instance=ronda, initial=inicial)
    if request.method == "POST" and form.is_valid():
        r = form.save()
        registrar("CONFIG", request.user, "Ronda", f"{'Editada' if ronda else 'Creada'}: ronda {r.numero} ({r.fecha})")
        messages.success(request, f"Ronda {r.numero} {'actualizada' if ronda else 'creada'}.")
        return redirect("delphi_panel")
    return render(request, "delphi/ronda_form.html", {"form": form, "ronda": ronda})


@requiere_permiso("delphi.delete_ronda")
def ronda_eliminar(request, pk):
    ronda = get_object_or_404(Ronda, pk=pk)
    if request.method == "POST":
        n = ronda.respuestas.count()
        ronda.delete()
        registrar("CONFIG", request.user, "Ronda", f"Eliminada: ronda {ronda.numero} ({n} respuestas)")
        messages.success(request, f"Ronda {ronda.numero} eliminada con sus {n} respuestas.")
        return redirect("delphi_panel")
    return render(request, "delphi/ronda_eliminar.html", {"ronda": ronda})
