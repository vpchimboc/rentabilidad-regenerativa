from django.db.models import Count
from django.shortcuts import render

from bibliometria.models import Referencia, RegistroPRISMA


def matriz(request):
    """Matriz bibliográfica + flujo PRISMA + distribución por base y por año."""
    referencias = Referencia.objects.all()
    base = request.GET.get("base")
    if base:
        referencias = referencias.filter(base=base)

    por_base = (
        Referencia.objects.values("base").annotate(n=Count("id")).order_by("-n")
    )
    etiquetas_base = dict(Referencia.BASES)
    for fila in por_base:
        fila["nombre"] = etiquetas_base.get(fila["base"], fila["base"])

    por_anio = (
        Referencia.objects.values("anio").annotate(n=Count("id")).order_by("anio")
    )
    maximo = max([f["n"] for f in por_anio], default=1)
    for fila in por_anio:
        fila["pct"] = round(100 * fila["n"] / maximo)

    return render(
        request,
        "bibliometria/matriz.html",
        {
            "referencias": referencias,
            "por_base": por_base,
            "por_anio": por_anio,
            "prisma": RegistroPRISMA.objects.all(),
            "filtro_base": base,
            "bases": Referencia.BASES,
            "incluidas": Referencia.objects.filter(incluida=True).count(),
        },
    )
