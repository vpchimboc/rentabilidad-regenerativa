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

    @property
    def margen_seguridad(self):
        """E1 = (V − PE) / V. None si no es calculable (no se registra como cero)."""
        ventas, pe = float(self.ventas), self.punto_equilibrio
        if ventas <= 0 or pe <= 0:
            return None
        return (ventas - pe) / ventas

    def mediciones_dict(self):
        """Valores observados {código: valor}; ND/NA/NV no aparecen (nunca como cero)."""
        return {
            m.indicador.codigo: m.valor
            for m in self.mediciones.select_related("indicador")
            if m.estado == Medicion.OBS and m.valor is not None
        }

    def simulados(self):
        """Códigos de KPI cuyo valor es simulado en este período."""
        return set(self.mediciones.filter(simulado=True).values_list("indicador__codigo", flat=True))

    def no_aplicables(self):
        """Códigos declarados NA (se excluyen del denominador de cobertura)."""
        return set(self.mediciones.filter(estado=Medicion.NA).values_list("indicador__codigo", flat=True))

    def salvaguardas_manuales(self):
        return {v.codigo: int(v.estado) for v in self.salvaguardas.all()}


class Medicion(models.Model):
    """Medición de un KPI con su procedencia (§2.12.5).

    Estados: OBS observado · ND no disponible · NA no aplicable (con justificación)
    · NV no verificable. Solo OBS entra al cálculo; los demás nunca se convierten en cero.
    """

    OBS, ND, NA, NV = "OBS", "ND", "NA", "NV"
    ESTADOS = [
        (OBS, "Observado"),
        (ND, "No disponible"),
        (NA, "No aplicable"),
        (NV, "No verificable"),
    ]

    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name="mediciones")
    indicador = models.ForeignKey(Indicador, on_delete=models.CASCADE, related_name="mediciones")
    estado = models.CharField(max_length=3, choices=ESTADOS, default=OBS)
    valor = models.FloatField("Resultado bruto", null=True, blank=True,
                              help_text="Si se informan numerador y denominador se calcula solo")
    numerador = models.FloatField(null=True, blank=True)
    denominador = models.FloatField(null=True, blank=True)
    unidad = models.CharField(max_length=40, blank=True)
    fuente = models.CharField(max_length=160, blank=True, help_text="Fuente y archivo de soporte")
    fecha_medicion = models.DateField(null=True, blank=True)
    responsable = models.CharField(max_length=120, blank=True)
    observaciones = models.CharField(max_length=300, blank=True,
                                     help_text="Justificación de NA/ND/NV o notas de auditoría")
    version_ficha = models.CharField(max_length=10, default="1.0")
    simulado = models.BooleanField(
        default=False, help_text="Valor generado por simulación (no es un dato verificado de la empresa)")

    class Meta:
        unique_together = [("periodo", "indicador")]
        ordering = ["indicador__variable__dimension__orden", "indicador__orden"]
        verbose_name = "medición"
        verbose_name_plural = "mediciones"

    def __str__(self):
        return f"{self.indicador.codigo} = {self.valor_efectivo if self.estado == self.OBS else self.estado}"

    def save(self, *args, **kwargs):
        # Cociente con denominador inválido: no disponible, jamás cero (§2.12.1).
        if self.numerador is not None and self.denominador is not None:
            if self.denominador > 0:
                self.valor = self.numerador / self.denominador
            else:
                self.valor, self.estado = None, self.ND
                self.observaciones = self.observaciones or "Denominador cero o inválido"
        # Anclas matemáticas 0–1 (MAT) solo valen para fracciones parte/total coherentes (Anexo técnico §3).
        if (self.estado == self.OBS and self.valor is not None
                and self.indicador.tipo_fuente_referencia == "MAT" and not 0 <= self.valor <= 1):
            self.valor, self.estado = None, self.ND
            self.observaciones = self.observaciones or "Proporción fuera de [0, 1]: numerador mayor que el denominador"
        if self.estado == self.OBS and self.valor is None:
            self.estado = self.ND
        if not self.unidad:
            self.unidad = self.indicador.unidad
        super().save(*args, **kwargs)

    @property
    def valor_efectivo(self):
        return self.valor if self.estado == self.OBS else None

    @property
    def z(self):
        return self.indicador.normalizar(self.valor_efectivo)


