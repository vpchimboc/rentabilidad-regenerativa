from django.contrib import admin

from framework.models import Dimension, Indicador, ParametrosFRR, Variable


class VariableInline(admin.TabularInline):
    model = Variable
    extra = 0


class IndicadorInline(admin.TabularInline):
    model = Indicador
    extra = 0
    fields = ("codigo", "nombre", "estado", "tipo", "peso", "ref_l", "ref_u", "ref_t", "ref_h")


@admin.register(Dimension)
class DimensionAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "peso", "orden")
    list_editable = ("peso", "orden")
    inlines = [VariableInline]


@admin.register(Variable)
class VariableAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "dimension")
    list_filter = ("dimension",)
    inlines = [IndicadorInline]


@admin.register(Indicador)
class IndicadorAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "variable", "estado", "tipo", "ref_l", "ref_u", "tipo_fuente_referencia", "estado_referencia")
    list_editable = ("estado", "ref_l", "ref_u", "tipo_fuente_referencia", "estado_referencia")
    list_per_page = 50
    list_filter = ("variable__dimension", "estado", "rol", "tipo", "tipo_fuente_referencia", "estado_referencia")
    search_fields = ("codigo", "nombre")
    fieldsets = (
        ("Ficha", {"fields": ("variable", "codigo", "nombre", "formula", "componentes", "unidad", "rol", "estado", "version_ficha", "orden")}),
        ("Normalización (§2.5)", {"fields": ("tipo", "peso", "ref_l", "ref_u", "ref_t", "ref_h")}),
        ("Ficha de la referencia", {"fields": ("tipo_fuente_referencia", "fuente_referencia", "periodo_referencia", "evidencia_referencia", "estado_referencia")}),
        ("Trazabilidad", {"fields": ("equivalencia_v0",)}),
    )


@admin.register(ParametrosFRR)
class ParametrosFRRAdmin(admin.ModelAdmin):
    list_display = ("version", "epsilon", "cobertura_minima", "activo", "creado")