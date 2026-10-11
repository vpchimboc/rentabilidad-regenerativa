from django.contrib import admin

from bibliometria.models import Referencia, RegistroPRISMA


@admin.register(Referencia)
class ReferenciaAdmin(admin.ModelAdmin):
    list_display = ("autores", "anio", "titulo", "revista", "base", "incluida")
    list_filter = ("base", "anio", "incluida")
    search_fields = ("autores", "titulo", "palabras_clave", "hallazgos")


@admin.register(RegistroPRISMA)
class RegistroPRISMAAdmin(admin.ModelAdmin):
    list_display = ("fase", "cantidad", "detalle")
    list_editable = ("cantidad", "detalle")
