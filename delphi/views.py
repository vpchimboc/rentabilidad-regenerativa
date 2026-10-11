from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from delphi.models import Experto, Item, ResultadoRonda, Respuesta, Ronda
from delphi.stats import UMBRAL_IVC, UMBRAL_W, analizar_ronda


def panel(request):
    rondas = Ronda.objects.prefetch_related("respuestas")
    return render(
        request,
        "delphi/panel.html",
        {
            "rondas": rondas,
            "expertos": Experto.objects.all(),
            "items": Item.objects.all(),
            "umbral_ivc": UMBRAL_IVC,
            "umbral_w": UMBRAL_W,
        },
    )


def cuestionario(request, pk):
    """Captura de las valoraciones Likert de un experto en una ronda."""
    ronda = get_object_or_404(Ronda, pk=pk)
    items = Item.objects.all()
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
        {"ronda": ronda, "filas": filas, "expertos": expertos, "experto": experto},
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
        },
    )
