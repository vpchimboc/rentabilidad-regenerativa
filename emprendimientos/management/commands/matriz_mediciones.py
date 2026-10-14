"""Matriz de mediciones: plantilla para completar KPI de empresas ya registradas e importarla.

    manage.py matriz_mediciones empresas [archivo.csv]                  → empresas con ID, RUC y enlaces
    manage.py matriz_mediciones exportar [archivo.csv] [--dimensiones D2 D3 D4]
    manage.py matriz_mediciones importar archivo.csv                    → simulación (no guarda)
    manage.py matriz_mediciones importar archivo.csv --aplicar          → guarda y registra en auditoría

Formato largo: una fila por período (empresa × año) y KPI. La empresa se identifica por
id_periodo (o, si falta, por RUC + año); nunca se crean empresas nuevas. CSV con «;» y
UTF-8 con BOM para abrirse en Excel. Reglas (§2.12): las filas sin estado ni valor se
ignoran; OBS exige valor (o numerador y denominador) y fuente; ND, NA y NV exigen
evidencia; ningún faltante se convierte en cero.
"""

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from administracion.models import registrar
from emprendimientos.models import Emprendimiento, Medicion, Periodo
from framework.models import Indicador

COLUMNAS = [
    "id_periodo", "ruc", "empresa", "anio", "codigo", "dimension", "indicador", "formula", "unidad",
    "estado", "valor", "numerador", "denominador", "fuente", "evidencia", "fecha", "responsable",
]
COLUMNAS_EMPRESAS = [
    "id_emprendimiento", "id_periodo", "ruc", "empresa", "sector", "provincia", "ciudad", "ciiu",
    "empleados", "anio", "fuente", "url_verificacion",
]
CARPETA = Path(settings.BASE_DIR) / "manual"


def _fmt(v):
    return "" if v is None else str(v).replace(".", ",")


def _num(texto, campo, ref):
    texto = (texto or "").strip().replace(",", ".")
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError as error:
        raise CommandError(f"{ref}: «{campo}» no es un número ({texto})") from error


