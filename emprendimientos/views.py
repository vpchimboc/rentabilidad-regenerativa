import csv

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from administracion.models import ConfiguracionSistema, registrar
from administracion.permisos import PERMISO_EXPORTAR, requiere_permiso
from core.indicadores import ORIGENES, filtrar_emprendimientos
from emprendimientos.models import Emprendimiento, Evaluacion, Periodo
from framework.services import elasticidad, evaluar
from rna.services import predecir


def _filtros(request):
    sector = request.GET.get("sector", "")
    origen = request.GET.get("origen", "")
    return {
        "q": request.GET.get("q", "").strip(),
        "sector": sector if sector in dict(Emprendimiento.SECTORES) else "",
        "provincia": request.GET.get("provincia", "").strip(),
        "origen": origen if origen in dict(ORIGENES) else "",
    }


def lista(request):
    filtros = _filtros(request)
    qs = filtrar_emprendimientos(**filtros).prefetch_related("periodos")
    pagina = Paginator(qs, ConfiguracionSistema.actual().registros_por_pagina).get_page(request.GET.get("pagina"))
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    return render(
        request,
        "emprendimientos/lista.html",
        {
            "pagina": pagina,
            "total": qs.count(),
            "filtros": filtros,
            "parametros": parametros.urlencode(),
            "sectores": Emprendimiento.SECTORES,
            "provincias": (Emprendimiento.objects.exclude(provincia="")
                           .values_list("provincia", flat=True).distinct().order_by("provincia")),
            "origenes": ORIGENES,
            "puede_exportar": request.user.has_perm(PERMISO_EXPORTAR),
        },
    )


@requiere_permiso(PERMISO_EXPORTAR)
def exportar(request):
    """CSV de los emprendimientos filtrados con su período más reciente."""
    filtros = _filtros(request)
    qs = filtrar_emprendimientos(**filtros).prefetch_related("periodos")
    respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = 'attachment; filename="emprendimientos.csv"'
    respuesta.write("﻿")  # BOM: Excel abre bien las tildes
    escritor = csv.writer(respuesta, delimiter=";")
    escritor.writerow(["Nombre", "RUC", "Sector", "Provincia", "Ciudad", "Empleados", "Año",
                       "Ventas (USD)", "Costos fijos (USD)", "Costos variables (USD)",
                       "Punto de equilibrio (USD)", "Fuente", "URL de verificación"])
    for e in qs:
        p = e.periodos.all()[0] if e.periodos.all() else None
        escritor.writerow([
            e.nombre, e.ruc, e.get_sector_display(), e.provincia, e.ciudad, e.empleados,
            p.anio if p else "", p.ventas if p else "", p.costos_fijos if p else "",
            p.costos_variables if p else "", round(p.punto_equilibrio, 2) if p else "",
            e.fuente, e.fuente_url,
        ])
    registrar("EXPORTAR", request.user, "Emprendimiento", f"{qs.count()} registros", filtros=filtros)
    return respuesta


def detalle(request, pk):
    emp = get_object_or_404(Emprendimiento, pk=pk)
    return render(
        request,
        "emprendimientos/detalle.html",
        {
            "emp": emp,
            "periodos": emp.periodos.prefetch_related("mediciones__indicador"),
        },
    )


def evaluar_periodo(request, pk):
    """Calcula el IRR del período y guarda la evaluación."""
    periodo = get_object_or_404(Periodo, pk=pk)
    mediciones = periodo.mediciones_dict()
    resultado, elasticidades = elasticidad(mediciones)

    if request.method == "POST":
        Evaluacion.objects.create(
            periodo=periodo,
            irr=resultado["irr"],
            media_aritmetica=resultado["media_aritmetica"],
            minimo_dimensional=resultado["minimo_dimensional"],
            veredicto=resultado["veredicto"],
            cuello_de_botella=resultado["cuello_de_botella"] or "",
            detalle={
                "dimensiones": [
                    {
                        "codigo": d["dimension"].codigo,
                        "nivel": d["nivel"],
                        "peso": d["peso"],
                    }
                    for d in resultado["dimensiones"]
                ]
            },
        )
        messages.success(request, f"Evaluación guardada. IRR = {resultado['irr']:.4f}")
        return redirect("emprendimiento_detalle", pk=periodo.emprendimiento_id)

    return render(
        request,
        "emprendimientos/evaluacion.html",
        {
            "periodo": periodo,
            "r": resultado,
            "elasticidades": elasticidades,
            "rna": predecir(mediciones),
        },
    )
