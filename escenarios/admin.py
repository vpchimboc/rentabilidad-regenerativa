from django.contrib import admin

from escenarios.models import Escenario


@admin.register(Escenario)
class EscenarioAdmin(admin.ModelAdmin):
    list_display = ("periodo", "tipo", "factor", "irr", "clasificacion", "veredicto", "version", "creado")
    list_filter = ("tipo", "periodo__emprendimiento")
    readonly_fields = ("detalle",)
