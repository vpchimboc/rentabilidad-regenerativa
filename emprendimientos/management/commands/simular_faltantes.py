"""Simula los KPI faltantes de D2–D4 en las empresas registradas, marcados como SIMULADO.

    manage.py simular_faltantes                 → simulación en pantalla (no guarda)
    manage.py simular_faltantes --aplicar       → guarda las mediciones simuladas
    manage.py simular_faltantes --eliminar      → borra todas las mediciones simuladas

Solo completa KPI sin ningún registro: nunca reemplaza datos reales ni justificaciones
ND/NA/NV. Los KPI con L/U se sortean dentro de [L, U]; los que no tienen referencias no
puntúan y reciben un valor simulado sin escala (0–1) solo para que la cobertura refleje un
levantamiento completo. Todas quedan con simulado=True, fuente «SIMULADO» y se excluyen
del cálculo de referencias y de la plantilla de datos reales. Las salvaguardas G1–G5 no
se simulan.
"""

import random

from django.core.management.base import BaseCommand
from django.db import transaction

from administracion.models import registrar
from emprendimientos.models import Medicion, Periodo
from framework.models import Indicador

FUENTE = "SIMULADO"


class Command(BaseCommand):
    help = "Simula los KPI faltantes de D2–D4 (marcados como SIMULADO) o los elimina."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true")
        parser.add_argument("--eliminar", action="store_true")
        parser.add_argument("--dimensiones", nargs="+", default=["D2", "D3", "D4"])
        parser.add_argument("--semilla", type=int, default=2026)

    @transaction.atomic
    def handle(self, *args, aplicar, eliminar, dimensiones, semilla, **opts):
        if eliminar:
            n, _ = Medicion.objects.filter(simulado=True).delete()
            registrar("CONFIG", None, "Medicion", f"Mediciones simuladas eliminadas ({n})")
            self.stdout.write(self.style.SUCCESS(f"Mediciones simuladas eliminadas: {n}"))
            return
        rng = random.Random(semilla)
        indicadores = list(Indicador.objects.filter(variable__dimension__codigo__in=dimensiones)
                           .exclude(estado=Indicador.EXCLUIDO))
        nuevas, puntuables = [], 0
        for p in Periodo.objects.prefetch_related("mediciones"):
            existentes = {m.indicador_id for m in p.mediciones.all()}
            for ind in indicadores:
                if ind.pk in existentes:
                    continue
                if ind.puntuable and ind.tipo == Indicador.OBJETIVO:
                    valor = rng.uniform(ind.ref_t - ind.ref_h, ind.ref_t + ind.ref_h)
                elif ind.puntuable:
                    valor = rng.uniform(ind.ref_l, ind.ref_u)
                else:
                    valor = rng.random()
                puntuables += ind.puntuable
                nuevas.append(Medicion(
                    periodo=p, indicador=ind, estado=Medicion.OBS, valor=round(valor, 6), unidad=ind.unidad,
                    fuente=FUENTE, simulado=True, responsable="Simulación",
                    observaciones=("Valor simulado dentro de [L, U]" if ind.puntuable
                                   else "Valor simulado sin escala: KPI sin L/U, no puntúa")
                                  + f" (semilla {semilla}); no es un dato verificado de la empresa",
                ))
        resumen = f"{len(nuevas)} mediciones simuladas ({puntuables} puntuables) en {Periodo.objects.count()} períodos"
        if aplicar:
            Medicion.objects.bulk_create(nuevas)
            registrar("CONFIG", None, "Medicion", f"Datos faltantes simulados: {resumen}", semilla=semilla)
            self.stdout.write(self.style.SUCCESS(f"Guardadas: {resumen}. Para quitarlas: --eliminar"))
        else:
            self.stdout.write(self.style.WARNING(f"Simulación: se crearían {resumen}. Use --aplicar."))
