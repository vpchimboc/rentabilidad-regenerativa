from django.contrib import admin

from rna.models import ModeloRNA


@admin.register(ModeloRNA)
class ModeloRNAAdmin(admin.ModelAdmin):
    list_display = ("nombre", "n_entradas", "n_ocultas", "epocas", "tasa_aprendizaje",
                    "n_muestras", "r2", "activo", "creado")
    list_filter = ("activo",)
    readonly_fields = ("pesos", "metricas", "historial", "codigos_entrada")

    @admin.display(description="R²")
    def r2(self, obj):
        return obj.metricas.get("r2", "—")
