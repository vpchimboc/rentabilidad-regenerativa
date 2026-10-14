"""Carga datos de demostración: emprendimientos, mediciones, expertos, respuestas
Delphi, referencias bibliográficas y registro PRISMA.

Los emprendimientos son casos ilustrativos construidos para probar el framework;
no corresponden a empresas reales.

Uso:  python manage.py cargar_demo
"""

import datetime
import random

from django.core.management import call_command
from django.core.management.base import BaseCommand

from bibliometria.models import Referencia, RegistroPRISMA
from delphi.models import Experto, Item, Respuesta, Ronda
from emprendimientos.models import Emprendimiento, Medicion, Periodo
from framework.models import Indicador

EMPRENDIMIENTOS = [
    {
        "nombre": "Raíz Andina S.A.S.",
        "sector": "AGRO",
        "ciudad": "Cuenca",
        "empleados": 24,
        "anio_inicio": 2018,
        "descripcion": "Cacao fino de aroma bajo manejo agroforestal, con 142 productores asociados.",
        "periodo": {"anio": 2025, "ventas": 840000, "costos_fijos": 310000, "costos_variables": 420000},
        "mediciones": {
            "E2": 0.085, "E3": 0.16, "E4": 1.8, "E5": 0.09, "E7": 0.38,
            "A2": 0.71, "A3": 1.4, "A5": 0.019, "A6": 2.1, "A7": 0.18, "A8": 0.82, "A10": 12.0,
            "S1": 0.92, "S2": 0.06, "S5": 0.82, "S8": 0.75, "S13": 0.80, "S4": 1.2, "S7": 0.85, "S9": 0.95, "S12": 0.64,
            "O3": 0.71, "O4": 0.93, "O2": 0.62, "O9": 0.5, "O10": 0.8, "O5": 0.02, "O7": 0.6, "O12": 0.7,
        },
    },
    {
        "nombre": "Textiles Sisa Cía. Ltda.",
        "sector": "MANU",
        "ciudad": "Cuenca",
        "empleados": 46,
        "anio_inicio": 2015,
        "descripcion": "Confección con fibras recuperadas y tintura de bajo consumo hídrico.",
        "periodo": {"anio": 2025, "ventas": 1250000, "costos_fijos": 480000, "costos_variables": 690000},
        "mediciones": {
            "E2": 0.112, "E3": 0.195, "E4": 1.4, "E5": 0.05, "E7": 0.22,
            "A2": 0.44, "A3": 1.05, "A5": 0.028, "A6": 3.9, "A7": 0.42, "A8": 0.55, "A10": -3.0,
            "S1": 0.80, "S2": 0.12, "S5": 0.70, "S8": 0.50, "S13": 0.55, "S4": 3.5, "S7": 0.60, "S9": 0.80, "S12": 0.35,
            "O3": 0.79, "O4": 0.88, "O2": 0.55, "O9": 0.4, "O10": 0.7, "O5": 0.05, "O7": 0.4, "O12": 0.6,
        },
    },
    {
        "nombre": "Ecoservicios del Austro",
        "sector": "SERV",
        "ciudad": "Azogues",
        "empleados": 12,
        "anio_inicio": 2021,
        "descripcion": "Gestión de residuos orgánicos y compostaje industrial para restaurantes.",
        "periodo": {"anio": 2025, "ventas": 320000, "costos_fijos": 145000, "costos_variables": 150000},
        "mediciones": {
            "E2": 0.041, "E3": 0.072, "E4": 1.1, "E5": 0.12, "E7": 0.15,
            "A2": 0.82, "A3": 2.3, "A5": 0.015, "A6": 1.4, "A7": 0.09, "A8": 0.9, "A10": 5.0,
            "S1": 0.70, "S2": 0.18, "S5": 0.64, "S8": 0.40, "S13": 0.45, "S4": 4.8, "S7": 0.45, "S9": 0.70, "S12": 0.55,
            "O3": 0.58, "O4": 0.81, "O2": 0.48, "O9": 0.3, "O10": 0.5, "O5": 0.08, "O7": 0.3, "O12": 0.45,
        },
    },
]

