from django.contrib import admin

from administracion.models import ConfiguracionSistema, RegistroActividad


@admin.register(RegistroActividad)
class RegistroActividadAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "accion", "entidad", "objeto", "resultado")
    list_filter = ("accion", "resultado")
    search_fields = ("objeto", "entidad")

    # El registro de auditoría es de solo lectura, también desde /admin/.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ConfiguracionSistema)
class ConfiguracionSistemaAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not ConfiguracionSistema.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
