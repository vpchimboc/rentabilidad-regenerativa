from django.contrib import admin

from emprendimientos.models import Emprendimiento, Evaluacion, Medicion, Periodo, VerificacionSalvaguarda


class MedicionInline(admin.TabularInline):
    model = Medicion
    extra = 0
    autocomplete_fields = ["indicador"]
    fields = ("indicador", "estado", "valor", "numerador", "denominador", "fuente", "fecha_medicion", "responsable", "observaciones")


class SalvaguardaInline(admin.TabularInline):
    model = VerificacionSalvaguarda
    extra = 0


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
    inlines = [MedicionInline, SalvaguardaInline]

    @admin.display(description="Punto de equilibrio (USD)")
    def punto_equilibrio(self, obj):
        return f"{obj.punto_equilibrio:,.2f}"

    @admin.display(description="Ventas / break-even")
    def margen_sobre_break_even(self, obj):
        return f"{obj.margen_sobre_break_even:.2f}x"


@admin.register(Medicion)
class MedicionAdmin(admin.ModelAdmin):
    list_display = ("periodo", "indicador", "estado", "valor", "puntuacion_z", "fuente")
    list_filter = ("estado", "indicador__variable__dimension", "periodo__emprendimiento")

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
