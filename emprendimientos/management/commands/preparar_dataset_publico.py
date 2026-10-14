"""Construye el dataset de emprendimientos ecuatorianos a partir de fuentes públicas.

Fuentes (descarga libre, sin credenciales):

* Superintendencia de Compañías, Valores y Seguros (SCVS) — Ranking empresarial
  https://appscvsmovil.supercias.gob.ec/ranking/reporte.html
    - recursos/bi_compania.csv  (expediente, RUC, razón social, tipo, provincia)
    - recursos/bi_ranking.csv   (estados financieros por compañía y año)
* B Lab Global — directorio «Find a B Corp», empresas con sede en Ecuador
  (exportado a emprendimientos/datos/fuentes/blab_ecuador_*.json).

Criterio de selección, reproducible:

1. Todas las Empresas B con sede en Ecuador. Si su razón social se identifica sin
   ambigüedad en el registro de la SCVS, se toman RUC y estados financieros.
2. Se completa con Sociedades por Acciones Simplificadas (SAS, la figura creada por
   la Ley Orgánica de Emprendimiento e Innovación de 2020) de la provincia elegida
   (Azuay por defecto), activas en el año del ranking, con ventas > 0 y de 1 a 49
   empleados. Se estratifica por sección CIIU y, dentro de cada sección, se toman
   las de mayores ventas.

Solo se derivan los KPI del catálogo FRR 1.0 cuya fórmula coincide con datos publicados
(E1–E5 de la dimensión económica). Las dimensiones ambiental, social y operacional no
tienen fuente pública: quedan sin dato (nunca como cero).
"""

import csv
import json
import re
import unicodedata
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

URL_RANKING = "https://appscvsmovil.supercias.gob.ec/ranking/reporte.html"
URL_BLAB = "https://www.bcorporation.net/en-us/find-a-b-corp/company/{slug}/"
SALIDA_POR_DEFECTO = Path(settings.BASE_DIR) / "emprendimientos" / "datos" / "emprendimientos_ecuador.csv"

COLUMNAS = [
    "origen", "nombre", "ruc", "sector", "ciudad", "provincia", "ciiu", "empleados",
    "fuente", "fuente_url", "anio", "ventas", "costos_fijos", "costos_variables",
    "utilidad_neta", "E1", "E2", "E3", "E4", "E5", "notas",
]

SECCIONES_COMPLEMENTO = ["A", "C", "G", "I", "J", "M"]

SECTOR_POR_CIIU = {"A": "AGRO", "C": "MANU", "G": "COME", "J": "TECN"}
SECTOR_POR_BLAB = {
    "Manufacturing": "MANU",
    "Agriculture/Growers": "AGRO",
    "Wholesale/Retail": "COME",
}

INDUSTRIAS_BLAB = {
    "Food products": "Productos alimenticios",
    "Beverages": "Bebidas",
    "Other insurance services": "Otros servicios de seguros",
    "Other personal services": "Otros servicios personales",
    "Health insurance": "Seguros de salud",
    "Agricultural Processing": "Procesamiento agrícola",
    "Cleaning products": "Productos de limpieza",
    "Deposit bank - Emerging Markets": "Banca de depósito (mercados emergentes)",
    "Data processing & hosting": "Procesamiento y alojamiento de datos",
    "Animal Production": "Producción animal",
    "Materials recovery & recycling": "Recuperación y reciclaje de materiales",
    "Accommodation": "Alojamiento",
    "Personal care products": "Productos de cuidado personal",
    "Mixed Farming": "Agricultura mixta",
    "Machinery & equipment": "Maquinaria y equipos",
    "Environmental consulting": "Consultoría ambiental",
    "Management consultant - for-profits": "Consultoría de gestión empresarial",
    "Facilities & cleaning services": "Servicios de instalaciones y limpieza",
    "Postal & courier activities": "Servicios postales y de mensajería",
}
SECTORES_BLAB = {
    "Manufacturing": "Manufactura",
    "Agriculture/Growers": "Agricultura / productores",
    "Wholesale/Retail": "Comercio mayorista / minorista",
    "Service with Minor Environmental Footprint": "Servicios con huella ambiental menor",
    "Service with Significant Environmental Footprint": "Servicios con huella ambiental significativa",
}

PROVINCIAS_BLAB = {"Pichincha Province": "PICHINCHA", "Guayas Province": "GUAYAS",
                   "Azuay Province": "AZUAY", "El Oro Province": "EL ORO",
                   "Manabí Province": "MANABI", "Galápagos Province": "GALAPAGOS"}

FORMAS_JURIDICAS = r"\b(S ?A ?S|SAS|S ?A|SA|CIA|CA|LTDA|BIC|B ?I ?C|SOCIEDAD ANONIMA|SL|C ?A)\b"


