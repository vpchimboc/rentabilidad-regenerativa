"""Validación por método Delphi modificado (objetivo específico 5)."""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Experto(models.Model):
    GRADOS = [("PHD", "Doctorado"), ("MSC", "Maestría")]

    nombre = models.CharField(max_length=160)
    institucion = models.CharField(max_length=160, blank=True)
    pais = models.CharField(max_length=80, default="Ecuador")
    grado = models.CharField(max_length=3, choices=GRADOS, blank=True, default="",
                             help_text="Dejar vacío si aún no se ha registrado")
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
        """Criterios del protocolo: maestría o doctorado, 5 años de experiencia y publicaciones científicas."""
        return self.anios_experiencia >= 5 and self.grado in ("PHD", "MSC") and self.publicaciones >= 1


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
        ("MED", "Medibilidad"),
        ("RIG", "Rigor técnico"),
    ]

    codigo = models.CharField(max_length=10, unique=True)
    componente = models.CharField(
        max_length=160, help_text="Componente del framework que se evalúa"
    )
    criterio = models.CharField(max_length=3, choices=CRITERIOS)
    enunciado = models.TextField()
    orden = models.PositiveSmallIntegerField(default=0)
    origen = models.TextField(blank=True, help_text="Origen específico de la pregunta y por qué se formula")
    activo = models.BooleanField(default=True, help_text="Solo los ítems activos aparecen en el cuestionario")

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


class Dictamen(models.Model):
    """Preguntas abiertas del cuestionario (P13 y P14): una por experto y ronda."""

    SI, AJUSTES, NO = "SI", "AJU", "NO"
    RECOMENDACIONES = [(SI, "Sí"), (AJUSTES, "Sí, con ajustes"), (NO, "No")]

    ronda = models.ForeignKey(Ronda, on_delete=models.CASCADE, related_name="dictamenes")
    experto = models.ForeignKey(Experto, on_delete=models.CASCADE, related_name="dictamenes")
    cambio_prioritario = models.TextField(
        "P13. Cambio prioritario", blank=True,
        help_text="¿Qué cambio considera prioritario en el Framework o en algún KPI? Código y justificación")
    recomendacion = models.CharField(
        "P14. ¿Recomienda mantener el FRR para evaluación exploratoria?", max_length=3,
        choices=RECOMENDACIONES, blank=True)

    class Meta:
        unique_together = [("ronda", "experto")]
        verbose_name = "dictamen del experto (P13–P14)"
        verbose_name_plural = "dictámenes de los expertos (P13–P14)"

    def __str__(self):
        return f"R{self.ronda.numero} · {self.experto.nombre} · {self.get_recomendacion_display() or 'sin respuesta'}"


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


class CambioItem(models.Model):
    """Trazabilidad de ajustes entre rondas (Tabla S4 del informe Delphi)."""

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="cambios")
    ronda = models.ForeignKey(Ronda, on_delete=models.CASCADE, related_name="cambios",
                              help_text="Ronda en la que se detectó el hallazgo")
    hallazgo = models.TextField("Hallazgo de la ronda", help_text="Comentario resumido y anónimo de los expertos")
    cambio = models.TextField("Cambio aplicado", blank=True, help_text="Redacción original → nueva")
    justificacion = models.TextField("Justificación", blank=True)
    reevaluado = models.BooleanField("Reevaluado en la ronda siguiente", default=False)

    class Meta:
        ordering = ["ronda__numero", "item__orden"]
        verbose_name = "cambio entre rondas"
        verbose_name_plural = "cambios entre rondas"

    def __str__(self):
        return f"R{self.ronda.numero} · {self.item.codigo}"
