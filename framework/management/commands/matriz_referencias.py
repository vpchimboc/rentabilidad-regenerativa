"""Matriz de referencias L/U del FRR: exportar para el investigador e importar la versión justificada.

    manage.py matriz_referencias exportar [archivo.csv]
    manage.py matriz_referencias importar archivo.csv            → simulación (no guarda)
    manage.py matriz_referencias importar archivo.csv --aplicar  → guarda y registra en auditoría

El CSV usa «;» y UTF-8 con BOM para abrirse directamente en Excel. La importación solo
modifica referencias y su ficha (L, U, T, H, fuente, tipo, periodo, evidencia y estado);
nunca cambia códigos ni fórmulas. Reglas: U > L, H > 0 y, si hay referencias, deben tener
fuente y tipo de fuente (§2.5: no se aceptan límites sin justificación).
"""

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from administracion.models import registrar
from framework.models import Indicador

COLUMNAS = [
    "codigo", "dimension", "indicador", "formula", "unidad", "sentido", "estado_kpi",
    "L", "U", "T", "H", "tipo_fuente", "fuente", "periodo", "evidencia", "estado_referencia",
    "correspondencia_v0",
]
EDITABLES = ["L", "U", "T", "H", "tipo_fuente", "fuente", "periodo", "evidencia", "estado_referencia", "estado_kpi"]
SALIDA = Path(settings.BASE_DIR) / "manual" / "matriz_referencias_FRR.csv"


def _num(texto, campo, codigo):
    texto = (texto or "").strip().replace(",", ".")
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError as error:
        raise CommandError(f"{codigo}: «{campo}» no es un número ({texto})") from error


class Command(BaseCommand):
    help = "Exporta o importa la matriz de referencias L/U de los KPI."

    def add_arguments(self, parser):
        parser.add_argument("accion", choices=["exportar", "importar"])
        parser.add_argument("archivo", nargs="?")
        parser.add_argument("--aplicar", action="store_true")

    def handle(self, *args, accion, archivo, aplicar, **opts):
        if accion == "exportar":
            self._exportar(Path(archivo) if archivo else SALIDA)
        else:
            if not archivo:
                raise CommandError("Indique el archivo CSV a importar")
            self._importar(Path(archivo), aplicar)

    def _exportar(self, ruta):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(COLUMNAS)
            for i in Indicador.objects.select_related("variable__dimension"):
                fmt = lambda v: "" if v is None else str(v).replace(".", ",")
                w.writerow([
                    i.codigo, i.variable.dimension.codigo, i.nombre, i.formula, i.unidad, i.tipo, i.estado,
                    fmt(i.ref_l), fmt(i.ref_u), fmt(i.ref_t), fmt(i.ref_h), i.tipo_fuente_referencia,
                    i.fuente_referencia, i.periodo_referencia, i.evidencia_referencia, i.estado_referencia,
                    i.equivalencia_v0,
                ])
        self.stdout.write(self.style.SUCCESS(f"Matriz exportada: {ruta}"))

    @transaction.atomic
    def _importar(self, ruta, aplicar):
        if not ruta.is_file():
            raise CommandError(f"No existe {ruta}")
        tipos = dict(Indicador.FUENTES_REF)
        estados = dict(Indicador.ESTADOS_REF)
        estados_kpi = dict(Indicador.ESTADOS)
        with ruta.open(encoding="utf-8-sig", newline="") as fh:
            muestra = fh.read(2048)
            fh.seek(0)
            filas = list(csv.DictReader(fh, delimiter=";" if ";" in muestra else ","))
        cambios = {}
        for fila in filas:
            codigo = (fila.get("codigo") or "").strip()
            try:
                ind = Indicador.objects.get(codigo=codigo)
            except Indicador.DoesNotExist as error:
                raise CommandError(f"KPI desconocido: «{codigo}»") from error
            nuevo = {
                "ref_l": _num(fila.get("L"), "L", codigo), "ref_u": _num(fila.get("U"), "U", codigo),
                "ref_t": _num(fila.get("T"), "T", codigo), "ref_h": _num(fila.get("H"), "H", codigo),
                "tipo_fuente_referencia": (fila.get("tipo_fuente") or "").strip().upper(),
                "fuente_referencia": (fila.get("fuente") or "").strip(),
                "periodo_referencia": (fila.get("periodo") or "").strip(),
                "evidencia_referencia": (fila.get("evidencia") or "").strip(),
                "estado_referencia": (fila.get("estado_referencia") or "PROP").strip().upper(),
                "estado": (fila.get("estado_kpi") or ind.estado).strip().upper(),
            }
            if nuevo["ref_l"] is not None and nuevo["ref_u"] is not None and nuevo["ref_u"] <= nuevo["ref_l"]:
                raise CommandError(f"{codigo}: U debe ser mayor que L")
            if nuevo["ref_h"] is not None and nuevo["ref_h"] <= 0:
                raise CommandError(f"{codigo}: H debe ser mayor que 0")
            tiene_ref = any(nuevo[k] is not None for k in ("ref_l", "ref_u", "ref_t", "ref_h"))
            if tiene_ref and (not nuevo["fuente_referencia"] or nuevo["tipo_fuente_referencia"] not in tipos):
                raise CommandError(f"{codigo}: tiene L/U pero falta la fuente o el tipo (MAT, NOR, SEC, EMP)")
            if nuevo["estado_referencia"] not in estados:
                raise CommandError(f"{codigo}: estado de referencia inválido (PROP, JUST, REV, VAL)")
            if nuevo["estado"] not in estados_kpi:
                raise CommandError(f"{codigo}: estado del KPI inválido (CAND, ACT, EXCL)")
            dif = {k: [getattr(ind, k), v] for k, v in nuevo.items() if getattr(ind, k) != v}
            if dif:
                cambios[codigo] = {k: [str(a), str(b)] for k, (a, b) in dif.items()}
                self.stdout.write(f"  {codigo}: " + ", ".join(f"{k} {a!r} → {b!r}" for k, (a, b) in dif.items()))
                if aplicar:
                    for k, v in nuevo.items():
                        setattr(ind, k, v)
                    ind.save()
        if not cambios:
            self.stdout.write("Sin cambios respecto de la configuración actual.")
        elif aplicar:
            registrar("CONFIG", None, "Indicador", f"Matriz de referencias importada ({len(cambios)} KPI)",
                      archivo=ruta.name, cambios=cambios)
            self.stdout.write(self.style.SUCCESS(f"Referencias actualizadas en {len(cambios)} KPI."))
        else:
            self.stdout.write(self.style.WARNING(f"Simulación: {len(cambios)} KPI cambiarían. Use --aplicar."))
