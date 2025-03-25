from django.core.management.base import BaseCommand
from performance_app.models import Course, Student


class Command(BaseCommand):
    help = 'Creates attendance courses for each level in the system'

    def handle(self, *args, **options):
        # Get all levels in the system by looking at students
        levels = Student.objects.values_list('level', flat=True).distinct()
        
        # If no students exist yet, default to levels 1 and 2
        if not levels:
            levels = [1, 2]
        
        created_count = 0
        
        # Create attendance course for each level
        for level in levels:
            code = f"ATTEND{level}"
            attend, created = Course.objects.get_or_create(
                code=code,
                defaults={
                    'name': f"Attendance Level {level}",
                    'level': level
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created Level {level} attendance course: {attend}'))
                created_count += 1
            else:
                self.stdout.write(f'Level {level} attendance course already exists: {attend}')
        
        # Summary
        if created_count > 0:
            self.stdout.write(self.style.SUCCESS(f'Created {created_count} attendance courses.'))
        else:
            self.stdout.write('All attendance courses already exist.') 