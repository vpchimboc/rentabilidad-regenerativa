"""Carga en la base el dataset de emprendimientos procedente de fuentes públicas.

Idempotente: identifica cada emprendimiento por RUC (o por nombre si no lo tiene) y
actualiza en lugar de duplicar. Solo crea mediciones para los indicadores que el
CSV trae con valor; el resto queda «sin dato» y la evaluación se informa como
incompleta, nunca como degenerativa.
"""

import csv
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from administracion.models import registrar
from administracion.senales import auditoria_silenciada
from emprendimientos.management.commands.preparar_dataset_publico import (
    SALIDA_POR_DEFECTO,
)
from emprendimientos.models import Emprendimiento, Medicion, Periodo
from framework.models import Indicador

CAMPOS_EMPRENDIMIENTO = ["sector", "ciudad", "provincia", "ciiu", "fuente", "fuente_url"]


def _decimal(valor):
    return float(valor) if valor not in (None, "") else 0.0


class Command(BaseCommand):
    help = "Importa emprendimientos ecuatorianos desde el CSV de fuentes públicas."

    def add_arguments(self, parser):
        parser.add_argument("archivo", nargs="?", default=str(SALIDA_POR_DEFECTO))

    def handle(self, *args, archivo, **opts):
        ruta = Path(archivo)
        if not ruta.is_file():
            raise CommandError(f"No existe el archivo {ruta}")
        try:
            with auditoria_silenciada():
                resumen = self._importar(ruta)
        except Exception as error:
            registrar("IMPORTAR", None, "Emprendimiento", ruta.name, resultado="ERROR", error=str(error)[:300])
            raise
        registrar("IMPORTAR", None, "Emprendimiento", f"{ruta.name}: {resumen['creados']} creados, "
                  f"{resumen['actualizados']} actualizados", **resumen)
        self.stdout.write(self.style.SUCCESS(
            f"Importación completa: {resumen['creados']} creados, {resumen['actualizados']} actualizados, "
            f"{resumen['periodos']} períodos, {resumen['mediciones']} mediciones."
        ))

    @transaction.atomic
    def _importar(self, ruta):
        if not Indicador.objects.exists():
            call_command("cargar_framework", stdout=self.stdout)
        indicadores = {i.codigo: i for i in Indicador.objects.all()}
        sectores = dict(Emprendimiento.SECTORES)

        creados = actualizados = periodos = mediciones = 0
        with ruta.open(encoding="utf-8", newline="") as fh:
            for n, fila in enumerate(csv.DictReader(fh), start=2):
                nombre = (fila.get("nombre") or "").strip()
                if not nombre:
                    raise CommandError(f"Línea {n}: falta el nombre")
                if fila.get("sector") not in sectores:
                    raise CommandError(f"Línea {n}: sector desconocido «{fila.get('sector')}»")
                ruc = (fila.get("ruc") or "").strip()
                if ruc and not (ruc.isdigit() and len(ruc) == 13):
                    raise CommandError(f"Línea {n}: RUC inválido «{ruc}»")

                datos = {c: (fila.get(c) or "").strip() for c in CAMPOS_EMPRENDIMIENTO}
                datos["ciudad"] = datos["ciudad"] or datos["provincia"].title()
                datos["empleados"] = int(_decimal(fila.get("empleados")))
                datos["descripcion"] = (fila.get("notas") or "").strip()
                datos["nombre"] = nombre
                clave = {"ruc": ruc} if ruc else {"nombre": nombre, "ruc": ""}
                emp, creado = Emprendimiento.objects.update_or_create(**clave, defaults=datos)
                creados += creado
                actualizados += not creado

                if not fila.get("anio"):
                    continue
                periodo, _ = Periodo.objects.update_or_create(
                    emprendimiento=emp,
                    anio=int(fila["anio"]),
                    defaults={
                        "etiqueta": "Estados financieros SCVS",
                        "ventas": _decimal(fila.get("ventas")),
                        "costos_fijos": _decimal(fila.get("costos_fijos")),
                        "costos_variables": _decimal(fila.get("costos_variables")),
                        "notas": datos["descripcion"],
                    },
                )
                periodos += 1
                for codigo, ind in indicadores.items():
                    valor = fila.get(codigo)
                    if valor in (None, ""):
                        continue
                    Medicion.objects.update_or_create(
                        periodo=periodo,
                        indicador=ind,
                        defaults={"valor": float(valor), "fuente": datos["fuente"][:160]},
                    )
                    mediciones += 1

        return {"creados": creados, "actualizados": actualizados, "periodos": periodos, "mediciones": mediciones}
