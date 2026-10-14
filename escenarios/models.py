"""Simulación de escenarios optimista, esperado y pesimista (objetivo específico 4)."""

from django.db import models

from emprendimientos.models import Periodo


class Escenario(models.Model):
    OPTIMISTA = "OPT"
    ESPERADO = "ESP"
    PESIMISTA = "PES"
    TIPOS = [
        (OPTIMISTA, "Optimista"),
        (ESPERADO, "Esperado"),
        (PESIMISTA, "Pesimista"),
    ]

    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name="escenarios")
    tipo = models.CharField(max_length=3, choices=TIPOS)
    factor = models.FloatField(
        help_text="Factor multiplicativo aplicado a los indicadores (1.00 = sin cambio)"
    )
    irr = models.FloatField("IRR resultante", null=True, blank=True)
    clasificacion = models.CharField(max_length=1, blank=True)
    veredicto = models.CharField(max_length=120, blank=True)
    version = models.CharField(max_length=12, blank=True)
    detalle = models.JSONField(default=dict, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["periodo", "tipo"]
        verbose_name = "escenario"
        verbose_name_plural = "escenarios"

    def __str__(self):
        irr = "no calculable" if self.irr is None else f"{self.irr:.3f}"
        return f"{self.periodo} · {self.get_tipo_display()} · IRR {irr}"
