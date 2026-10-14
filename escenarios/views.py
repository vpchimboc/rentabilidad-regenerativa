from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from emprendimientos.models import Periodo
from escenarios.models import Escenario
from escenarios.services import FACTORES_POR_DEFECTO, sensibilidad, sensibilidad_pesos, simular
from framework.services import serializar


def lista(request):
    return render(
        request,
        "escenarios/lista.html",
        {
            "escenarios": Escenario.objects.select_related("periodo__emprendimiento"),
            "periodos": Periodo.objects.select_related("emprendimiento"),
        },
    )


def simular_periodo(request, pk):
    """Escenarios optimista, esperado y pesimista, más sensibilidad de desempeño y de pesos."""
    periodo = get_object_or_404(Periodo, pk=pk)
    mediciones = periodo.mediciones_dict()

    factores = dict(FACTORES_POR_DEFECTO)
    delta = 0.10
    if request.method == "POST":
        for tipo in factores:
            try:
                factores[tipo] = float(request.POST.get(f"factor_{tipo}", factores[tipo]))
            except (TypeError, ValueError):
                pass
        try:
            delta = float(request.POST.get("delta", 10)) / 100.0
        except (TypeError, ValueError):
            delta = 0.10

    resultados = simular(mediciones, factores, periodo=periodo)
    base, filas_sensibilidad = sensibilidad(mediciones, delta, periodo=periodo)

    if request.method == "POST" and request.POST.get("guardar"):
        for r in resultados:
            res = r["resultado"]
            Escenario.objects.update_or_create(
                periodo=periodo,
                tipo=r["tipo"],
                defaults={
                    "factor": r["factor"], "irr": res["irr"], "clasificacion": res["clasificacion"],
                    "veredicto": res["veredicto"], "version": res["version"], "detalle": serializar(res),
                },
            )
        messages.success(request, "Escenarios guardados para el período.")
        return redirect("escenario_simular", pk=periodo.pk)

    return render(
        request,
        "escenarios/simular.html",
        {
            "periodo": periodo,
            "resultados": resultados,
            "factores": factores,
            "delta_pct": round(delta * 100),
            "base": base,
            "sensibilidad": filas_sensibilidad,
            "sensibilidad_pesos": sensibilidad_pesos(base),
        },
    )
