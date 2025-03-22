from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Avg
import numpy as np
import os
import json
import pickle
from sklearn.linear_model import LinearRegression
from django.conf import settings
from .models import *
from .forms import *
from django.views.decorators.http import require_POST
# Basic Views
def home(request):
    """Home page view."""
    return render(request, 'home.html')

def about(request):
    """About page with project information."""
    return render(request, 'about.html')

def register(request):
    """User registration view."""
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create Student or Teacher profile based on role
            role = form.cleaned_data.get('role')
            if role == 'student':
                Student.objects.create(
                    user=user,
                    student_id=form.cleaned_data.get('id_number')
                )
            elif role == 'teacher':
                Teacher.objects.create(user=user)
            
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! Please log in.')
            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, 'register.html', {'form': form})

@login_required
def dashboard(request):
    """Main dashboard view - redirects to appropriate dashboard based on user role."""
    if hasattr(request.user, 'teacher'):
        return redirect('teacher_dashboard')
    elif hasattr(request.user, 'student'):
        return redirect('student_dashboard')
    else:
        messages.warning(request, 'Your account is not properly set up. Please contact an administrator.')
        return redirect('home')

# Teacher Views
@login_required
def teacher_dashboard(request):
    """Teacher dashboard with course overview."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
        
    # Get courses taught by this teacher
    teacher = request.user.teacher
    courses = Course.objects.filter(teacher=teacher)
    
    # Calculate statistics for dashboard
    at_risk_count = 0
    all_grades = []
    
    for course in courses:
        # Calculate average performance for each course
        grades = StudentGrade.objects.filter(course=course)
        course_grades = [grade.grade for grade in grades if grade.grade is not None]
        
        if course_grades:
            course.average_performance = sum(course_grades) / len(course_grades)
            all_grades.extend(course_grades)
        else:
            course.average_performance = 0
        
        # Identify at-risk students (those with grades below 60)
        at_risk_students = len([g for g in course_grades if g < 60])
        course.at_risk_count = at_risk_students
        at_risk_count += at_risk_students
    
    # Get total unique students in the database
    total_students = Student.objects.count()
    
    context = {
        'courses': courses,
        'total_students': total_students,
        'at_risk_count': at_risk_count,
    }
    
    return render(request, 'teacher/dashboard.html', context)

@login_required
def add_course(request):
    """View for adding a new course."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to add courses.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CourseForm(request.POST, initial={'teacher': request.user.teacher})
        
        if form.is_valid():
            # Create course but don't save to DB yet
            course = form.save(commit=False)
            course.teacher = request.user.teacher
            course.save()
            
            messages.success(request, f'Course "{course.name}" has been created successfully.')
            return redirect('teacher_dashboard')
        else:
            # If form is invalid, pass errors to template
            context = {
                'form_errors': 'This course code already exists. Please use a different code.'
            }
            return render(request, 'teacher/dashboard.html', context)
    
    return redirect('teacher_dashboard')

