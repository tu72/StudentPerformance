from django.apps import AppConfig


class PerformanceAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'performance_app'
    
    def ready(self):
        """
        Run when the app is ready.
        """
        # Import signals
        import performance_app.signals
        
        # Attempt to create attendance courses
        from django.db import connection
        if connection.connection is not None:
            # Only run if database is connected
            try:
                # Use on_commit to run after the app is fully loaded
                from django.db import transaction
                transaction.on_commit(lambda: self._create_attendance_courses())
            except Exception as e:
                print(f"Error scheduling attendance course creation: {str(e)}")
    
    def _create_attendance_courses(self):
        """
        Create attendance courses if they don't exist.
        """
        try:
            from performance_app.signals import create_attendance_courses
            create_attendance_courses()
        except Exception as e:
            print(f"Error creating attendance courses: {str(e)}")