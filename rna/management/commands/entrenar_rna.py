from django.core.management.base import BaseCommand

from rna.services import entrenar, entrenar_hibrido


class Command(BaseCommand):
    help = ("Entrena la red neuronal y la deja activa. Con --hibrido usa los KPI económicos reales de las "
            "empresas y simula D2–D4 (los datos simulados no se guardan en las empresas).")

    def add_arguments(self, parser):
        parser.add_argument("--muestras", type=int, default=600)
        parser.add_argument("--ocultas", type=int, default=8)
        parser.add_argument("--epocas", type=int, default=300)
        parser.add_argument("--hibrido", action="store_true")
        parser.add_argument("--repeticiones", type=int, default=10, help="Escenarios simulados por empresa (--hibrido)")

    def handle(self, *args, muestras, ocultas, epocas, hibrido, repeticiones, **opts):
        if hibrido:
            modelo = entrenar_hibrido(repeticiones=repeticiones, n_ocultas=ocultas, epocas=epocas)
            m = modelo.metricas
            self.stdout.write(self.style.SUCCESS(
                f"RNA híbrida: MLP {modelo.n_entradas}-{modelo.n_ocultas}-1 · {modelo.n_muestras} muestras · "
                f"{m['empresas_entrenamiento']} empresas de entrenamiento, {m['empresas_prueba']} de prueba "
                f"({m['empresas_omitidas_d1_incompleto']} omitidas por D1 incompleto) · "
                f"R² en empresas no vistas {m['r2_empresas_no_vistas']} · MAE {m['mae_empresas_no_vistas']}"
            ))
        else:
            modelo = entrenar(n_muestras=muestras, n_ocultas=ocultas, epocas=epocas)
            self.stdout.write(self.style.SUCCESS(
                f"RNA entrenada: MLP {modelo.n_entradas}-{modelo.n_ocultas}-1 · R² {modelo.metricas.get('r2')}"
            ))