@login_required
def course_detail(request, course_id):
    """View details of a specific course."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
        
    # Get the course
    course = get_object_or_404(Course, id=course_id, teacher=request.user.teacher)
    
    # Get students enrolled in this course
    students = course.students.all()
    
    # Get grades
    student_grades = StudentGrade.objects.filter(course=course)
    
    # Get prediction models
    prediction_models = PredictionModel.objects.filter(course=course)
    
    # Calculate at-risk count - only for students at the same level as the course
    at_risk_grades = [g.grade for g in student_grades if g.grade is not None and g.grade < 60 and g.student.level == course.level]
    course.at_risk_count = len(at_risk_grades)
    
    # Calculate average performance
    all_grades = [g.grade for g in student_grades if g.grade is not None]
    course.average_performance = sum(all_grades) / len(all_grades) if all_grades else 0
    
    context = {
        'course': course,
        'students': students,
        'prediction_models': prediction_models,
    }
    
    return render(request, 'teacher/course_detail.html', context)

@login_required
def student_grades(request):
    """Spreadsheet view of all student grades with proper level-based access control."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
        
    # Get the teacher
    teacher = request.user.teacher
    
    # Get all courses taught by this teacher, organized by level
    courses = Course.objects.filter(teacher=teacher).order_by('level', 'name')
    
    # Group courses by level for easier template rendering
    course_levels = {}
    for course in courses:
        if course.level not in course_levels:
            course_levels[course.level] = []
        course_levels[course.level].append(course)
    
    # Get all students enrolled in any of these courses
    enrolled_student_ids = set()
    for course in courses:
        enrolled_student_ids.update(course.students.values_list('id', flat=True))
    
    # Fix: Corrected the syntax error in this line
    students = Student.objects.filter(id__in=enrolled_student_ids).order_by('name')
    
    # If form is submitted, update grades - only where allowed based on student level
    if request.method == 'POST':
        updated_count = 0
        for student in students:
            for course in courses:
                # Skip courses that are higher level than student's level
                if course.level > student.level:
                    continue
                
                # For level 2 students, don't allow editing level 1 courses
                if student.level > course.level:
                    continue
                    
                grade_key = f"grade_{student.id}_{course.id}"
                attendance_key = f"attendance_{student.id}_{course.id}"
                
                grade_value = request.POST.get(grade_key, '').strip()
                attendance_value = request.POST.get(attendance_key, '').strip()
                
                # Only process if student is enrolled in this course
                if student in course.students.all():
                    # If both are empty and grade doesn't exist, skip
                    if not grade_value and not attendance_value:
                        continue
                        
                    # Create or update grade
                    student_grade, created = StudentGrade.objects.get_or_create(
                        student=student,
                        course=course,
                        defaults={
                            'grade': float(grade_value) if grade_value else None,
                            'attendance_percentage': float(attendance_value) if attendance_value else None
                        }
                    )
                    
                    # Update existing grade
                    if not created:
                        if grade_value:
                            student_grade.grade = float(grade_value)
                        if attendance_value:
                            student_grade.attendance_percentage = float(attendance_value)
                        student_grade.save()
                        
                    updated_count += 1
        
        messages.success(request, f'Grades updated successfully. {updated_count} records updated.')
        return redirect('student_grades')
    
    # Prepare data for the template
    grades_data = {}
    student_level_courses = {}
    
    for student in students:
        grades_data[student.id] = {}
        student_level_courses[student.id] = {}
        
        for course in courses:
            # Check if student is currently enrolled
            actual_enrollment = student in course.students.all()
            
            # For level 2 students and level 1 courses:
            # - They should be marked as enrolled (to show the grades)
            # - They should not be able to edit (readonly fields)
            if student.level > course.level:
                # Level 2 student looking at level 1 course
                can_edit = False
                can_view = True  # Always allow viewing
            else:
                # Normal case: level matches or course level is higher
                can_edit = actual_enrollment and course.level <= student.level
                can_view = actual_enrollment and course.level <= student.level
            
            student_level_courses[student.id][course.id] = {
                'enrolled': True,  # Always mark as enrolled to avoid "Not Enrolled" message
                'can_edit': can_edit,
                'can_view': can_view
            }
            
            # IMPORTANT CHANGE: Always try to get grades for all students and all courses,
            # regardless of current enrollment status
            try:
                grade = StudentGrade.objects.get(student=student, course=course)
                grades_data[student.id][course.id] = {
                    'grade': grade.grade,
                    'attendance': grade.attendance_percentage
                }
            except StudentGrade.DoesNotExist:
                grades_data[student.id][course.id] = {
                    'grade': None,
                    'attendance': None
                }
    
    context = {
        'courses': courses,
        'course_levels': course_levels,
        'students': students,
        'grades_data': grades_data,
        'student_level_courses': student_level_courses,
        'active_tab': request.GET.get('tab', 'level1')
    }
    
    return render(request, 'teacher/student_grades.html', context)

@login_required
def add_student_to_course(request, course_id):
    """Add a student to a course."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
            
    # Get the course
    course = get_object_or_404(Course, id=course_id, teacher=request.user.teacher)
    
    if request.method == 'POST':
        student_id_number = request.POST.get('student_id')
        student_name = request.POST.get('student_name')
        
        if not student_id_number:
            messages.error(request, 'Student ID is required.')
            return redirect('course_detail', course_id=course.id)
        
        # Try to find existing student or create new one
        try:
            student = Student.objects.get(student_id=student_id_number)
            # Update name if provided and different
            if student_name and student.name != student_name:
                student.name = student_name
                student.save()
                
        except Student.DoesNotExist:
            if not student_name:
                messages.error(request, 'Student name is required for new students.')
                return redirect('course_detail', course_id=course.id)
            
            # Create new student
            student = Student.objects.create(
                student_id=student_id_number,
                name=student_name
            )
        
        # Add student to course if not already enrolled
        if student in course.students.all():
            messages.warning(request, f'Student {student.name} is already enrolled in this course.')
        else:
            course.students.add(student)
            messages.success(request, f'Student {student.name} added to the course successfully.')
        
        return redirect('course_detail', course_id=course.id)
    
    # This view should only handle POST requests
    return redirect('course_detail', course_id=course.id)

@login_required
def remove_student_from_course(request, course_id, student_id):
    """Remove a student from a course."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    # Get the course and student
    course = get_object_or_404(Course, id=course_id, teacher=request.user.teacher)
    student = get_object_or_404(Student, id=student_id)
    
    # Remove student from course
    if student in course.students.all():
        course.students.remove(student)
        
        # Delete associated grades
        StudentGrade.objects.filter(student=student, course=course).delete()
        
        messages.success(request, f'Student {student.name} removed from the course.')
    else:
        messages.error(request, f'Student {student.name} is not enrolled in this course.')
    
    return redirect('course_detail', course_id=course.id)

