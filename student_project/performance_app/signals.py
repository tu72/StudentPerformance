from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.apps import apps
from django.db import transaction


# Create attendance courses for each level if they don't exist yet
def create_attendance_courses():
    """
    Make sure attendance courses exist for each level.
    Each level should have a dedicated attendance course.
    """
    try:
        Course = apps.get_model('performance_app', 'Course')
        
        # Get all levels in the system by looking at students
        Student = apps.get_model('performance_app', 'Student')
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
            
        return created_any
    except Exception as e:
        print(f"Error creating attendance courses: {str(e)}")
        return False

@receiver(post_save, sender='performance_app.Student')
def create_attendance_courses_after_student_creation(sender, instance, created, **kwargs):
    """
    Create attendance courses when a student is created.
    """
    if created:
        # Only create attendance courses if this is the first student
        Student = apps.get_model('performance_app', 'Student')
        if Student.objects.count() == 1:
            transaction.on_commit(create_attendance_courses)


@receiver(post_save, sender='performance_app.Course')
def enroll_students_in_new_course(sender, instance, created, **kwargs):
    """
    When a new course is created, automatically enroll all students of the same level.
    """
    if created:
        # Get Student model
        Student = apps.get_model('performance_app', 'Student')
        
        # Find all students in the same level as the course
        students_in_level = Student.objects.filter(level=instance.level)
        
        # Add all students to the course
        if students_in_level.exists():
            instance.students.add(*students_in_level)


@receiver(post_save, sender='performance_app.Student')
def ensure_student_course_enrollment(sender, instance, created, **kwargs):
    """
    Ensure a student is enrolled in all courses of their level,
    and not enrolled in courses of other levels.
    """
    # Get Course model
    Course = apps.get_model('performance_app', 'Course')
    
    # Get courses for the student's level
    level_courses = Course.objects.filter(level=instance.level)
    
    # Get current courses the student is enrolled in
    current_courses = instance.courses.all()
    
    # Find courses to add (in current level but not enrolled)
    courses_to_add = level_courses.exclude(id__in=current_courses.values_list('id', flat=True))
    
    # Find courses to remove (enrolled but not in current level)
    courses_to_remove = current_courses.exclude(level=instance.level)
    
    # Update enrollments
    if courses_to_add.exists():
        instance.courses.add(*courses_to_add)
    
    if courses_to_remove.exists():
        instance.courses.remove(*courses_to_remove)


@receiver(post_delete, sender='performance_app.Course')
def cleanup_after_course_deletion(sender, instance, **kwargs):
    """
    Clean up any related data when a course is deleted.
    """
    # Get StudentGrade model
    StudentGrade = apps.get_model('performance_app', 'StudentGrade')
    
    # Delete any grades associated with this course
    StudentGrade.objects.filter(course=instance).delete()


# Function to update student enrollments after level change
def update_student_enrollments_after_level_change(student, old_level, new_level):
    """
    Update student enrollments after a level change.
    This should be called whenever a student's level changes.
    """
    # Get Course model
    Course = apps.get_model('performance_app', 'Course')
    
    # Remove from old level courses
    old_level_courses = Course.objects.filter(level=old_level)
    student.courses.remove(*old_level_courses)
    
    # Add to new level courses
    new_level_courses = Course.objects.filter(level=new_level)
    student.courses.add(*new_level_courses)