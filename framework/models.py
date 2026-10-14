"""Catálogo del Framework de Rentabilidad Regenerativa (FRR), versión 1.0.

Implementa la especificación «Fase 2. Diseño conceptual y operacional del FRR»
(versión científica 2.0, 14-oct-2026):

* Cuatro dimensiones con códigos semánticos estables: D1 económica, D2 ambiental,
  D3 social, D4 operacional (§2.3).
* Catálogo de 42 KPI candidatos E1–E7, A1–A10, S1–S13, O1–O12 (§2.6–2.9) con
  fórmula, componentes, rol y estado.
* Normalización a z ∈ [0, 1] con referencias L/U (beneficio y costo) o T/H
  (objetivo) (§2.5). Sin referencias justificadas el indicador no se puntúa.
* Parámetros de agregación versionados (ε, cobertura mínima) (§2.10.2).
"""

from django.core.validators import MinValueValidator
from django.db import models


class Dimension(models.Model):
    """D1 económica · D2 ambiental · D3 social · D4 operacional."""

    codigo = models.CharField(max_length=4, unique=True, help_text="D1, D2, D3, D4 (identificador semántico estable)")
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    funcion = models.CharField("Función en el FRR", max_length=200, blank=True)
    peso = models.FloatField(
        "Peso α", default=0.25,
        help_text="Peso dimensional α(d) en la agregación geométrica. Se normalizan para sumar 1. "
                  "Provisional hasta la validación de expertos.",
    )
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["orden", "codigo"]
        verbose_name = "dimensión"
        verbose_name_plural = "dimensiones"

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class Variable(models.Model):
    """Agrupación temática de indicadores dentro de una dimensión."""

    dimension = models.ForeignKey(Dimension, on_delete=models.CASCADE, related_name="variables")
    codigo = models.CharField(max_length=12, unique=True)
    nombre = models.CharField(max_length=140)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ["dimension__orden", "codigo"]

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class Indicador(models.Model):
    """KPI candidato del FRR con su ficha (§2.10, §2.12.3)."""

    BENEFICIO, COSTO, OBJETIVO = "BEN", "COS", "OBJ"
    TIPOS = [
        (BENEFICIO, "Beneficio (mayor es mejor)"),
        (COSTO, "Costo (menor es mejor)"),
        (OBJETIVO, "Objetivo (cercanía a un valor ideal)"),
    ]
    ROLES = [("NUC", "Núcleo"), ("SAL", "Salvaguarda"), ("COM", "Complementario"), ("HAB", "Habilitador"),
             ("PEN", "Por definir")]
    CANDIDATO, ACTIVO, EXCLUIDO = "CAND", "ACT", "EXCL"
    ESTADOS = [
        (CANDIDATO, "Candidato (pendiente de validación)"),
        (ACTIVO, "Activo en la versión operativa"),
        (EXCLUIDO, "Excluido (decisión documentada)"),
    ]

    variable = models.ForeignKey(Variable, on_delete=models.CASCADE, related_name="indicadores")
    codigo = models.CharField(max_length=16, unique=True, help_text="ID semántico estable: E1…E7, A1…A10, S1…S13, O1…O12")
    nombre = models.CharField(max_length=160)
    formula = models.CharField(max_length=240, blank=True)
    componentes = models.TextField("Componentes y cómo obtenerlos", blank=True)
    unidad = models.CharField(max_length=40, blank=True)
    rol = models.CharField(max_length=3, choices=ROLES, default="PEN")
    estado = models.CharField(max_length=4, choices=ESTADOS, default=CANDIDATO)
    tipo = models.CharField("Tipo de normalización", max_length=3, choices=TIPOS, default=BENEFICIO)
    peso = models.FloatField(
        "Peso w(d,j)", default=1.0, validators=[MinValueValidator(0.0)],
        help_text="Peso no negativo dentro de la dimensión (candidato, no validado)",
    )
    ref_l = models.FloatField("L (referencia inferior)", null=True, blank=True)
    ref_u = models.FloatField("U (referencia superior)", null=True, blank=True)
    ref_t = models.FloatField("T (objetivo)", null=True, blank=True)
    ref_h = models.FloatField("H (tolerancia)", null=True, blank=True)
    fuente_referencia = models.CharField(
        "Sustento de las referencias", max_length=240, blank=True,
        help_text="Sin sustento documentado el indicador no se puntúa (§2.5).",
    )
    referencia_provisional = models.BooleanField(default=True)
    equivalencia_v0 = models.CharField(
        "Correspondencia con la plataforma preliminar", max_length=240, blank=True,
        help_text="Matriz de correspondencia 17 → 42 (DIREC 1, prioridad 1)",
    )
    version_ficha = models.CharField(max_length=10, default="1.0")
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["variable__dimension__orden", "orden", "codigo"]
        verbose_name = "indicador (KPI)"
        verbose_name_plural = "indicadores (KPIs)"

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"

    @property
    def dimension(self):
        return self.variable.dimension

    @property
    def puntuable(self):
        """True si existen referencias válidas para normalizar (§2.5)."""
        if self.tipo == self.OBJETIVO:
            return self.ref_t is not None and self.ref_h is not None and self.ref_h > 0
        return self.ref_l is not None and self.ref_u is not None and self.ref_u > self.ref_l

    def normalizar(self, x):
        """Puntuación z ∈ [0, 1]; None si no hay referencias válidas o valor."""
        if x is None or not self.puntuable:
            return None
        if self.tipo == self.BENEFICIO:
            z = (x - self.ref_l) / (self.ref_u - self.ref_l)
        elif self.tipo == self.COSTO:
            z = (self.ref_u - x) / (self.ref_u - self.ref_l)
        else:
            z = 1 - abs(x - self.ref_t) / self.ref_h
        return min(1.0, max(0.0, z))


class ParametrosFRR(models.Model):
    """Parámetros de agregación versionados. Solo una versión está activa."""

    version = models.CharField(max_length=12, unique=True, default="1.0")
    epsilon = models.FloatField(
        "ε (estabilidad numérica)", default=0.01,
        help_text="Constante pequeña 0 < ε < 1 del IRR suavizado (§2.5). Requiere análisis de sensibilidad.",
    )
    cobertura_minima = models.FloatField(
        "Cobertura mínima C", default=0.6,
        help_text="Proporción ponderada mínima de información observada por dimensión. Provisional.",
    )
    activo = models.BooleanField(default=True)
    notas = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]
        verbose_name = "parámetros del FRR"
        verbose_name_plural = "parámetros del FRR"

    def __str__(self):
        return f"FRR {self.version} · ε={self.epsilon} · Cmin={self.cobertura_minima}"

    @classmethod
    def vigentes(cls):
        obj = cls.objects.filter(activo=True).first()
        return obj or cls.objects.create(version="1.0")
