from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from emprendimientos.models import Periodo
from escenarios.models import Escenario
from escenarios.services import FACTORES_POR_DEFECTO, sensibilidad, simular


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
    """Corre los escenarios optimista, esperado y pesimista, más la sensibilidad."""
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

    resultados = simular(mediciones, factores)
    base, filas_sensibilidad = sensibilidad(mediciones, delta)

    if request.method == "POST" and request.POST.get("guardar"):
        for r in resultados:
            Escenario.objects.update_or_create(
                periodo=periodo,
                tipo=r["tipo"],
                defaults={
                    "factor": r["factor"],
                    "irr": r["resultado"]["irr"],
                    "minimo_dimensional": r["resultado"]["minimo_dimensional"],
                    "veredicto": r["resultado"]["veredicto"],
                    "detalle": {
                        d["dimension"].codigo: d["nivel"]
                        for d in r["resultado"]["dimensiones"]
                    },
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
        },
    )
