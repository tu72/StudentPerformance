"""
Standalone script to create attendance courses.
This can be run directly from the Django shell.

Usage:
1. Navigate to the student_project directory
2. Run: python manage.py shell
3. In the shell, type: exec(open('create_attendance_courses.py').read())
"""

from performance_app.models import Course, Student

def create_attendance_courses():
    # Get all levels in the system by looking at students
    levels = Student.objects.values_list('level', flat=True).distinct()
    
    # If no students exist yet, default to levels 1 and 2
    if not levels:
        levels = [1, 2]
    
    created_any = False
    
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
            print(f"Created Level {level} attendance course: {attend}")
            created_any = True
        else:
            print(f"Level {level} attendance course already exists: {attend}")
    
    # Summary
    if created_any:
        print('Attendance courses creation completed!')
    else:
        print('All attendance courses already exist.')
    
    return created_any

# Execute when run directly
if __name__ == "__main__":
    create_attendance_courses()
else:
    # When imported as a module
    print("Executing create_attendance_courses()")
    create_attendance_courses() 