class FichaEcologica(models.Model):
    """Ficha operacional del indicador A10 «Resultado ecológico neto» (corrección por observación experta).

    Distingue la eficiencia ambiental (A1–A9) de una mejora verificable en el ESTADO del ecosistema.
    ΔY = Y_t − Y_0 es descriptivo: sin anclas validadas A10 no se normaliza ni puntúa. Solo una ficha
    completa y con evidencia verificada (OBS) permite evaluar la salvaguarda G3; en otro caso G3
    queda indeterminada.
    """

    AUMENTO, DISMINUCION = "AUM", "DIS"
    DIRECCIONES = [(AUMENTO, "Mejora si aumenta"), (DISMINUCION, "Mejora si disminuye")]
    OBS, ND, NV, NA = "OBS", "ND", "NV", "NA"
    ESTADOS = [(OBS, "Observado y verificable"), (ND, "No disponible"), (NV, "No verificable"),
               (NA, "No aplicable (justificado)")]

    periodo = models.OneToOneField(Periodo, on_delete=models.CASCADE, related_name="ficha_ecologica")
    variable = models.CharField("Variable ecológica de estado", max_length=200, blank=True,
                                help_text="Indicador de ESTADO del ecosistema (no de presión o eficiencia). "
                                          "Ej.: cobertura de vegetación nativa, un parámetro de calidad de agua, "
                                          "riqueza de especies nativas")
    justificacion = models.TextField("Pertinencia local", blank=True)
    unidad = models.CharField("Unidad de medida", max_length=60, blank=True, help_text="%, mg/L, individuos/ha, …")
    metodo = models.TextField("Método de medición", blank=True)
    direccion = models.CharField("Dirección favorable", max_length=3, choices=DIRECCIONES, blank=True,
                                 help_text="Se define ANTES de analizar el resultado")
    y0 = models.FloatField("Línea base Y₀", null=True, blank=True)
    y0_fecha = models.DateField("Fecha de la línea base", null=True, blank=True)
    yt = models.FloatField("Seguimiento Yₜ", null=True, blank=True)
    yt_fecha = models.DateField("Fecha del seguimiento", null=True, blank=True)
    area = models.TextField("Área de evaluación", blank=True,
                            help_text="Polígono o coordenadas, superficie, ecosistema y relación con la intervención")
    periodo_inicio = models.DateField("Inicio del período", null=True, blank=True)
    periodo_fin = models.DateField("Fin del período", null=True, blank=True)
    estacionalidad = models.CharField("Periodicidad y estacionalidad", max_length=200, blank=True)
    contribucion = models.TextField("Contribución del emprendimiento", blank=True,
                                    help_text="Acciones documentadas, localización, secuencia temporal, mecanismo "
                                              "plausible y factores externos")
    y0_referencia = models.FloatField("Y₀ del sitio de referencia", null=True, blank=True)
    yt_referencia = models.FloatField("Yₜ del sitio de referencia", null=True, blank=True)
    fuentes = models.TextField("Fuentes de verificación", blank=True,
                               help_text="Monitoreo de campo, laboratorio, registros georreferenciados, auditoría")
    estado = models.CharField("Estado de la evidencia", max_length=3, choices=ESTADOS, default=ND)
    responsable = models.CharField(max_length=120, blank=True)

    CAMPOS_REQUERIDOS = ["variable", "unidad", "metodo", "direccion", "y0", "y0_fecha", "yt", "yt_fecha", "area",
                         "periodo_inicio", "periodo_fin", "contribucion", "fuentes"]

    class Meta:
        verbose_name = "ficha ecológica A10"
        verbose_name_plural = "fichas ecológicas A10"

    def __str__(self):
        return f"A10 · {self.periodo}"

    def faltantes(self):
        return [self._meta.get_field(c).verbose_name for c in self.CAMPOS_REQUERIDOS
                if getattr(self, c) in (None, "")]

    @property
    def completa(self):
        return not self.faltantes()

    @property
    def verificada(self):
        return self.completa and self.estado == self.OBS

    @property
    def delta(self):
        return None if self.y0 is None or self.yt is None else self.yt - self.y0

    @property
    def delta_ajustado(self):
        """ΔY_aj = (Yₜ − Y₀)_intervención − (Yₜ − Y₀)_referencia; por sí solo no demuestra causalidad."""
        if self.delta is None or self.y0_referencia is None or self.yt_referencia is None:
            return None
        return self.delta - (self.yt_referencia - self.y0_referencia)

    @property
    def favorable(self):
        """¿El cambio va en la dirección favorable definida? Usa ΔY ajustado si hay sitio de referencia."""
        d = self.delta_ajustado if self.delta_ajustado is not None else self.delta
        if d is None or not self.direccion:
            return None
        return d > 0 if self.direccion == self.AUMENTO else d < 0


class VerificacionSalvaguarda(models.Model):
    """Verificación documentada de una condición habilitante G1–G5 (§2.4).

    G1, G3, G4 y G5 tienen una regla automática; este registro la sustituye cuando
    existe evidencia revisada por el evaluador. G2 solo se establece por verificación.
    """

    CODIGOS = [
        ("G1", "G1 · Viabilidad económica"),
        ("G2", "G2 · No daño social crítico"),
        ("G3", "G3 · Resultado ambiental positivo"),
        ("G4", "G4 · Trazabilidad y cobertura"),
        ("G5", "G5 · Persistencia temporal"),
    ]
    ESTADOS = [("1", "Se verifica"), ("0", "Se incumple")]

    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name="salvaguardas")
    codigo = models.CharField(max_length=2, choices=CODIGOS)
    estado = models.CharField(max_length=1, choices=ESTADOS)
    evidencia = models.CharField(max_length=300, help_text="Documento, registro o verificación que lo respalda")
    responsable = models.CharField(max_length=120, blank=True)
    fecha = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [("periodo", "codigo")]
        ordering = ["codigo"]
        verbose_name = "verificación de salvaguarda"
        verbose_name_plural = "verificaciones de salvaguardas"

    def __str__(self):
        return f"{self.periodo} · {self.codigo}={self.estado}"


class Evaluacion(models.Model):
    """Resultado del FRR para un período, con la configuración usada (§2.10.2 Versiones)."""

    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name="evaluaciones")
    clasificacion = models.CharField(max_length=1, blank=True, help_text="a–e según §2.2")
    veredicto = models.CharField(max_length=120)
    irr = models.FloatField("IRR suavizado", null=True, blank=True)
    irr0 = models.FloatField("IRR₀ sin suavizado", null=True, blank=True)
    media_aritmetica = models.FloatField(null=True, blank=True)
    elegibilidad = models.CharField("R (elegibilidad regenerativa)", max_length=14, blank=True)
    cuello_de_botella = models.CharField(max_length=8, blank=True)
    version = models.CharField(max_length=12, blank=True)
    detalle = models.JSONField(default=dict, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]
        verbose_name = "evaluación"
        verbose_name_plural = "evaluaciones"

    def __str__(self):
        return f"{self.periodo} · {self.veredicto}"
