# models.py
from django.db import models
from django.contrib.auth.models import User

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher')
    # Additional teacher fields
    def __str__(self):
        if self.user.first_name and self.user.last_name:
            return f"{self.user.first_name} {self.user.last_name}"
        return self.user.username

class Student(models.Model):
    """Student model representing a student in the system."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255, db_index=True)  # Add index for faster name searches
    student_id = models.IntegerField(unique=True, db_index=True)  # Add index for faster ID lookups
    level = models.PositiveIntegerField(default=1, db_index=True)  # Add index for level filtering
    courses = models.ManyToManyField('Course', related_name='students', blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['level', 'name']),  # Combined index for common filtering
        ]

    def __str__(self):
        return self.name
    
    def progress_to_next_level(self):
        """Promote student to the next level and update course enrollments."""
        if self.level < 2:  # Assuming max level is 2
            old_level = self.level
            self.level += 1
            self.save()
            
            # Import here to avoid circular import
            from .signals import update_student_enrollments_after_level_change
            
            # Update course enrollments
            update_student_enrollments_after_level_change(self, old_level, self.level)
            
            return True
        return False
        
    @classmethod
    def bulk_progress_to_next_level(cls, student_ids):
        """
        Promote multiple students to the next level efficiently.
        Returns the number of students successfully promoted.
        """
        from .signals import update_student_enrollments_after_level_change
        from django.db import transaction
        
        # Get all eligible students (level < 2)
        students = cls.objects.filter(id__in=student_ids, level__lt=2)
        student_count = students.count()
        
        if not student_count:
            return 0
            
        # Store original levels for signal processing
        student_levels = {student.id: student.level for student in students}
        
        # Use bulk update for better performance
        with transaction.atomic():
            # Update levels in bulk
            students.update(level=models.F('level') + 1)
            
            # Process course enrollments for each updated student
            for student_id, old_level in student_levels.items():
                student = cls.objects.get(id=student_id)
                update_student_enrollments_after_level_change(student, old_level, old_level + 1)
            
        return student_count

class Course(models.Model):
    """Course model representing a class that students can enroll in."""
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True)
    level = models.PositiveIntegerField(default=1)
    
    def __str__(self):
        return f"{self.name} ({self.code})"
        
    def save(self, *args, **kwargs):
        """
        Override save method to handle level changes for existing courses.
        """
        # Check if this is an existing course that's changing levels
        if self.pk:
            try:
                old_instance = Course.objects.get(pk=self.pk)
                if old_instance.level != self.level:
                    old_level = old_instance.level
                    # Save first so that signals work with the updated level
                    super().save(*args, **kwargs)
                    
                    # Get Student model
                    Student = self.students.model
                    
                    # Remove all students from the old level
                    students_to_remove = Student.objects.filter(
                        courses=self,
                        level=old_level
                    )
                    if students_to_remove.exists():
                        self.students.remove(*students_to_remove)
                    
                    # Add all students from the new level
                    students_to_add = Student.objects.filter(
                        level=self.level
                    ).exclude(
                        courses=self
                    )
                    if students_to_add.exists():
                        self.students.add(*students_to_add)
                        
                    return  # Already saved above
            except Course.DoesNotExist:
                pass  # This is a new course
        
        # Normal save for new courses or no level change
        super().save(*args, **kwargs)

class StudentGrade(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grades')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='grades')
    grade = models.FloatField(null=True, blank=True)
    
    class Meta:
        unique_together = ('student', 'course')
        indexes = [
            models.Index(fields=['student', 'course']),
            models.Index(fields=['course', 'grade']),  # For finding at-risk students
        ]
    def __str__(self):
        return f"{self.student.name} - {self.course.name}: {self.grade if self.grade is not None else 'N/A'}"

class PredictionModel(models.Model):
    name = models.CharField(max_length=100)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='models')
    features = models.JSONField()  # Store selected features as JSON
    target = models.CharField(max_length=100)  # What we're predicting (e.g., "ph2")
    model_file = models.FileField(upload_to='prediction_models/')
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.name} ({self.course.name})"

class Prediction(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='predictions')
    model = models.ForeignKey(PredictionModel, on_delete=models.CASCADE)
    predicted_value = models.FloatField()
    confidence = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)