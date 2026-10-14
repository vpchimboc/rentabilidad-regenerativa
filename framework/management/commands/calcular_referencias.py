"""Fija referencias de normalización L/U a partir de la distribución observada.

Sustento: L = percentil 10 y U = percentil 90 de los valores observados (estado OBS)
de cada KPI en la base, cuando hay al menos `--minimo` observaciones. Las referencias
quedan marcadas como PROVISIONALES con su fuente y número de casos: la especificación
(§2.5) exige referencias justificadas y su revisión sectorial o experta posterior.

Por defecto solo muestra el resultado; con --aplicar las guarda (y deja constancia en
la auditoría). Nunca sobrescribe referencias existentes salvo con --sobrescribir.
"""

from django.core.management.base import BaseCommand

from administracion.models import registrar
from emprendimientos.models import Medicion
from framework.models import Indicador


def percentil(valores, p):
    datos = sorted(valores)
    if not datos:
        return None
    k = (len(datos) - 1) * p
    f = int(k)
    c = min(f + 1, len(datos) - 1)
    return datos[f] + (datos[c] - datos[f]) * (k - f)


class Command(BaseCommand):
    help = "Calcula referencias L/U provisionales (P10–P90) desde los datos observados."

    def add_arguments(self, parser):
        parser.add_argument("--minimo", type=int, default=20, help="Observaciones mínimas por KPI")
        parser.add_argument("--aplicar", action="store_true")
        parser.add_argument("--sobrescribir", action="store_true")

    def handle(self, *args, minimo, aplicar, sobrescribir, **opts):
        cambios = {}
        for ind in Indicador.objects.exclude(tipo=Indicador.OBJETIVO).order_by("codigo"):
            valores = list(Medicion.objects.filter(indicador=ind, estado=Medicion.OBS, valor__isnull=False)
                           .values_list("valor", flat=True))
            if len(valores) < minimo:
                continue
            if ind.puntuable and not sobrescribir:
                self.stdout.write(f"  {ind.codigo}: ya tiene referencias ({ind.fuente_referencia}); se conservan")
                continue
            l, u = round(percentil(valores, 0.10), 6), round(percentil(valores, 0.90), 6)
            if u <= l:
                self.stdout.write(self.style.WARNING(f"  {ind.codigo}: distribución sin dispersión; no se fija"))
                continue
            fuente = f"Percentiles P10–P90 de la muestra observada (n={len(valores)}); provisional"
            self.stdout.write(f"  {ind.codigo} {ind.nombre}: L={l:.4f} · U={u:.4f} · n={len(valores)}")
            cambios[ind.codigo] = {"L": [ind.ref_l, l], "U": [ind.ref_u, u], "n": len(valores)}
            if aplicar:
                ind.ref_l, ind.ref_u = l, u
                ind.fuente_referencia, ind.referencia_provisional = fuente, True
                ind.save(update_fields=["ref_l", "ref_u", "fuente_referencia", "referencia_provisional"])

        if not cambios:
            self.stdout.write("Ningún KPI alcanza el mínimo de observaciones sin referencias previas.")
        elif aplicar:
            registrar("CONFIG", None, "Indicador", f"Referencias L/U provisionales ({len(cambios)} KPI)", cambios=cambios)
            self.stdout.write(self.style.SUCCESS(f"Referencias guardadas para {len(cambios)} KPI."))
        else:
            self.stdout.write(self.style.WARNING("Simulación: use --aplicar para guardarlas."))
