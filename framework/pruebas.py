"""Utilidades exclusivas de las pruebas automatizadas.

Asigna referencias L/U ficticias para poder verificar el cálculo completo del FRR.
No se usan en producción: allí las referencias requieren sustento documentado (§2.5).
"""

from framework.models import Indicador

REFERENCIAS_PRUEBA = {
    "E4": (0.5, 2.5), "E5": (-0.2, 0.3),
    "A1": (0.1, 2.0), "A3": (0.5, 3.0), "A5": (0.01, 0.05), "A6": (0.5, 5.0), "A7": (0.05, 1.2),
    "A10": (-10.0, 20.0), "S4": (0.0, 6.0), "S11": (-10.0, 20.0),
    "O1": (0.0, 100.0), "O6": (0.0, 48.0), "O8": (0.0, 72.0),
}


def asignar_referencias_prueba():
    for ind in Indicador.objects.all():
        if ind.tipo == Indicador.OBJETIVO:
            ind.ref_t, ind.ref_h = 0.5, 0.5
        else:
            ind.ref_l, ind.ref_u = REFERENCIAS_PRUEBA.get(ind.codigo, (0.0, 1.0))
        ind.fuente_referencia = "Referencias ficticias de prueba"
        ind.save()
