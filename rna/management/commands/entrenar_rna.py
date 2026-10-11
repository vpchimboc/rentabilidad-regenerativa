from django.core.management.base import BaseCommand

from rna.services import entrenar


class Command(BaseCommand):
    help = "Entrena la red neuronal con los parámetros por defecto y la deja activa."

    def add_arguments(self, parser):
        parser.add_argument("--muestras", type=int, default=600)
        parser.add_argument("--ocultas", type=int, default=8)
        parser.add_argument("--epocas", type=int, default=300)

    def handle(self, *args, muestras, ocultas, epocas, **opts):
        modelo = entrenar(n_muestras=muestras, n_ocultas=ocultas, epocas=epocas)
        self.stdout.write(self.style.SUCCESS(
            f"RNA entrenada: MLP {modelo.n_entradas}-{modelo.n_ocultas}-1 · R² {modelo.metricas.get('r2')}"
        ))
