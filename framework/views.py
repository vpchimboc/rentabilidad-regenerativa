from django.shortcuts import render

from framework.models import NIVELES, Dimension


def matriz(request):
    """Matriz de construcción del Framework: dimensiones → variables → indicadores → KPIs."""
    dimensiones = Dimension.objects.prefetch_related("variables__indicadores").all()
    total_peso = sum(d.peso for d in dimensiones) or 1.0
    filas = []
    for dim in dimensiones:
        indicadores = [i for v in dim.variables.all() for i in v.indicadores.all()]
        filas.append(
            {
                "dimension": dim,
                "peso_normalizado": round(dim.peso / total_peso, 3),
                "variables": dim.variables.all(),
                "n_indicadores": len(indicadores),
            }
        )
    return render(
        request,
        "framework/matriz.html",
        {"filas": filas, "niveles": NIVELES.items()},
    )
