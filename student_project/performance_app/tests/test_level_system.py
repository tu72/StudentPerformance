from django.test import TestCase
from performance_app.models import Student, Course, Teacher, User

class LevelSystemTestCase(TestCase):
    def setUp(self):
        # Create a teacher
        self.user = User.objects.create_user(username='teacher', password='password')
        self.teacher = Teacher.objects.create(user=self.user)
        
        # Create courses for different levels
        self.course_level1_math = Course.objects.create(
            name='Math 101', 
            code='MATH101', 
            teacher=self.teacher, 
            level=1
        )
        
        self.course_level1_english = Course.objects.create(
            name='English 101', 
            code='ENG101', 
            teacher=self.teacher, 
            level=1
        )
        
        self.course_level2_math = Course.objects.create(
            name='Math 201', 
            code='MATH201', 
            teacher=self.teacher, 
            level=2
        )
        
        self.course_level2_english = Course.objects.create(
            name='English 201', 
            code='ENG201', 
            teacher=self.teacher, 
            level=2
        )
        
        # Create students
        self.student1 = Student.objects.create(
            name='Student One',
            student_id='S001',
            level=1
        )
        
        self.student2 = Student.objects.create(
            name='Student Two',
            student_id='S002',
            level=2
        )

    def test_new_student_automatic_enrollment(self):
        """Test that new students are automatically enrolled in courses of their level"""
        # Check student1 (level 1) enrollments
        self.assertIn(self.course_level1_math, self.student1.courses.all())
        self.assertIn(self.course_level1_english, self.student1.courses.all())
        self.assertNotIn(self.course_level2_math, self.student1.courses.all())
        self.assertNotIn(self.course_level2_english, self.student1.courses.all())
        
        # Check student2 (level 2) enrollments
        self.assertIn(self.course_level2_math, self.student2.courses.all())
        self.assertIn(self.course_level2_english, self.student2.courses.all())
        self.assertNotIn(self.course_level1_math, self.student2.courses.all())
        self.assertNotIn(self.course_level1_english, self.student2.courses.all())

    def test_new_course_automatic_enrollment(self):
        """Test that when a new course is created, students of that level are automatically enrolled"""
        # Create a new level 1 course
        new_course_level1 = Course.objects.create(
            name='Science 101', 
            code='SCI101', 
            teacher=self.teacher, 
            level=1
        )
        
        # Student1 (level 1) should be enrolled automatically
        self.assertIn(new_course_level1, self.student1.courses.all())
        
        # Student2 (level 2) should not be enrolled
        self.assertNotIn(new_course_level1, self.student2.courses.all())

    def test_student_promotion(self):
        """Test that when a student is promoted, enrollments are updated correctly"""
        # Promote student1 from level 1 to level 2
        self.assertTrue(self.student1.progress_to_next_level())
        
        # After promotion:
        # Should not be in level 1 courses anymore
        self.assertNotIn(self.course_level1_math, self.student1.courses.all())
        self.assertNotIn(self.course_level1_english, self.student1.courses.all())
        
        # Should be in level 2 courses
        self.assertIn(self.course_level2_math, self.student1.courses.all())
        self.assertIn(self.course_level2_english, self.student1.courses.all())

    def test_course_level_change(self):
        """Test that when a course changes level, enrollments are updated correctly"""
        # Change course_level1_math from level 1 to level 2
        self.course_level1_math.level = 2
        self.course_level1_math.save()
        
        # Student1 (level 1) should no longer be enrolled
        self.assertNotIn(self.course_level1_math, self.student1.courses.all())
        
        # Student2 (level 2) should now be enrolled
        self.assertIn(self.course_level1_math, self.student2.courses.all())