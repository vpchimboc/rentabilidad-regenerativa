"""Estructura del Framework: dimensiones, variables, indicadores y KPIs.

Corresponde al objetivo específico 2 del protocolo: "Definir los componentes,
dimensiones, variables e indicadores que conformarán el Framework de
Rentabilidad Regenerativa".
"""

from django.core.validators import MinValueValidator
from django.db import models


class Dimension(models.Model):
    """Las cuatro dimensiones del framework: económica, operativa, social y ambiental."""

    codigo = models.CharField(max_length=4, unique=True, help_text="D1, D2, D3, D4")
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    peso = models.FloatField(
        default=0.25,
        help_text="Peso w_i en la agregación geométrica. Los pesos se normalizan para sumar 1.",
    )
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["orden", "codigo"]
        verbose_name = "dimensión"
        verbose_name_plural = "dimensiones"

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class Variable(models.Model):
    """Variable de una dimensión. Agrupa indicadores afines."""

    dimension = models.ForeignKey(Dimension, on_delete=models.CASCADE, related_name="variables")
    codigo = models.CharField(max_length=12, unique=True)
    nombre = models.CharField(max_length=140)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ["dimension__orden", "codigo"]

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class Indicador(models.Model):
    """Indicador / KPI medible.

    Los cortes c1..c4 traducen el valor medido a la escala de niveles 0–4
    (degenerativo, mitigado, neutro, restaurativo, regenerativo).
    """

    MAYOR_MEJOR = "MAY"
    MENOR_MEJOR = "MEN"
    DIRECCIONES = [
        (MAYOR_MEJOR, "Mayor es mejor"),
        (MENOR_MEJOR, "Menor es mejor"),
    ]

    variable = models.ForeignKey(Variable, on_delete=models.CASCADE, related_name="indicadores")
    codigo = models.CharField(max_length=16, unique=True)
    nombre = models.CharField(max_length=160)
    unidad = models.CharField(max_length=40, blank=True)
    formula = models.CharField(max_length=240, blank=True, help_text="Fórmula del KPI")
    direccion = models.CharField(max_length=3, choices=DIRECCIONES, default=MAYOR_MEJOR)
    peso = models.FloatField(default=1.0, validators=[MinValueValidator(0.0)],
                             help_text="Peso relativo dentro de su dimensión")
    c1 = models.FloatField(help_text="Corte nivel 0→1")
    c2 = models.FloatField(help_text="Corte nivel 1→2 (neutro / balance cero)")
    c3 = models.FloatField(help_text="Corte nivel 2→3 (restaurativo)")
    c4 = models.FloatField(help_text="Corte nivel 3→4 (regenerativo)")
    es_entrada_rna = models.BooleanField(
        default=True, help_text="Se usa como entrada del modelo de Red Neuronal Artificial"
    )
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
    def cortes(self):
        return [self.c1, self.c2, self.c3, self.c4]

    def nivel_continuo(self, valor):
        """Traduce un valor medido a la escala 0–4 con interpolación lineal.

        La interpolación conserva resolución para el análisis de sensibilidad;
        el nivel discreto (piso del continuo) es el que se usa para el veredicto.
        """
        cortes = self.cortes
        if self.direccion == self.MENOR_MEJOR:
            # Cortes descendentes: se evalúa sobre la escala invertida.
            valor = -valor
            cortes = [-c for c in cortes]

        if valor >= cortes[3]:
            return 4.0
        if valor < cortes[0]:
            # Zona degenerativa: se degrada linealmente hacia 0 usando el
            # ancho del primer tramo como referencia de escala.
            span = (cortes[1] - cortes[0]) or 1.0
            return max(0.0, 1.0 + (valor - cortes[0]) / span)
        for i in range(3):
            if cortes[i] <= valor < cortes[i + 1]:
                span = (cortes[i + 1] - cortes[i]) or 1.0
                return (i + 1) + (valor - cortes[i]) / span
        return 4.0

    def nivel(self, valor):
        """Nivel discreto 0–4."""
        return int(min(4, max(0, int(self.nivel_continuo(valor)))))


NIVELES = {
    0: "Degenerativo",
    1: "Mitigado",
    2: "Neutro / sostenible",
    3: "Restaurativo",
    4: "Regenerativo",
}
