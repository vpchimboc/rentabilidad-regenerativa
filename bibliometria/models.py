"""Matriz bibliográfica y registro PRISMA (objetivo específico 1)."""

from django.db import models


class Referencia(models.Model):
    """Fila de la matriz bibliométrica."""

    BASES = [
        ("SCO", "Scopus"),
        ("WOS", "Web of Science"),
        ("SCD", "ScienceDirect"),
        ("SPR", "SpringerLink"),
        ("EME", "Emerald"),
        ("WIL", "Wiley"),
        ("SCI", "SciELO"),
        ("GSC", "Google Scholar"),
    ]

    autores = models.CharField(max_length=300)
    anio = models.PositiveIntegerField("Año")
    titulo = models.CharField(max_length=400)
    revista = models.CharField(max_length=240, blank=True)
    base = models.CharField(max_length=3, choices=BASES, default="SCO")
    doi = models.CharField("DOI", max_length=160, blank=True)
    palabras_clave = models.CharField(max_length=300, blank=True)
    metodologia = models.CharField(max_length=200, blank=True)
    variables = models.CharField(max_length=300, blank=True)
    hallazgos = models.TextField(blank=True)
    incluida = models.BooleanField("Incluida en la síntesis", default=True)
    motivo_exclusion = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-anio", "autores"]
        verbose_name = "referencia"
        verbose_name_plural = "matriz bibliográfica"

    def __str__(self):
        return f"{self.autores} ({self.anio})"


class RegistroPRISMA(models.Model):
    """Conteos del flujo PRISMA de selección de estudios."""

    FASES = [
        (1, "Identificación — registros encontrados"),
        (2, "Identificación — duplicados eliminados"),
        (3, "Cribado — títulos y resúmenes revisados"),
        (4, "Cribado — registros excluidos"),
        (5, "Elegibilidad — textos completos evaluados"),
        (6, "Elegibilidad — textos completos excluidos"),
        (7, "Inclusión — estudios incluidos en la síntesis"),
    ]

    fase = models.PositiveSmallIntegerField(choices=FASES, unique=True)
    cantidad = models.PositiveIntegerField(default=0)
    detalle = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["fase"]
        verbose_name = "registro PRISMA"
        verbose_name_plural = "registro PRISMA"

    def __str__(self):
        return f"{self.get_fase_display()}: {self.cantidad}"
