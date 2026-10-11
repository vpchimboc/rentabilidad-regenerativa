"""Validación por método Delphi modificado (objetivo específico 5)."""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Experto(models.Model):
    GRADOS = [("PHD", "Doctorado"), ("MSC", "Maestría")]

    nombre = models.CharField(max_length=160)
    institucion = models.CharField(max_length=160, blank=True)
    pais = models.CharField(max_length=80, default="Ecuador")
    grado = models.CharField(max_length=3, choices=GRADOS, default="PHD")
    area = models.CharField(
        max_length=160, blank=True, help_text="Ingeniería Industrial, sostenibilidad, emprendimiento"
    )
    anios_experiencia = models.PositiveSmallIntegerField(default=5)
    publicaciones = models.PositiveSmallIntegerField(default=0)
    correo = models.EmailField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.get_grado_display()})"

    @property
    def cumple_criterios(self):
        """Criterios de selección declarados en el protocolo."""
        return self.anios_experiencia >= 5 and self.grado in ("PHD", "MSC")


class Ronda(models.Model):
    ABIERTA = "ABI"
    CERRADA = "CER"
    ESTADOS = [(ABIERTA, "Abierta"), (CERRADA, "Cerrada")]

    numero = models.PositiveSmallIntegerField(unique=True)
    fecha = models.DateField()
    estado = models.CharField(max_length=3, choices=ESTADOS, default=ABIERTA)
    observaciones = models.TextField(blank=True, help_text="Ajustes incorporados tras la ronda")

    class Meta:
        ordering = ["numero"]

    def __str__(self):
        return f"Ronda {self.numero}"


class Item(models.Model):
    """Ítem del cuestionario Delphi, en escala Likert de cinco niveles."""

    CRITERIOS = [
        ("CLA", "Claridad"),
        ("PER", "Pertinencia"),
        ("COH", "Coherencia"),
        ("APL", "Aplicabilidad"),
        ("FAC", "Factibilidad"),
    ]

    codigo = models.CharField(max_length=10, unique=True)
    componente = models.CharField(
        max_length=160, help_text="Componente del framework que se evalúa"
    )
    criterio = models.CharField(max_length=3, choices=CRITERIOS)
    enunciado = models.TextField()
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["orden", "codigo"]
        verbose_name = "ítem del cuestionario"
        verbose_name_plural = "ítems del cuestionario"

    def __str__(self):
        return f"{self.codigo} · {self.get_criterio_display()}"


class Respuesta(models.Model):
    ronda = models.ForeignKey(Ronda, on_delete=models.CASCADE, related_name="respuestas")
    experto = models.ForeignKey(Experto, on_delete=models.CASCADE, related_name="respuestas")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="respuestas")
    valor = models.PositiveSmallIntegerField(
        "Valoración Likert (1–5)", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comentario = models.TextField(blank=True)

    class Meta:
        unique_together = [("ronda", "experto", "item")]
        ordering = ["ronda", "item", "experto"]

    def __str__(self):
        return f"R{self.ronda.numero} · {self.experto.nombre} · {self.item.codigo} = {self.valor}"


class ResultadoRonda(models.Model):
    """Consolidado estadístico de una ronda: IVC por ítem, S-CVI y W de Kendall."""

    ronda = models.OneToOneField(Ronda, on_delete=models.CASCADE, related_name="resultado")
    s_cvi = models.FloatField("S-CVI/Ave (validez de contenido global)", default=0)
    kendall_w = models.FloatField("W de Kendall", default=0)
    chi_cuadrado = models.FloatField(default=0)
    gl = models.PositiveSmallIntegerField("Grados de libertad", default=0)
    consenso = models.BooleanField(default=False)
    detalle = models.JSONField(default=dict, blank=True)
    calculado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Resultado {self.ronda} · W={self.kendall_w:.3f}"