@login_required
def search_students(request, course_id):
    """AJAX endpoint to search for students."""
    if not hasattr(request.user, 'teacher'):
        return JsonResponse({'results': []})
        
    # Get the course
    course = get_object_or_404(Course, id=course_id, teacher=request.user.teacher)
    
    search_term = request.GET.get('term', '')

    if len(search_term) < 2:  # Require at least 2 characters
        return JsonResponse({'results': []})
    
    # Find students not already in this course
    current_students = course.students.values_list('id', flat=True)
    students = Student.objects.exclude(id__in=current_students).filter(
        Q(name__icontains=search_term) | 
        Q(student_id__icontains=search_term)
    )[:10]  # Limit results
    
    results = [{'id': student.id, 'text': f"{student.name} ({student.student_id})"} for student in students]
    return JsonResponse({'results': results})

@login_required
def create_model_page(request, course_id):
    """Show form for creating a prediction model."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    # Get the course
    course = get_object_or_404(Course, id=course_id, teacher=request.user.teacher)
    
    # Get available subjects (courses) for prediction
    teacher_courses = Course.objects.filter(teacher=request.user.teacher)
    
    # Get courses with data
    courses_with_data = []
    for tcourse in teacher_courses:
        if StudentGrade.objects.filter(course=tcourse).exists():
            courses_with_data.append(tcourse)
    
    context = {
        'course': course,
        'available_courses': courses_with_data,
    }
    
    return render(request, 'teacher/create_model.html', context)

@login_required
def generate_predictions(request, course_id):
    """Create a prediction model and make predictions."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    # Get the course
    course = get_object_or_404(Course, id=course_id, teacher=request.user.teacher)
    
    if request.method == 'POST':
        # Get selected features and target
        feature_course_ids = request.POST.getlist('features')
        target_course_id = request.POST.get('target')
        model_name = request.POST.get('model_name')
        
        if not feature_course_ids or not target_course_id or not model_name:
            messages.error(request, 'Please select at least one feature course, a target course, and provide a model name.')
            return redirect('create_model_page', course_id=course.id)
        
        # Get feature and target courses
        feature_courses = Course.objects.filter(id__in=feature_course_ids)
        target_course = get_object_or_404(Course, id=target_course_id)
        
        # Get students with data for all required courses
        all_students = set(course.students.all())
        valid_students = []
        
        # For each student, check if they have grades for all required courses
        X = []  # Features
        y = []  # Target
        
        for student in all_students:
            feature_values = []
            has_all_data = True
            
            # Check each feature course
            for fcourse in feature_courses:
                try:
                    grade = StudentGrade.objects.get(student=student, course=fcourse)
                    if grade.grade is None:
                        has_all_data = False
                        break
                    feature_values.append(grade.grade)
                except StudentGrade.DoesNotExist:
                    has_all_data = False
                    break
            
            # Check target course
            try:
                target_grade = StudentGrade.objects.get(student=student, course=target_course)
                if target_grade.grade is None:
                    has_all_data = False
            except StudentGrade.DoesNotExist:
                has_all_data = False
            
            # If student has all required data, add to training set
            if has_all_data:
                X.append(feature_values)
                y.append(target_grade.grade)
                valid_students.append(student.id)
        
        # Check if we have enough data
        if len(X) < 5:
            messages.error(request, 'Not enough data to train the model. Need at least 5 students with complete data.')
            return redirect('create_model_page', course_id=course.id)
        
        # Train the model using scikit-learn
        X_array = np.array(X)
        y_array = np.array(y)
        
        model = LinearRegression()
        model.fit(X_array, y_array)
        
        # Create a directory for saving models if it doesn't exist
        model_dir = os.path.join(settings.MEDIA_ROOT, 'prediction_models')
        os.makedirs(model_dir, exist_ok=True)
        
        # Save the model to a file
        model_filename = f"model_{course.id}_{model_name.replace(' ', '_')}.pkl"
        model_path = os.path.join(model_dir, model_filename)
        
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        
        # Store model metadata in database
        features_json = json.dumps([int(id) for id in feature_course_ids])
        
        prediction_model = PredictionModel.objects.create(
            name=model_name,
            course=course,
            features=features_json,
            target=target_course.id,
            model_file=f"prediction_models/{model_filename}"
        )
        
        messages.success(request, f'Model "{model_name}" created successfully with {len(X)} student records.')
        return redirect('course_detail', course_id=course.id)
    
    # For GET requests, redirect to model creation page
    return redirect('create_model_page', course_id=course.id)