EXPERTOS = [
    ("Dra. Mariana Escobar Cárdenas", "PHD", "Universidad Católica de Cuenca", "Ecuador",
     "Ingeniería Industrial, sostenibilidad", 14, 22),
    ("Dr. Julián Restrepo Vélez", "PHD", "Universidad EAFIT", "Colombia",
     "Economía circular y modelos de negocio", 11, 31),
    ("Mgs. Paola Chimbo Ríos", "MSC", "Universidad de Cuenca", "Ecuador",
     "Emprendimiento e innovación", 8, 6),
]

REFERENCIAS = [
    ("Hahn, T., & Tampe, M.", 2021, "Strategies for regenerative business: Analytical framework and agenda for future research",
     "Strategic Organization", "SCO", "10.1177/1476127020979228", "Revisión conceptual",
     "Propone abandonar la lógica de reducción de daños por estrategias regenerativas."),
    ("Bocken, N. M. P., & Ritala, P.", 2022, "Six ways to build a circular and regenerative business",
     "Journal of Business Strategy", "EME", "10.1108/JBS-01-2021-0012", "Estudio de casos múltiples",
     "Identifica seis configuraciones de modelo de negocio circular y regenerativo."),
    ("Veleva, V.", 2023, "From circular to regenerative economy: The role of business as a catalyst for change",
     "Business Strategy and the Environment", "WIL", "10.1002/bse.3265", "Revisión sistemática",
     "Introduce el Retorno de Inversión Regenerativa como métrica superadora del ROI."),
    ("Konietzko, J., Das, A., & Bocken, N. M. P.", 2023, "Circular ecosystems: Reviewing the state of the art and a roadmap for future research",
     "Journal of Cleaner Production", "SCD", "10.1016/j.jclepro.2022.135156", "Revisión sistemática",
     "Los ecosistemas de innovación circular reducen el riesgo operativo del emprendimiento."),
    ("Inigo, E. A., & Albareda, L.", 2022, "Understanding regenerative business models: A systemic review of the literature",
     "Corporate Social Responsibility and Environmental Management", "WIL", "10.1002/csr.2257",
     "Revisión sistémica", "Sistematiza los modelos de negocio regenerativos de base territorial."),
    ("Nishant, R., Kennedy, M., & Corbett, J.", 2022, "Artificial intelligence for sustainability: Challenges, opportunities, and a research agenda",
     "International Journal of Information Management", "SCD", "10.1016/j.ijinfomgt.2021.102439",
     "Agenda de investigación", "La trazabilidad digital hace auditable el impacto positivo."),
    ("Garcés-Ayerbe, C., et al.", 2021, "Is it possible to change from a linear to a circular economy?",
     "Business Strategy and the Environment", "WOS", "10.1002/bse.2610", "Encuesta a PYMES europeas",
     "Documenta barreras y facilitadores de la transición circular en PYMES."),
    ("Schoenmaker, D., & Schramade, W.", 2023, "Corporate finance for long-term value",
     "Springer", "SPR", "", "Marco teórico",
     "Propone indicadores integrados que capturan el valor total en tres dimensiones."),
    ("Whiteman, G., & Cooper, W. H.", 2023, "Ecological sensemaking and regenerative business models",
     "Academy of Management Review", "WOS", "10.5465/amr.2019.0441", "Teoría",
     "El capital social regenerativo como componente sistémico de la sostenibilidad."),
    ("López-Díaz, A., Viteri, J., & Rivera, J.", 2024, "Emprendimiento y resiliencia en economías dolarizadas: El caso de Ecuador",
     "Revista Latinoamericana de Estrategia", "SCI", "", "Estudio de caso",
     "Falta de metodologías de validación adaptadas a microestructuras ecuatorianas."),
]

PRISMA = [
    (1, 412, "Scopus, WoS, ScienceDirect, SpringerLink (2022–2026)"),
    (2, 87, "Duplicados eliminados"),
    (3, 325, "Títulos y resúmenes revisados"),
    (4, 241, "Excluidos por no abordar triple impacto o rentabilidad"),
    (5, 84, "Textos completos evaluados"),
    (6, 52, "Excluidos: sin propuesta metodológica evaluable"),
    (7, 32, "Estudios incluidos en la síntesis"),
]


