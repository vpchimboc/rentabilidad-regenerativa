from django.apps import AppConfig


class AdministracionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "administracion"
    verbose_name = "Administración"

    def ready(self):
        from administracion import senales  # noqa: F401  (registra los receptores)
