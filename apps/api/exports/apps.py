from django.apps import AppConfig


class ExportsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "exports"

    def ready(self):
        from .config import validate_export_config

        validate_export_config()
