from django.contrib import admin

from emprendimientos.models import (Emprendimiento, Evaluacion, FichaEcologica, Medicion, Periodo,
                                     VerificacionSalvaguarda)


class MedicionInline(admin.TabularInline):
    model = Medicion
    extra = 0
    autocomplete_fields = ["indicador"]
    fields = ("indicador", "estado", "valor", "numerador", "denominador", "fuente", "fecha_medicion", "responsable", "observaciones", "simulado")


class SalvaguardaInline(admin.TabularInline):
    model = VerificacionSalvaguarda
    extra = 0


class FichaEcologicaInline(admin.StackedInline):
    model = FichaEcologica
    extra = 0
    max_num = 1
    verbose_name = "ficha ecológica A10 (resultado ecológico neto y salvaguarda G3)"
    fieldsets = (
        ("Variable ecológica", {"fields": ("variable", "justificacion", "unidad", "metodo", "direccion")}),
        ("Línea base y seguimiento", {"fields": (("y0", "y0_fecha"), ("yt", "yt_fecha"))}),
        ("Área y período", {"fields": ("area", ("periodo_inicio", "periodo_fin"), "estacionalidad")}),
        ("Contribución del emprendimiento", {"fields": ("contribucion", ("y0_referencia", "yt_referencia"))}),
        ("Verificación", {"fields": ("fuentes", "estado", "responsable")}),
    )


class PeriodoInline(admin.TabularInline):
    model = Periodo
    extra = 0
    fields = ("anio", "etiqueta", "ventas", "costos_fijos", "costos_variables")


@admin.register(Emprendimiento)
class EmprendimientoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "ruc", "sector", "ciudad", "provincia", "empleados", "fuente")
    list_filter = ("sector", "provincia", "fuente")
    search_fields = ("nombre", "ruc", "ciiu")
    inlines = [PeriodoInline]


@admin.register(Periodo)
class PeriodoAdmin(admin.ModelAdmin):
    list_display = ("emprendimiento", "anio", "ventas", "punto_equilibrio", "margen_sobre_break_even")
    list_filter = ("anio", "emprendimiento")
    inlines = [FichaEcologicaInline, MedicionInline, SalvaguardaInline]

    @admin.display(description="Punto de equilibrio (USD)")
    def punto_equilibrio(self, obj):
        return f"{obj.punto_equilibrio:,.2f}"

    @admin.display(description="Ventas / break-even")
    def margen_sobre_break_even(self, obj):
        return f"{obj.margen_sobre_break_even:.2f}x"


@admin.register(Medicion)
class MedicionAdmin(admin.ModelAdmin):
    list_display = ("periodo", "indicador", "estado", "valor", "puntuacion_z", "fuente")
    list_filter = ("simulado", "estado", "indicador__variable__dimension", "periodo__emprendimiento")

    @admin.display(description="z")
    def puntuacion_z(self, obj):
        z = obj.z
        return "—" if z is None else f"{z:.3f}"


@admin.register(Evaluacion)
class EvaluacionAdmin(admin.ModelAdmin):
    list_display = ("periodo", "clasificacion", "veredicto", "irr", "elegibilidad", "version", "creado")
    list_filter = ("clasificacion", "version", "periodo__emprendimiento")
    readonly_fields = ("detalle",)


@admin.register(VerificacionSalvaguarda)
class VerificacionSalvaguardaAdmin(admin.ModelAdmin):
    list_display = ("periodo", "codigo", "estado", "evidencia", "responsable", "fecha")
    list_filter = ("codigo", "estado")
