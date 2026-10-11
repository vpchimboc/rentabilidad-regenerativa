from django.contrib import messages
from django.shortcuts import redirect, render

from rna.models import ModeloRNA
from rna.services import entrenar, indicadores_entrada, modelo_activo, predecir


def panel(request):
    modelo = modelo_activo()
    return render(
        request,
        "rna/panel.html",
        {
            "modelo": modelo,
            "modelos": ModeloRNA.objects.all()[:10],
            "entradas": indicadores_entrada(),
        },
    )


def entrenar_modelo(request):
    if request.method != "POST":
        return redirect("rna_panel")
    try:
        n_muestras = int(request.POST.get("n_muestras", 600))
        n_ocultas = int(request.POST.get("n_ocultas", 8))
        epocas = int(request.POST.get("epocas", 300))
        lr = float(request.POST.get("lr", 0.05))
    except (TypeError, ValueError):
        messages.error(request, "Parámetros de entrenamiento inválidos.")
        return redirect("rna_panel")

    modelo = entrenar(n_muestras=n_muestras, n_ocultas=n_ocultas, epocas=epocas, lr=lr)
    messages.success(
        request,
        f"Modelo entrenado con {n_muestras} muestras simuladas. "
        f"R² = {modelo.metricas.get('r2')} · RMSE = {modelo.metricas.get('rmse')}",
    )
    return redirect("rna_panel")


def predecir_vista(request):
    """Formulario de predicción manual: se ingresan los indicadores y la red estima el IRR."""
    entradas = indicadores_entrada()
    valores, resultado = {}, None

    if request.method == "POST":
        for ind in entradas:
            try:
                valores[ind.codigo] = float(request.POST.get(ind.codigo, ""))
            except (TypeError, ValueError):
                valores[ind.codigo] = None
        resultado = predecir({k: v for k, v in valores.items() if v is not None})
        if resultado is None:
            messages.warning(request, "Primero debe entrenar un modelo de RNA.")

    filas = [{"ind": ind, "valor": valores.get(ind.codigo)} for ind in entradas]
    return render(
        request,
        "rna/predecir.html",
        {"filas": filas, "resultado": resultado},
    )
