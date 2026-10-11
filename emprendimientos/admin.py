from django.contrib import admin

from emprendimientos.models import Emprendimiento, Evaluacion, Medicion, Periodo


class MedicionInline(admin.TabularInline):
    model = Medicion
    extra = 0
    autocomplete_fields = ["indicador"]


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
    inlines = [MedicionInline]

    @admin.display(description="Punto de equilibrio (USD)")
    def punto_equilibrio(self, obj):
        return f"{obj.punto_equilibrio:,.2f}"

    @admin.display(description="Ventas / break-even")
    def margen_sobre_break_even(self, obj):
        return f"{obj.margen_sobre_break_even:.2f}x"


@admin.register(Medicion)
class MedicionAdmin(admin.ModelAdmin):
    list_display = ("periodo", "indicador", "valor", "nivel")
    list_filter = ("indicador__variable__dimension", "periodo__emprendimiento")


@admin.register(Evaluacion)
class EvaluacionAdmin(admin.ModelAdmin):
    list_display = ("periodo", "irr", "minimo_dimensional", "veredicto", "cuello_de_botella", "creado")
    list_filter = ("veredicto", "periodo__emprendimiento")
    readonly_fields = ("detalle",)
