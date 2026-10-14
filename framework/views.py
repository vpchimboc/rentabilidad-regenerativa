from django.shortcuts import render

from framework.management.commands.cargar_framework import CORRESPONDENCIA_V0
from framework.models import Dimension, Indicador, ParametrosFRR
from framework.services import CLASIFICACIONES, NOMBRES_G


def matriz(request):
    """Matriz de construcción del FRR: dimensiones, KPI candidatos, fichas y parámetros."""
    dimensiones = list(Dimension.objects.prefetch_related("variables__indicadores").all())
    total_peso = sum(d.peso for d in dimensiones) or 1.0
    filas = []
    for dim in dimensiones:
        indicadores = [i for v in dim.variables.all() for i in v.indicadores.all()]
        filas.append({
            "dimension": dim,
            "alfa": round(dim.peso / total_peso, 3),
            "variables": dim.variables.all(),
            "n_indicadores": len(indicadores),
            "n_puntuables": sum(1 for i in indicadores if i.puntuable),
        })
    return render(request, "framework/matriz.html", {
        "filas": filas,
        "parametros": ParametrosFRR.vigentes(),
        "total_kpi": Indicador.objects.count(),
        "total_puntuables": sum(1 for i in Indicador.objects.all() if i.puntuable),
        "clasificaciones": [(k, v[0], v[1]) for k, v in CLASIFICACIONES.items()],
        "salvaguardas": NOMBRES_G.items(),
        "correspondencia": CORRESPONDENCIA_V0,
    })