@login_required
def course_grades(request, course_id):
    """View to input grades for a specific course."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
        
    # Get the course
    course = get_object_or_404(Course, id=course_id, teacher=request.user.teacher)
    
    # Get students enrolled in this course
    students = course.students.all()
    
    if request.method == 'POST':
        # Process form submission
        for student in students:
            grade_key = f"grade_{student.id}"
            attendance_key = f"attendance_{student.id}"
            
            grade_value = request.POST.get(grade_key, '').strip()
            attendance_value = request.POST.get(attendance_key, '').strip()
            
            if grade_value or attendance_value:
                # Create or update grade
                student_grade, created = StudentGrade.objects.get_or_create(
                    student=student,
                    course=course,
                    defaults={
                        'grade': float(grade_value) if grade_value else None,
                        'attendance_percentage': float(attendance_value) if attendance_value else None
                    }
                )
                
                # Update existing grade
                if not created:
                    if grade_value:
                        student_grade.grade = float(grade_value)
                    if attendance_value:
                        student_grade.attendance_percentage = float(attendance_value)
                    student_grade.save()
        
        messages.success(request, 'Grades updated successfully.')
        return redirect('course_detail', course_id=course.id)
    
    # Prepare existing grades for display
    student_grades = {}
    for student in students:
        try:
            grade = StudentGrade.objects.get(student=student, course=course)
            student_grades[student.id] = {
                'grade': grade.grade,
                'attendance': grade.attendance_percentage
            }
        except StudentGrade.DoesNotExist:
            student_grades[student.id] = {
                'grade': None,
                'attendance': None
            }
    
    context = {
        'course': course,
        'students': students,
        'student_grades': student_grades,
    }
    
    return render(request, 'course_grades.html', context)

@login_required
@require_POST
def promote_selected_students(request):
    """
    Promotes multiple selected students to the next level.
    This view handles the form submission from the student_grades.html template.
    """
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to perform this action.')
        return redirect('dashboard')
    
    student_ids = request.POST.getlist('student_ids')
    
    if not student_ids:
        messages.warning(request, "No students were selected for promotion.")
        return redirect('student_grades')
    
    promoted_count = 0
    for student_id in student_ids:
        try:
            student = Student.objects.get(id=student_id)
            # The progress_to_next_level method now handles all enrollment changes
            if student.progress_to_next_level():
                promoted_count += 1
        except Student.DoesNotExist:
            continue
    
    if promoted_count > 0:
        messages.success(request, f"{promoted_count} students have been promoted to the next level.")
    else:
        messages.info(request, "No students were eligible for promotion.")
    
    # Redirect back to the grades page, preserving the level1 tab
    return redirect('student_grades')

# Student Views
@login_required
def student_dashboard(request):
    """Dashboard for students."""
    if not hasattr(request.user, 'student'):
        messages.warning(request, 'You need to be a student to access this page.')
        return redirect('dashboard')
    
    student = request.user.student
    courses = student.courses.all()
    
    course_data = []
    for course in courses:
        try:
            grade = StudentGrade.objects.get(student=student, course=course)
            grade_value = grade.grade
            attendance = grade.attendance_percentage
        except StudentGrade.DoesNotExist:
            grade_value = None
            attendance = None
        
        course_data.append({
            'course': course,
            'grade': grade_value,
            'attendance': attendance
        })
    
    context = {
        'student': student,
        'course_data': course_data
    }
    
    return render(request, 'student/student_dashboard.html', context)