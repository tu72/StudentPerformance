from django.apps import AppConfig


class PerformanceAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'performance_app'
    def ready(self):
        # Import signals module to ensure signals are connected
        import performance_app.signals  # Replace with your actual app name