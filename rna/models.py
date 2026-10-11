"""Persistencia del modelo de Red Neuronal Artificial (objetivo específico 3)."""

from django.db import models


class ModeloRNA(models.Model):
    nombre = models.CharField(max_length=120, default="MLP Rentabilidad Regenerativa")
    n_entradas = models.PositiveSmallIntegerField(default=0)
    n_ocultas = models.PositiveSmallIntegerField(default=8)
    epocas = models.PositiveIntegerField(default=300)
    tasa_aprendizaje = models.FloatField(default=0.05)
    n_muestras = models.PositiveIntegerField(default=0)
    codigos_entrada = models.JSONField(default=list)
    pesos = models.JSONField(default=dict)
    metricas = models.JSONField(default=dict)
    historial = models.JSONField(default=list)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]
        verbose_name = "modelo RNA"
        verbose_name_plural = "modelos RNA"

    def __str__(self):
        return f"{self.nombre} ({self.n_entradas}-{self.n_ocultas}-1) · R² {self.metricas.get('r2', '—')}"
