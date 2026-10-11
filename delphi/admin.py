from django.contrib import admin

from delphi.models import Experto, Item, ResultadoRonda, Respuesta, Ronda


@admin.register(Experto)
class ExpertoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "grado", "institucion", "pais", "anios_experiencia",
                    "publicaciones", "cumple_criterios", "activo")
    list_filter = ("grado", "pais", "activo")
    search_fields = ("nombre", "institucion")

    @admin.display(boolean=True, description="Cumple criterios")
    def cumple_criterios(self, obj):
        return obj.cumple_criterios


@admin.register(Ronda)
class RondaAdmin(admin.ModelAdmin):
    list_display = ("numero", "fecha", "estado")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("codigo", "criterio", "componente", "orden")
    list_filter = ("criterio",)
    search_fields = ("codigo", "enunciado")


@admin.register(Respuesta)
class RespuestaAdmin(admin.ModelAdmin):
    list_display = ("ronda", "experto", "item", "valor")
    list_filter = ("ronda", "experto", "item__criterio")
    list_editable = ("valor",)


@admin.register(ResultadoRonda)
class ResultadoRondaAdmin(admin.ModelAdmin):
    list_display = ("ronda", "s_cvi", "kendall_w", "chi_cuadrado", "gl", "consenso")
    readonly_fields = ("detalle",)
