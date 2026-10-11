"""Emprendimientos evaluados, sus períodos y mediciones."""

from django.db import models

from framework.models import Indicador


class Emprendimiento(models.Model):
    SECTORES = [
        ("AGRO", "Agroindustrial"),
        ("MANU", "Manufacturero"),
        ("SERV", "Servicios"),
        ("COME", "Comercial"),
        ("TECN", "Tecnológico"),
    ]

    nombre = models.CharField(max_length=160)
    ruc = models.CharField("RUC", max_length=13, blank=True)
    sector = models.CharField(max_length=4, choices=SECTORES, default="AGRO")
    ciudad = models.CharField(max_length=80, default="Cuenca")
    provincia = models.CharField(max_length=60, blank=True)
    ciiu = models.CharField("Actividad CIIU", max_length=12, blank=True)
    fuente = models.CharField(
        "Fuente pública", max_length=200, blank=True,
        help_text="Registro público del que proceden los datos de identificación",
    )
    fuente_url = models.URLField("URL de verificación", max_length=300, blank=True)
    anio_inicio = models.PositiveIntegerField("Año de inicio de operaciones", null=True, blank=True)
    empleados = models.PositiveIntegerField(default=0)
    descripcion = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @property
    def ultima_evaluacion(self):
        return (
            Evaluacion.objects.filter(periodo__emprendimiento=self)
            .order_by("-periodo__anio", "-creado")
            .first()
        )


class Periodo(models.Model):
    """Período de evaluación (normalmente un ejercicio anual)."""

    emprendimiento = models.ForeignKey(
        Emprendimiento, on_delete=models.CASCADE, related_name="periodos"
    )
    anio = models.PositiveIntegerField()
    etiqueta = models.CharField(max_length=60, blank=True)
    ventas = models.DecimalField("Ventas del período (USD)", max_digits=14, decimal_places=2, default=0)
    costos_fijos = models.DecimalField("Costos fijos (USD)", max_digits=14, decimal_places=2, default=0)
    costos_variables = models.DecimalField("Costos variables (USD)", max_digits=14, decimal_places=2, default=0)
    notas = models.TextField(blank=True)

    class Meta:
        ordering = ["-anio"]
        unique_together = [("emprendimiento", "anio")]
        verbose_name = "período"
        verbose_name_plural = "períodos"

    def __str__(self):
        return f"{self.emprendimiento} · {self.anio}"

    @property
    def punto_equilibrio(self):
        """Break-even en USD. Es el umbral que el framework busca superar."""
        ventas = float(self.ventas)
        cv = float(self.costos_variables)
        if ventas <= 0:
            return 0.0
        margen_contribucion = 1 - (cv / ventas)
        if margen_contribucion <= 0:
            return 0.0
        return float(self.costos_fijos) / margen_contribucion

    @property
    def margen_sobre_break_even(self):
        """Cuánto supera las ventas al punto de equilibrio, en veces."""
        pe = self.punto_equilibrio
        if pe <= 0:
            return 0.0
        return float(self.ventas) / pe

    def mediciones_dict(self):
        return {m.indicador.codigo: m.valor for m in self.mediciones.select_related("indicador")}


class Medicion(models.Model):
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name="mediciones")
    indicador = models.ForeignKey(Indicador, on_delete=models.CASCADE, related_name="mediciones")
    valor = models.FloatField()
    fuente = models.CharField(max_length=160, blank=True, help_text="Origen del dato / evidencia")

    class Meta:
        unique_together = [("periodo", "indicador")]
        ordering = ["indicador__variable__dimension__orden", "indicador__orden"]
        verbose_name = "medición"
        verbose_name_plural = "mediciones"

    def __str__(self):
        return f"{self.indicador.codigo} = {self.valor}"

    @property
    def nivel(self):
        return self.indicador.nivel(self.valor)


class Evaluacion(models.Model):
    """Resultado del cálculo del IRR para un período."""

    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name="evaluaciones")
    irr = models.FloatField("Índice de Rentabilidad Regenerativa")
    media_aritmetica = models.FloatField(default=0)
    minimo_dimensional = models.PositiveSmallIntegerField(default=0)
    veredicto = models.CharField(max_length=80)
    cuello_de_botella = models.CharField(max_length=8, blank=True)
    detalle = models.JSONField(default=dict, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]
        verbose_name = "evaluación"
        verbose_name_plural = "evaluaciones"

    def __str__(self):
        return f"{self.periodo} · IRR {self.irr:.3f}"