def normalizar(nombre):
    texto = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode()
    texto = re.sub(r"[^A-Za-z0-9 ]", " ", texto.upper())
    texto = re.sub(FORMAS_JURIDICAS, " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def num(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def indicadores(est, anterior=None):
    """KPI E1–E5 del FRR calculados con las fórmulas de la Fase 2 (§2.6).

    E1 margen de seguridad (V − PE)/V, con PE = CF/(1 − CV/V)
    E2 margen neto UN/V
    E3 ROA UN/A_prom, A_prom = (activos inicio + activos fin)/2 (requiere el año anterior)
    E4 razón corriente AC/PC (indicador «liquidez corriente» publicado por la SCVS)
    E5 crecimiento de ingresos (V_t − V_t−1)/V_t−1
    Un KPI no calculable se omite (queda ND), nunca se registra como cero.
    """
    ventas = num(est["ingresos_ventas"]) or 0.0
    cv = num(est["costos_ventas_prod"]) or 0.0
    cf = num(est["gastos_admin_ventas"]) or 0.0
    un = num(est["utilidad_neta"])
    activos = num(est["activos"])
    datos = {}
    if ventas > 0 and cv < ventas:
        pe = cf / (1 - cv / ventas)
        datos["E1"] = round((ventas - pe) / ventas, 6)
    if ventas > 0 and un is not None:
        datos["E2"] = round(un / ventas, 6)
    if anterior is not None and un is not None:
        activos_ant = num(anterior["activos"])
        if activos and activos_ant and activos + activos_ant > 0:
            datos["E3"] = round(un / ((activos + activos_ant) / 2), 6)
    liquidez = num(est["liquidez_corriente"])
    if liquidez is not None and liquidez > 0:
        datos["E4"] = round(liquidez, 6)
    if anterior is not None:
        ventas_ant = num(anterior["ingresos_ventas"]) or 0.0
        if ventas_ant > 0:
            datos["E5"] = round((ventas - ventas_ant) / ventas_ant, 6)
    return datos


class Command(BaseCommand):
    help = "Genera el CSV de emprendimientos ecuatorianos desde la SCVS y B Lab."

    def add_arguments(self, parser):
        parser.add_argument("--companias", required=True, help="Ruta a bi_compania.csv (SCVS)")
        parser.add_argument("--ranking", required=True, help="Ruta a bi_ranking.csv (SCVS)")
        parser.add_argument("--blab", required=True, help="JSON exportado del directorio de B Lab")
        parser.add_argument("--anio", type=int, default=2025)
        parser.add_argument("--provincia", default="AZUAY")
        parser.add_argument("--total", type=int, default=120)
        parser.add_argument("--salida", default=str(SALIDA_POR_DEFECTO))

    def handle(self, *args, **opts):
        for clave in ("companias", "ranking", "blab"):
            if not Path(opts[clave]).is_file():
                raise CommandError(f"No existe el archivo --{clave}: {opts[clave]}")

        companias = self._leer_companias(opts["companias"])
        ranking, self.anterior = self._leer_ranking(opts["ranking"], opts["anio"])
        self.stdout.write(f"SCVS: {len(companias)} compañías, {len(ranking)} estados {opts['anio']}.")

        filas = self._empresas_b(opts["blab"], companias, ranking, opts["anio"])
        rucs = {f["ruc"] for f in filas if f["ruc"]}
        faltan = max(0, opts["total"] - len(filas))
        filas += self._complemento_sas(companias, ranking, opts, faltan, rucs)

        salida = Path(opts["salida"])
        salida.parent.mkdir(parents=True, exist_ok=True)
        with salida.open("w", newline="", encoding="utf-8") as fh:
            escritor = csv.DictWriter(fh, fieldnames=COLUMNAS)
            escritor.writeheader()
            escritor.writerows(filas)

        con_ruc = sum(1 for f in filas if f["ruc"])
        self.stdout.write(self.style.SUCCESS(
            f"Dataset escrito en {salida}: {len(filas)} emprendimientos "
            f"({con_ruc} con RUC y estados financieros SCVS)."
        ))

    # -- lectura de fuentes -------------------------------------------------

    def _leer_companias(self, ruta):
        with open(ruta, encoding="utf-8", newline="") as fh:
            return {
                f["expediente"]: {k: (v or "").strip() for k, v in f.items()}
                for f in csv.DictReader(fh)
            }

    def _leer_ranking(self, ruta, anio):
        """Estados del año de análisis y del anterior (para E3 y E5)."""
        actual, anterior = {}, {}
        with open(ruta, encoding="utf-8", newline="") as fh:
            for f in csv.DictReader(fh):
                if f["anio"] == str(anio):
                    actual[f["expediente"]] = f
                elif f["anio"] == str(anio - 1):
                    anterior[f["expediente"]] = f
        return actual, anterior

    # -- construcción de filas ----------------------------------------------

    def _fila(self, origen, nombre, cia, est, anio, **extra):
        fila = dict.fromkeys(COLUMNAS, "")
        fila.update(origen=origen, nombre=nombre, **extra)
        if cia:
            fila["ruc"] = cia["ruc"]
            fila["provincia"] = fila["provincia"] or cia["provincia"]
        if est:
            ventas = num(est["ingresos_ventas"]) or 0.0
            fila.update(
                anio=anio,
                ciiu=est["ciiu_n6"].strip(),
                empleados=int(num(est["n_empleados"]) or 0),
                ventas=round(ventas, 2),
                costos_variables=round(num(est["costos_ventas_prod"]) or 0.0, 2),
                costos_fijos=round(num(est["gastos_admin_ventas"]) or 0.0, 2),
                utilidad_neta=round(num(est["utilidad_neta"]) or 0.0, 2),
                **indicadores(est, self.anterior.get(cia["expediente"])),
            )
            fila["notas"] = (
                f"Estados financieros {anio} publicados por la SCVS (expediente {cia['expediente']}). "
                "Costos variables = costo de ventas y producción; costos fijos = gastos de "
                "administración y ventas (aproximación para E1). E3 y E5 usan los estados del año anterior. "
                + fila["notas"]
            ).strip()
        return fila

    def _empresas_b(self, ruta_blab, companias, ranking, anio):
        datos = json.loads(Path(ruta_blab).read_text(encoding="utf-8"))
        campos = datos["campos"]
        por_nombre = {}
        for cia in companias.values():
            por_nombre.setdefault(normalizar(cia["nombre"]), []).append(cia)

        filas = []
        for valores in datos["empresas"]:
            b = dict(zip(campos, valores))
            candidatos = por_nombre.get(normalizar(b["nombre"]), [])
            provincia_b = PROVINCIAS_BLAB.get(b["provincia"])
            if provincia_b:
                # Mismo nombre en otra provincia: puede ser otra compañía homónima.
                candidatos = [c for c in candidatos if normalizar(c["provincia"]) == provincia_b]
            candidatos = [c for c in candidatos if c["expediente"] in ranking] or candidatos
            cia = candidatos[0] if len(candidatos) == 1 else None
            est = ranking.get(cia["expediente"]) if cia else None
            sector = SECTOR_POR_BLAB.get(b["sector"], "SERV")
            if est and est["ciiu_n1"].strip() in SECTOR_POR_CIIU:
                sector = SECTOR_POR_CIIU[est["ciiu_n1"].strip()]
            tamano = "sin dato" if b["tamano"] in ("", "0") else f"{b['tamano']} empleados".replace("+", " o más")
            nota = (f"Empresa B certificada desde {b['certificada_desde']}, puntaje de "
                    f"Evaluación de Impacto B {b['puntaje_bia'].replace('.', ',')}, industria "
                    f"«{INDUSTRIAS_BLAB.get(b['industria'], b['industria'])}», sector "
                    f"«{SECTORES_BLAB.get(b['sector'], b['sector'])}», tamaño {tamano}.")
            if not cia:
                nota += " Razón social no identificada sin ambigüedad en la SCVS: sin RUC ni estados."
            filas.append(self._fila(
                "BLAB", b["nombre"], cia, est, anio,
                sector=sector,
                ciudad=(b["ciudad"] or "").title(),
                provincia=PROVINCIAS_BLAB.get(b["provincia"], ""),
                fuente="Directorio de Empresas B (B Lab)" + (" + ranking SCVS" if est else ""),
                fuente_url=URL_BLAB.format(slug=b["slug"]),
                notas=nota,
            ))
        return filas

    def _complemento_sas(self, companias, ranking, opts, faltan, excluir):
        if faltan <= 0:
            return []
        por_seccion = {s: [] for s in SECCIONES_COMPLEMENTO}
        for exp, est in ranking.items():
            cia = companias.get(exp)
            if not cia or cia["ruc"] in excluir:
                continue
            if "SIMPLIFICADA" not in cia["tipo"] or cia["provincia"] != opts["provincia"]:
                continue
            ventas = num(est["ingresos_ventas"]) or 0.0
            empleados = num(est["n_empleados"]) or 0.0
            seccion = est["ciiu_n1"].strip()
            if ventas <= 0 or not 1 <= empleados <= 49 or seccion not in por_seccion:
                continue
            por_seccion[seccion].append((ventas, exp, cia, est))

        cuota = -(-faltan // len(SECCIONES_COMPLEMENTO))
        elegidas = []
        for seccion in SECCIONES_COMPLEMENTO:
            candidatas = sorted(por_seccion[seccion], key=lambda t: (-t[0], t[1]))[:cuota]
            elegidas.extend(candidatas)
        elegidas = elegidas[:faltan]

        return [
            self._fila(
                "SCVS", cia["nombre"], cia, est, opts["anio"],
                sector=SECTOR_POR_CIIU.get(est["ciiu_n1"].strip(), "SERV"),
                ciudad="",
                fuente=f"SCVS ranking empresarial {opts['anio']}",
                fuente_url=URL_RANKING,
                notas="SAS (Ley Orgánica de Emprendimiento e Innovación).",
            )
            for _, _, cia, est in elegidas
        ]