class Command(BaseCommand):
    help = "Carga datos de demostración para probar todos los módulos."

    def handle(self, *args, **opciones):
        if not Indicador.objects.exists():
            self.stdout.write("Framework vacío; ejecutando cargar_framework...")
            call_command("cargar_framework")

        indicadores = {i.codigo: i for i in Indicador.objects.all()}

        for data in EMPRENDIMIENTOS:
            mediciones = data["mediciones"]
            periodo_data = data["periodo"]
            campos = {k: v for k, v in data.items() if k not in ("mediciones", "periodo")}
            emp, _ = Emprendimiento.objects.update_or_create(
                nombre=campos["nombre"], defaults=campos
            )
            periodo, _ = Periodo.objects.update_or_create(
                emprendimiento=emp, anio=periodo_data["anio"], defaults=periodo_data
            )
            for codigo, valor in mediciones.items():
                if codigo in indicadores:
                    Medicion.objects.update_or_create(
                        periodo=periodo,
                        indicador=indicadores[codigo],
                        defaults={"valor": valor, "fuente": "Levantamiento de campo (caso demostrativo)"},
                    )

        for nombre, grado, institucion, pais, area, anios, pubs in EXPERTOS:
            Experto.objects.update_or_create(
                nombre=nombre,
                defaults={
                    "grado": grado, "institucion": institucion, "pais": pais,
                    "area": area, "anios_experiencia": anios, "publicaciones": pubs,
                },
            )

        expertos = list(Experto.objects.all())

        # Ronda 1: acuerdo parcial. Los ítems de factibilidad de medición y de
        # aplicabilidad reciben puntajes más bajos, como es habitual en la primera
        # consulta, y no alcanzan el IVC mínimo.
        ronda1, _ = Ronda.objects.update_or_create(
            numero=1,
            defaults={
                "fecha": datetime.date(2026, 7, 15),
                "estado": "CER",
                "observaciones": "Se reformularon los ítems I09 e I10 y se simplificó la "
                                 "batería de indicadores de la dimensión ambiental.",
            },
        )
        rng = random.Random(11)
        for item in Item.objects.all():
            base = 3 if item.codigo in ("I09", "I10") else 4
            for experto in expertos:
                valor = min(5, max(1, base + rng.choice([-1, 0, 0, 1])))
                Respuesta.objects.update_or_create(
                    ronda=ronda1, experto=experto, item=item, defaults={"valor": valor}
                )

        # Ronda 2: tras incorporar los ajustes, se alcanza consenso.
        ronda2, _ = Ronda.objects.update_or_create(
            numero=2,
            defaults={
                "fecha": datetime.date(2026, 8, 12),
                "estado": "CER",
                "observaciones": "Consenso alcanzado. El framework pasa a versión definitiva.",
            },
        )
        rng2 = random.Random(29)
        for item in Item.objects.all():
            base = 4 if item.codigo in ("I09", "I10") else 5
            for experto in expertos:
                valor = min(5, max(4, base + rng2.choice([-1, 0, 0])))
                Respuesta.objects.update_or_create(
                    ronda=ronda2, experto=experto, item=item, defaults={"valor": valor}
                )

        for autores, anio, titulo, revista, base, doi, metodologia, hallazgos in REFERENCIAS:
            Referencia.objects.update_or_create(
                autores=autores, anio=anio, titulo=titulo,
                defaults={
                    "revista": revista, "base": base, "doi": doi,
                    "metodologia": metodologia, "hallazgos": hallazgos, "incluida": True,
                },
            )

        for fase, cantidad, detalle in PRISMA:
            RegistroPRISMA.objects.update_or_create(
                fase=fase, defaults={"cantidad": cantidad, "detalle": detalle}
            )

        self.stdout.write(self.style.SUCCESS(
            f"Demo cargada: {Emprendimiento.objects.count()} emprendimientos, "
            f"{Medicion.objects.count()} mediciones, {Experto.objects.count()} expertos, "
            f"{Respuesta.objects.count()} respuestas Delphi, "
            f"{Referencia.objects.count()} referencias."
        ))
