from django.shortcuts import render

from administracion.models import ConfiguracionSistema
from bibliometria.models import Referencia
from core import indicadores as tablero_indicadores
from core.indicadores import ORIGENES
from delphi.models import Experto, ResultadoRonda, Ronda
from emprendimientos.models import Emprendimiento, Evaluacion
from escenarios.models import Escenario
from framework.models import Dimension, Indicador
from rna.models import ModeloRNA


def tablero(request):
    """Tablero de control: estado de la investigación por objetivo específico."""
    referencias = Referencia.objects.count()
    indicadores = Indicador.objects.count()
    modelo = ModeloRNA.objects.filter(activo=True).first()
    escenarios = Escenario.objects.count()
    resultado = ResultadoRonda.objects.order_by("-ronda__numero").first()

    objetivos = [
        {
            "n": 1,
            "titulo": "Revisión bibliométrica y documental",
            "modulo": "Bibliometría",
            "url": "/bibliometria/",
            "estado": referencias > 0,
            "dato": f"{referencias} referencias en la matriz",
        },
        {
            "n": 2,
            "titulo": "Definir dimensiones, variables e indicadores",
            "modulo": "Framework",
            "url": "/framework/",
            "estado": indicadores > 0,
            "dato": f"{Dimension.objects.count()} dimensiones · {indicadores} indicadores",
        },
        {
            "n": 3,
            "titulo": "Modelado mediante Redes Neuronales Artificiales",
            "modulo": "RNA",
            "url": "/rna/",
            "estado": modelo is not None,
            "dato": (
                f"MLP {modelo.n_entradas}-{modelo.n_ocultas}-1 · R² {modelo.metricas.get('r2')}"
                if modelo else "Sin modelo entrenado"
            ),
        },
        {
            "n": 4,
            "titulo": "Simulación de escenarios y análisis de sensibilidad",
            "modulo": "Escenarios",
            "url": "/escenarios/",
            "estado": escenarios > 0,
            "dato": f"{escenarios} escenarios simulados",
        },
        {
            "n": 5,
            "titulo": "Validación mediante método Delphi",
            "modulo": "Delphi",
            "url": "/delphi/",
            "estado": resultado is not None,
            "dato": (
                f"Ronda {resultado.ronda.numero} · S-CVI {resultado.s_cvi} · W {resultado.kendall_w}"
                if resultado else f"{Experto.objects.count()} expertos registrados"
            ),
        },
    ]

    config = ConfiguracionSistema.actual()
    filtros = {
        "sector": request.GET.get("sector", "") if request.GET.get("sector") in dict(Emprendimiento.SECTORES) else "",
        "provincia": request.GET.get("provincia", "").strip(),
        "origen": request.GET.get("origen", "") if request.GET.get("origen") in dict(ORIGENES) else "",
    }
    anio = request.GET.get("anio", "")
    anio = int(anio) if anio.isdigit() else config.anio_analisis
    datos = tablero_indicadores.calcular(anio=anio, umbral=float(config.umbral_alerta_break_even), **filtros)

    return render(
        request,
        "core/tablero.html",
        {
            "objetivos": objetivos,
            "d": datos,
            "filtros": filtros,
            "hay_filtros": any(filtros.values()) or bool(request.GET.get("anio")),
            "umbral": config.umbral_alerta_break_even,
            "sectores": Emprendimiento.SECTORES,
            "provincias": (Emprendimiento.objects.exclude(provincia="")
                           .values_list("provincia", flat=True).distinct().order_by("provincia")),
            "origenes": ORIGENES,
            "evaluaciones": Evaluacion.objects.select_related("periodo__emprendimiento")[:6],
            "rondas": Ronda.objects.count(),
        },
    )