class Command(BaseCommand):
    help = "Exporta la plantilla de mediciones o importa los KPI completados para empresas registradas."

    def add_arguments(self, parser):
        parser.add_argument("accion", choices=["empresas", "exportar", "importar"])
        parser.add_argument("archivo", nargs="?")
        parser.add_argument("--dimensiones", nargs="+", default=["D2", "D3", "D4"])
        parser.add_argument("--aplicar", action="store_true")

    def handle(self, *args, accion, archivo, dimensiones, aplicar, **opts):
        if accion == "empresas":
            self._empresas(Path(archivo) if archivo else CARPETA / "empresas_FRR.csv")
        elif accion == "exportar":
            self._exportar(Path(archivo) if archivo else CARPETA / "plantilla_mediciones_FRR.csv", dimensiones)
        else:
            if not archivo:
                raise CommandError("Indique el archivo CSV a importar")
            self._importar(Path(archivo), aplicar)

    def _periodos(self):
        return Periodo.objects.select_related("emprendimiento").order_by("emprendimiento__nombre", "anio")

    def _empresas(self, ruta):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(COLUMNAS_EMPRESAS)
            for p in self._periodos():
                e = p.emprendimiento
                w.writerow([e.pk, p.pk, e.ruc, e.nombre, e.get_sector_display(), e.provincia, e.ciudad,
                            e.ciiu, e.empleados, p.anio, e.fuente, e.fuente_url])
        self.stdout.write(self.style.SUCCESS(f"Empresas exportadas: {ruta}"))

    def _exportar(self, ruta, dimensiones):
        indicadores = list(Indicador.objects.select_related("variable__dimension")
                           .filter(variable__dimension__codigo__in=dimensiones))
        if not indicadores:
            raise CommandError(f"No hay KPI en las dimensiones {dimensiones}")
        ruta.parent.mkdir(parents=True, exist_ok=True)
        n = 0
        with ruta.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(COLUMNAS)
            for p in self._periodos().prefetch_related("mediciones"):
                med = {m.indicador_id: m for m in p.mediciones.all()}
                for i in indicadores:
                    m = med.get(i.pk)
                    w.writerow([
                        p.pk, p.emprendimiento.ruc, p.emprendimiento.nombre, p.anio, i.codigo,
                        i.variable.dimension.codigo, i.nombre, i.formula, i.unidad,
                        m.estado if m else "", _fmt(m.valor) if m else "", _fmt(m.numerador) if m else "",
                        _fmt(m.denominador) if m else "", m.fuente if m else "", m.observaciones if m else "",
                        m.fecha_medicion.isoformat() if m and m.fecha_medicion else "", m.responsable if m else "",
                    ])
                    n += 1
        self.stdout.write(self.style.SUCCESS(f"Plantilla exportada ({n} filas): {ruta}"))

    def _periodo(self, fila, ref):
        pid = (fila.get("id_periodo") or "").strip()
        if pid:
            try:
                return Periodo.objects.get(pk=int(pid))
            except (ValueError, Periodo.DoesNotExist) as error:
                raise CommandError(f"{ref}: id_periodo «{pid}» no existe") from error
        ruc, anio = (fila.get("ruc") or "").strip(), (fila.get("anio") or "").strip()
        if not ruc or not anio:
            raise CommandError(f"{ref}: falta id_periodo (o RUC y año)")
        if not Emprendimiento.objects.filter(ruc=ruc).exists():
            raise CommandError(f"{ref}: RUC {ruc} no está registrado (no se crean empresas nuevas)")
        p = Periodo.objects.filter(emprendimiento__ruc=ruc, anio=anio).first()
        if p is None:
            raise CommandError(f"{ref}: la empresa {ruc} no tiene período {anio}")
        return p

    @transaction.atomic
    def _importar(self, ruta, aplicar):
        if not ruta.is_file():
            raise CommandError(f"No existe {ruta}")
        with ruta.open(encoding="utf-8-sig", newline="") as fh:
            muestra = fh.read(2048)
            fh.seek(0)
            filas = list(csv.DictReader(fh, delimiter=";" if ";" in muestra else ","))
        estados = dict(Medicion.ESTADOS)
        indicadores = {i.codigo: i for i in Indicador.objects.all()}
        nuevas = actualizadas = ignoradas = 0
        cambios = []
        for n, fila in enumerate(filas, start=2):
            codigo = (fila.get("codigo") or "").strip()
            ref = f"Fila {n} ({codigo or 'sin código'})"
            estado = (fila.get("estado") or "").strip().upper()
            valor = _num(fila.get("valor"), "valor", ref)
            numerador = _num(fila.get("numerador"), "numerador", ref)
            denominador = _num(fila.get("denominador"), "denominador", ref)
            if not estado and valor is None and numerador is None:
                ignoradas += 1
                continue
            if codigo not in indicadores:
                raise CommandError(f"{ref}: KPI desconocido")
            periodo = self._periodo(fila, ref)
            estado = estado or Medicion.OBS
            if estado not in estados:
                raise CommandError(f"{ref}: estado inválido (OBS, ND, NA, NV)")
            fuente = (fila.get("fuente") or "").strip()
            evidencia = (fila.get("evidencia") or "").strip()
            if estado == Medicion.OBS:
                if valor is None and (numerador is None or denominador is None):
                    raise CommandError(f"{ref}: OBS requiere valor o numerador y denominador")
                if not fuente:
                    raise CommandError(f"{ref}: OBS requiere la fuente verificable del dato")
            else:
                if not evidencia:
                    raise CommandError(f"{ref}: {estado} requiere la justificación en «evidencia»")
                valor = numerador = denominador = None
            datos = {
                "estado": estado, "valor": valor, "numerador": numerador, "denominador": denominador,
                "fuente": fuente[:160], "observaciones": evidencia[:300],
                "fecha_medicion": (fila.get("fecha") or "").strip() or None,
                "responsable": (fila.get("responsable") or "").strip()[:120],
            }
            existe = Medicion.objects.filter(periodo=periodo, indicador=indicadores[codigo]).exists()
            nuevas += not existe
            actualizadas += existe
            cambios.append(f"{periodo.pk}:{codigo}={estado}")
            if aplicar:
                m, _ = Medicion.objects.get_or_create(periodo=periodo, indicador=indicadores[codigo],
                                                      defaults={"estado": estado})
                for k, v in datos.items():
                    setattr(m, k, v)
                m.full_clean(exclude=["periodo", "indicador"])
                m.save()
        resumen = f"{nuevas} nuevas, {actualizadas} actualizadas, {ignoradas} filas vacías ignoradas"
        if aplicar and cambios:
            registrar("IMPORTAR",None, "Medicion", f"Matriz de mediciones importada ({resumen})",
                      archivo=ruta.name, filas=len(cambios))
            self.stdout.write(self.style.SUCCESS(f"Mediciones guardadas: {resumen}."))
        else:
            self.stdout.write(self.style.WARNING(f"Simulación: {resumen}. Use --aplicar para guardar."))
