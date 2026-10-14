"""Deja en la base solo emprendimientos reales con datos utilizables por el framework.

Criterios de exclusión (se informa el motivo de cada uno):
  1. Casos de demostración creados por `cargar_demo` (ficticios).
  2. Registros sin fuente pública verificable ni período financiero (pruebas manuales).
  3. Sin período con estados financieros.
  4. Ventas iguales a cero.
  5. Punto de equilibrio no calculable (costos variables ≥ ventas).

Uso:
  manage.py limpiar_datos                   → solo muestra qué se eliminaría
  manage.py limpiar_datos --aplicar         → respalda db.sqlite3 y elimina
  manage.py limpiar_datos --depurar-csv     → además quita esas filas del CSV público
"""

import csv
import shutil
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from administracion.models import registrar
from administracion.senales import auditoria_silenciada
from core.management.commands.cargar_demo import EMPRENDIMIENTOS as DEMO
from emprendimientos.management.commands.preparar_dataset_publico import SALIDA_POR_DEFECTO
from emprendimientos.models import Emprendimiento

NOMBRES_DEMO = {e["nombre"] for e in DEMO}


def motivo_exclusion(emp):
    """Devuelve el motivo por el que el emprendimiento no sirve, o None si es utilizable."""
    if emp.nombre in NOMBRES_DEMO and not emp.fuente:
        return "caso de demostración (ficticio)"
    periodo = emp.periodos.order_by("-anio").first()
    if periodo is None:
        return "sin estados financieros" if emp.fuente else "registro manual sin fuente ni datos"
    if float(periodo.ventas) <= 0:
        return "ventas iguales a cero"
    if periodo.punto_equilibrio <= 0:
        return "punto de equilibrio no calculable (costos variables ≥ ventas)"
    return None


def fila_csv_utilizable(fila):
    try:
        ventas = float(fila.get("ventas") or 0)
        variables = float(fila.get("costos_variables") or 0)
    except ValueError:
        return False
    return bool(fila.get("anio")) and ventas > 0 and variables < ventas


class Command(BaseCommand):
    help = "Elimina casos ficticios y emprendimientos sin datos utilizables (por defecto, solo simula)."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Ejecuta la eliminación (con respaldo)")
        parser.add_argument("--depurar-csv", action="store_true",
                            help="Quita del CSV público las filas sin datos utilizables")

    def handle(self, *args, aplicar, depurar_csv, **opts):
        excluir = []
        for emp in Emprendimiento.objects.prefetch_related("periodos"):
            motivo = motivo_exclusion(emp)
            if motivo:
                excluir.append((emp, motivo))

        total = Emprendimiento.objects.count()
        self.stdout.write(f"Emprendimientos: {total} · utilizables: {total - len(excluir)} · a eliminar: {len(excluir)}\n")
        for emp, motivo in sorted(excluir, key=lambda t: (t[1], t[0].nombre)):
            self.stdout.write(f"  - {emp.nombre} [{motivo}]")

        if depurar_csv:
            self._depurar_csv(aplicar)

        if not aplicar:
            self.stdout.write(self.style.WARNING("\nSimulación: no se eliminó nada. Use --aplicar para ejecutar."))
            return
        if not excluir:
            self.stdout.write(self.style.SUCCESS("No hay nada que eliminar."))
            return

        db = Path(settings.DATABASES["default"]["NAME"])
        if db.is_file():
            respaldo = db.with_name(f"{db.name}.respaldo-limpieza-{datetime.now():%Y%m%d-%H%M%S}")
            shutil.copy2(db, respaldo)
            self.stdout.write(f"\nRespaldo: {respaldo}")

        with transaction.atomic(), auditoria_silenciada():
            ids = [emp.pk for emp, _ in excluir]
            borrados, por_modelo = Emprendimiento.objects.filter(pk__in=ids).delete()
        registrar("ELIMINAR", None, "Emprendimiento", f"Limpieza de datos: {len(ids)} emprendimientos",
                  motivos={m: sum(1 for _, x in excluir if x == m) for _, m in excluir})
        self.stdout.write(self.style.SUCCESS(
            f"Eliminados {len(ids)} emprendimientos ({borrados} registros en total, incluidos períodos, "
            f"mediciones, evaluaciones y escenarios). Quedan {Emprendimiento.objects.count()}."
        ))

    def _depurar_csv(self, aplicar):
        ruta = Path(SALIDA_POR_DEFECTO)
        if not ruta.is_file():
            self.stdout.write(self.style.WARNING(f"No existe {ruta}"))
            return
        with ruta.open(encoding="utf-8", newline="") as fh:
            lector = csv.DictReader(fh)
            columnas, filas = lector.fieldnames, list(lector)
        buenas = [f for f in filas if fila_csv_utilizable(f)]
        self.stdout.write(f"\nCSV público: {len(filas)} filas · utilizables: {len(buenas)} · a quitar: {len(filas) - len(buenas)}")
        if aplicar:
            with ruta.open("w", encoding="utf-8", newline="") as fh:
                escritor = csv.DictWriter(fh, fieldnames=columnas)
                escritor.writeheader()
                escritor.writerows(buenas)
            self.stdout.write(f"CSV depurado: {ruta}")
