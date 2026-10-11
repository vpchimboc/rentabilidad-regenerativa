from django.contrib import admin

from framework.models import Dimension, Indicador, Variable


class VariableInline(admin.TabularInline):
    model = Variable
    extra = 0


class IndicadorInline(admin.TabularInline):
    model = Indicador
    extra = 0
    fields = ("codigo", "nombre", "unidad", "direccion", "peso", "c1", "c2", "c3", "c4", "es_entrada_rna")


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
    list_display = ("codigo", "nombre", "variable", "unidad", "direccion", "peso", "es_entrada_rna")
    list_filter = ("variable__dimension", "direccion", "es_entrada_rna")
    search_fields = ("codigo", "nombre")
