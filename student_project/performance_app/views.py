from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Avg, F, Index, Prefetch
import numpy as np
import os
import json
import pickle
import shutil
from sklearn.linear_model import LinearRegression
from django.conf import settings
from .models import *
from .forms import *
from django.views.decorators.http import require_POST
from django.urls import reverse
import csv
import io
from django.core.paginator import Paginator
from .prediction_models import EnhancedPredictionModel, ModelPrediction, ModelFeature
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
            role = form.cleaned_data.get('role')
            
            user = form.save()
            # Create Student or Teacher profile based on role
            if role == 'student':
                # Get the highest student ID currently in the database
                last_student = Student.objects.all().order_by('-student_id').first()
                next_id = 1  # Default if no students exist
                
                if last_student:
                    next_id = last_student.student_id + 1
                
                Student.objects.create(
                    user=user,
                    student_id=next_id,
                    name=f"{user.first_name} {user.last_name}".strip() or user.username
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
        
    # Get all courses since there is no teacher field anymore
    courses = Course.objects.all()
    
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
        form = CourseForm(request.POST)
        
        if form.is_valid():
            # Create course and save directly since we don't need to set teacher anymore
            course = form.save()
            
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
        
    # Get the course without teacher check
    course = get_object_or_404(Course, id=course_id)
    
    # Get students enrolled in this course
    students = course.students.all()
    
    # Get grades
    student_grades = StudentGrade.objects.filter(course=course)
    
    # Get prediction models - updated to use EnhancedPredictionModel
    prediction_models = EnhancedPredictionModel.objects.filter(target_course=course)
    
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
        
    # Get active tab (level) from request
    active_tab = request.GET.get('tab', 'level1')
    active_level = int(active_tab.replace('level', ''))
    
    # Get all courses since there is no teacher field
    courses = Course.objects.all().order_by('level', 'name')
    
    # Group courses by level for easier template rendering
    course_levels = {}
    for course in courses:
        if course.level not in course_levels:
            course_levels[course.level] = []
        course_levels[course.level].append(course)
    
    # Filter courses based on active tab
    relevant_course_ids = [c.id for c in courses if c.level <= active_level]
    
    # Get only students from the currently active level
    students = Student.objects.filter(level=active_level).order_by('name')
    
    # Implement pagination for students
    page_number = request.GET.get('page', 1)
    items_per_page = 50  # Adjust based on your needs
    paginator = Paginator(students, items_per_page)
    page_obj = paginator.get_page(page_number)
    current_students = page_obj.object_list
    
    # If form is submitted, update grades - only where allowed based on student level
    if request.method == 'POST':
        updated_count = 0
        for student in current_students:
            for course in courses:
                # Skip courses that are higher level than student's level
                if course.level > student.level:
                    continue
                
                # For level 2 students, don't allow editing level 1 courses
                if student.level > course.level:
                    continue
                    
                grade_key = f"grade_{student.id}_{course.id}"
                
                grade_value = request.POST.get(grade_key, '').strip()
                
                # Only process if student is enrolled in this course
                if student.courses.filter(id=course.id).exists():
                    # If empty and grade doesn't exist, skip
                    if not grade_value:
                        continue
                        
                    # Create or update grade
                    student_grade, created = StudentGrade.objects.update_or_create(
                        student=student,
                        course=course,
                        defaults={
                            'grade': float(grade_value) if grade_value else None
                        }
                    )
                    
                    updated_count += 1
        
        messages.success(request, 'Grades updated successfully.')
        # The fix: Use redirect to the named URL, then append the query params
        return redirect(f'{reverse("student_grades")}?tab={active_tab}&page={page_number}')
    
    # Get all grades for the current students and relevant courses in a single query
    all_grades = StudentGrade.objects.filter(
        student__in=current_students,
        course__id__in=relevant_course_ids
    ).select_related('student', 'course')
    
    # Create a dictionary to store the grades for faster lookup
    grades_map = {}
    for grade in all_grades:
        if grade.student_id not in grades_map:
            grades_map[grade.student_id] = {}
        grades_map[grade.student_id][grade.course_id] = grade.grade
    
    # Prefetch course enrollments for the current students
    student_courses = {}
    for student in current_students:
        student_courses[student.id] = set(student.courses.values_list('id', flat=True))
    
    # Prepare data structures for template rendering
    grades_data = {}
    student_level_courses = {}
    
    for student in current_students:
        grades_data[student.id] = {}
        student_level_courses[student.id] = {}
        
        # Only process courses relevant to the student's level
        for course in [c for c in courses if c.level <= active_level]:
            # Check if student is enrolled
            is_enrolled = course.id in student_courses.get(student.id, set())
            
            # For level 2 students and level 1 courses: can view but not edit
            if student.level > course.level:
                can_edit = False
                can_view = True
            else:
                can_edit = is_enrolled
                can_view = is_enrolled
            
            student_level_courses[student.id][course.id] = {
                'enrolled': True,  # Always mark as enrolled to avoid "Not Enrolled" message
                'can_edit': can_edit,
                'can_view': can_view
            }
            
            # Get the grade from our preloaded map
            grades_data[student.id][course.id] = {
                'grade': grades_map.get(student.id, {}).get(course.id, None)
            }
    
    context = {
        'courses': courses,
        'course_levels': course_levels,
        'students': current_students,
        'grades_data': grades_data,
        'student_level_courses': student_level_courses,
        'active_tab': active_tab,
        'page_obj': page_obj,
    }
    
    return render(request, 'teacher/student_grades.html', context)

@login_required
def add_student_to_course(request, course_id):
    """Add a student to a course."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
            
    # Get the course without teacher check
    course = get_object_or_404(Course, id=course_id)
    
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
    
    # Get the course without teacher check
    course = get_object_or_404(Course, id=course_id)
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
        
    # Get the course without teacher check
    course = get_object_or_404(Course, id=course_id)
    
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
    
    # Get the course without teacher check
    course = get_object_or_404(Course, id=course_id)
    
    # Get available subjects (courses) for prediction
    teacher_courses = Course.objects.all()
    
    # Get courses with data
    courses_with_data = []
    for tcourse in teacher_courses:
        if StudentGrade.objects.filter(course=tcourse).exists():
            courses_with_data.append(tcourse)
    
    context = {
        'course': course,
        'courses': courses_with_data,
    }
    
    return render(request, 'prediction/create.html', context)

@login_required
def generate_predictions(request, course_id):
    """Create a prediction model and make predictions."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    # Get the course without teacher check
    course = get_object_or_404(Course, id=course_id)
    
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
        
    # Get the course without teacher check
    course = get_object_or_404(Course, id=course_id)
    
    # Get students enrolled in this course
    students = course.students.all()
    
    if request.method == 'POST':
        # Process form submission
        for student in students:
            grade_key = f"grade_{student.id}"
            
            grade_value = request.POST.get(grade_key, '').strip()
            
            if grade_value:
                # Create or update grade
                student_grade, created = StudentGrade.objects.get_or_create(
                    student=student,
                    course=course,
                    defaults={
                        'grade': float(grade_value) if grade_value else None
                    }
                )
                
                # Update existing grade
                if not created:
                    if grade_value:
                        student_grade.grade = float(grade_value)
                    student_grade.save()
        
        messages.success(request, 'Grades updated successfully.')
        return redirect('course_detail', course_id=course.id)
    
    # Prepare existing grades for display
    student_grades = {}
    for student in students:
        try:
            grade = StudentGrade.objects.get(student=student, course=course)
            student_grades[student.id] = {
                'grade': grade.grade
            }
        except StudentGrade.DoesNotExist:
            student_grades[student.id] = {
                'grade': None
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
    Modified to handle batch processing and avoid TooManyFieldsSent error.
    """
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to perform this action.')
        return redirect('dashboard')
    
    # Get the list of student IDs either from POST parameters or JSON body
    student_ids = []
    
    # Check if we're using the standard form approach (for small numbers of students)
    if 'student_ids' in request.POST:
        student_ids = request.POST.getlist('student_ids')
    # If we have a JSON payload instead (for bulk promotion)
    elif request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            student_ids = data.get('student_ids', [])
        except json.JSONDecodeError:
            messages.error(request, "Invalid JSON data received")
            return redirect('student_grades')
    
    if not student_ids:
        messages.warning(request, "No students were selected for promotion.")
        return redirect('student_grades')
    
    # Use the new bulk promotion method
    total_promoted = Student.bulk_progress_to_next_level(student_ids)
    
    if total_promoted > 0:
        messages.success(request, f"{total_promoted} students have been promoted to the next level.")
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
    
    # Calculate overall GPA and attendance rate
    all_grades = StudentGrade.objects.filter(student=student)
    grades_with_value = [g.grade for g in all_grades if g.grade is not None]
    overall_gpa = sum(grades_with_value) / len(grades_with_value) if grades_with_value else 0
    avg_attendance = 85  # Placeholder - implement actual attendance calculation
    avg_study_hours = 12  # Placeholder - implement actual study hours tracking
    
    course_data = []
    for course in courses:
        # Get grades for this course
        try:
            grade_obj = StudentGrade.objects.get(student=student, course=course)
            grade_value = grade_obj.grade
            
            # Structure for template that expects a grades list even though we only have a single grade
            grades = [{
                'get_grade_type_display': 'Final',  # Placeholder grade type
                'score': grade_value,
                'max_score': 100,
                'date': '-'  # Placeholder date
            }] if grade_value is not None else []
            
        except StudentGrade.DoesNotExist:
            grade_value = None
            grades = []
        
        # Add course data with structured grades for template
        course_data.append({
            'course': course,
            'grade': grade_value,
            'grades': grades,
            'attendance_rate': avg_attendance,  # Placeholder
        })
    
    # Get future courses (level 2 courses that the student is not enrolled in)
    future_courses = []
    if student.level == 1:  # Only show future courses for level 1 students
        # Get all level 2 courses
        level_2_courses = Course.objects.filter(level=2)
        # Filter out courses the student is already enrolled in
        enrolled_course_ids = courses.values_list('id', flat=True)
        future_course_objects = level_2_courses.exclude(id__in=enrolled_course_ids)
        
        # Create data structure for future courses
        for course in future_course_objects:
            # Get prediction data for this course if available
            prediction_data = None
            # Find any models that predict this course
            prediction_models = EnhancedPredictionModel.objects.filter(target_course=course)
            
            if prediction_models.exists():
                # Check if there are any predictions for this student with any of these models
                prediction = ModelPrediction.objects.filter(
                    model__in=prediction_models,
                    student=student
                ).order_by('-created_at').first()
                
                if prediction:
                    # Get feature importances for this prediction model
                    features = ModelFeature.objects.filter(
                        model=prediction.model
                    ).select_related('course').order_by('-importance')
                    
                    # Get current student performance in these courses
                    performance_data = []
                    recommendations = []
                    
                    if features.exists():
                        # Get top 3 most important features
                        top_features = features[:3]
                        
                        for feature in top_features:
                            # Only include features with importance values
                            if feature.importance is not None:
                                # Find student grade in this course
                                try:
                                    grade = StudentGrade.objects.get(student=student, course=feature.course)
                                    grade_value = grade.grade
                                except StudentGrade.DoesNotExist:
                                    grade_value = None
                                
                                # Add to performance data
                                performance_data.append({
                                    'course': feature.course,
                                    'importance': feature.importance,
                                    'grade': grade_value
                                })
                                
                                # Generate recommendation based on importance and grade
                                if grade_value is not None:
                                    if grade_value < 70 and feature.importance > 10:
                                        recommendations.append({
                                            'course': feature.course,
                                            'text': f"Improve your performance in {feature.course.name} as it's a critical foundation for success in {course.name}.",
                                            'importance': feature.importance
                                        })
                                    elif 70 <= grade_value < 85 and feature.importance > 15:
                                        recommendations.append({
                                            'course': feature.course,
                                            'text': f"Continue strengthening your skills in {feature.course.name} to excel in {course.name}.",
                                            'importance': feature.importance
                                        })
                                else:
                                    # Missing grade but important feature
                                    if feature.importance > 20:
                                        recommendations.append({
                                            'course': feature.course,
                                            'text': f"Complete {feature.course.name} with a strong grade as it's extremely important for {course.name}.",
                                            'importance': feature.importance
                                        })
                        
                        # Add a fallback recommendation if none were generated
                        if not recommendations and prediction.predicted_grade >= 70:
                            recommendations.append({
                                'course': None,
                                'text': f"You're on track for success in {course.name}. Continue your consistent performance in your current courses.",
                                'importance': None
                            })
                        elif not recommendations:
                            recommendations.append({
                                'course': None,
                                'text': f"Focus on building strong foundations in your current courses to improve your readiness for {course.name}.",
                                'importance': None
                            })
                    
                    prediction_data = {
                        'predicted_grade': prediction.predicted_grade,
                        'confidence': prediction.confidence,
                        'created_at': prediction.created_at,
                        'model': prediction.model,
                        'performance_data': performance_data,
                        'recommendations': recommendations
                    }
            
            future_courses.append({
                'course': course,
                'is_future': True,
                'prediction': prediction_data
            })
    
    context = {
        'student': student,
        'course_data': course_data,
        'future_courses': future_courses,
        'overall_gpa': overall_gpa,
        'avg_attendance': avg_attendance,
        'avg_study_hours': avg_study_hours
    }
    
    return render(request, 'student/dashboard.html', context)

@login_required
def create_attendance_courses_view(request):
    """
    Teacher view to manually create attendance courses.
    """
    if not hasattr(request.user, 'teacher'):
        messages.error(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
        
    from .signals import create_attendance_courses
    
    created = create_attendance_courses()
    
    if created:
        messages.success(request, 'Attendance courses have been created successfully!')
    else:
        messages.info(request, 'Attendance courses already exist or could not be created.')
        
    return redirect('teacher_dashboard')

@login_required
def add_student_to_level(request, level):
    """Add a student to a specific level and enroll them in all relevant courses."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
            
    if request.method == 'POST':
        action = request.POST.get('action', 'single_add')
        
        # Get the highest student ID currently in the database
        last_student = Student.objects.all().order_by('-student_id').first()
        next_id = 1  # Default if no students exist
        
        if last_student:
            next_id = last_student.student_id + 1
        
        # Handle bulk student creation
        if action == 'bulk_add':
            bulk_count = request.POST.get('bulk_count')
            
            if not bulk_count:
                messages.error(request, 'Please specify how many students to add.')
                return redirect('student_grades')
                
            try:
                count = int(bulk_count)
                if count < 1 or count > 5000:
                    messages.error(request, 'Bulk count must be between 1 and 5000.')
                    return redirect('student_grades')
                
                students_added = 0
                
                for i in range(count):
                    student_id = next_id + i
                    
                    # Create the student with a placeholder name
                    Student.objects.create(
                        student_id=student_id,
                        name=f"Student {student_id}",
                        level=level
                    )
                    students_added += 1
                
                messages.success(request, f'Added {students_added} new students to Level {level}.')
                
            except ValueError:
                messages.error(request, 'Invalid bulk count provided.')
                
        else:  # single_add
            student_name = request.POST.get('student_name')
            
            if not student_name:
                messages.error(request, 'Student name is required.')
                return redirect('student_grades')
            
            # Create new student with auto-generated ID
            student = Student.objects.create(
                student_id=next_id,
                name=student_name,
                level=level
            )
            # The signal ensure_student_course_enrollment will automatically 
            # enroll the student in all relevant courses
            
            messages.success(request, f'Student {student.name} added to Level {level} successfully.')
        
        # Redirect back to the student grades page with the tab parameter
        return redirect(f'{reverse("student_grades")}?tab=level{level}')
    
    # If not POST, redirect to student grades page
    return redirect('student_grades')

@login_required
def global_search_students(request):
    """AJAX endpoint to search for students globally (not tied to a specific course)."""
    if not hasattr(request.user, 'teacher'):
        return JsonResponse({'results': []})
    
    search_term = request.GET.get('term', '')

    if len(search_term) < 2:  # Require at least 2 characters
        return JsonResponse({'results': []})
    
    # Find all students matching the search term
    students = Student.objects.filter(
        Q(name__icontains=search_term) | 
        Q(student_id__icontains=search_term)
    )[:10]  # Limit results
    
    results = [{'id': student.id, 'text': f"{student.name} ({student.student_id})"} for student in students]
    return JsonResponse({'results': results})

@login_required
def upload_grades(request):
    """View for uploading grades in bulk via CSV file."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    # Get all courses for validation and display
    courses = Course.objects.all().order_by('level', 'name')
    
    if request.method == 'POST':
        form = GradeUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            
            # Check file type
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Please upload a CSV file.')
                return redirect('upload_grades')
            
            # Process the file
            try:
                # Read the file
                csv_data = csv_file.read().decode('utf-8')
                io_string = io.StringIO(csv_data)
                reader = csv.reader(io_string)
                
                # Extract header row (course codes)
                header = next(reader)
                if len(header) < 2:
                    messages.error(request, 'CSV file must have at least two columns: student ID and at least one grade.')
                    return redirect('upload_grades')
                
                # First column should be "student_id" or similar
                student_id_col = header[0].strip().lower()
                if not any(keyword in student_id_col for keyword in ['student', 'id']):
                    messages.warning(request, f'First column "{header[0]}" doesn\'t appear to be a student ID column, but proceeding anyway.')
                
                # Extract course codes from remaining columns while preserving order
                header_course_codes = [code.strip() for code in header[1:]]
                
                # Validate course codes
                course_objects = {}
                invalid_courses = []
                
                for code in header_course_codes:
                    try:
                        course = Course.objects.get(code=code)
                        course_objects[code] = course
                    except Course.DoesNotExist:
                        invalid_courses.append(code)
                
                if invalid_courses:
                    messages.error(request, f'Invalid course codes in CSV: {", ".join(invalid_courses)}')
                    return redirect('upload_grades')
                
                # Process grade rows
                grades_updated = 0
                students_not_found = []
                rows_processed = 0
                
                for row in reader:
                    rows_processed += 1
                    
                    if not row or len(row) == 0:
                        continue  # Skip empty rows
                    
                    # Get student ID from first column
                    try:
                        student_id = int(row[0].strip())
                    except (ValueError, IndexError):
                        messages.warning(request, f'Invalid student ID in row {rows_processed + 1}: {row[0] if row else "empty"}. Skipping this row.')
                        continue
                    
                    # Check if student exists
                    try:
                        student = Student.objects.get(student_id=student_id)
                    except Student.DoesNotExist:
                        students_not_found.append(student_id)
                        continue
                    
                    # Process grades for each course column
                    for col_index, course_code in enumerate(header_course_codes):
                        # Skip if index is out of range (row might be shorter than header)
                        if col_index + 1 >= len(row):
                            continue
                            
                        # Get grade value from the same column position
                        grade_value = row[col_index + 1].strip()
                        
                        # Skip empty grades
                        if not grade_value:
                            continue
                            
                        try:
                            # Convert to float
                            grade_float = float(grade_value)
                            
                            # Validate grade range
                            if grade_float < 0 or grade_float > 100:
                                messages.warning(request, f'Invalid grade value {grade_float} for student {student_id} in course {course_code}. Grades must be between 0 and 100.')
                                continue
                                
                            # Get course object from our map
                            course = course_objects.get(course_code)
                            
                            # Create or update grade
                            student_grade, created = StudentGrade.objects.update_or_create(
                                student=student,
                                course=course,
                                defaults={'grade': grade_float}
                            )
                            
                            grades_updated += 1
                            
                        except ValueError:
                            messages.warning(request, f'Invalid grade format for student {student_id} in course {course_code}: {grade_value}')
                
                # Generate appropriate messages
                if grades_updated > 0:
                    messages.success(request, f'Successfully updated {grades_updated} grades from {rows_processed} rows.')
                else:
                    messages.warning(request, 'No grades were updated. Please check the CSV format and try again.')
                    
                if students_not_found:
                    if len(students_not_found) <= 5:
                        messages.warning(request, f'The following student IDs were not found: {", ".join(map(str, students_not_found))}')
                    else:
                        messages.warning(request, f'{len(students_not_found)} student IDs were not found in the system.')
                
                return redirect('student_grades')
                
            except Exception as e:
                messages.error(request, f'Error processing CSV file: {str(e)}')
                return redirect('upload_grades')
    else:
        form = GradeUploadForm()
    
    context = {
        'form': form,
        'courses': courses
    }
    
    return render(request, 'teacher/upload_grades.html', context)

@login_required
def download_grades_template(request):
    """Generate and download a CSV template for grades."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this feature.')
        return redirect('dashboard')
    
    # Get all courses for the template
    courses = Course.objects.all().order_by('level', 'code')
    
    # Create a response object with CSV content
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="grades_template.csv"'
    
    # Create CSV writer
    writer = csv.writer(response)
    
    # Write header row with course codes
    header = ['student_id']
    for course in courses:
        header.append(course.code)
    writer.writerow(header)
    
    # Get some student IDs for example rows
    students = Student.objects.all()[:3]
    if students:
        # Write data rows for existing students
        for student in students:
            row = [student.student_id]
            for course in courses:
                # Use existing grade or empty value
                try:
                    grade = StudentGrade.objects.get(student=student, course=course)
                    row.append(grade.grade if grade.grade is not None else '')
                except StudentGrade.DoesNotExist:
                    row.append('')
            writer.writerow(row)
    else:
        # Use placeholder student IDs if no students exist
        for i in range(1, 4):
            row = [i]
            for _ in courses:
                # Add sample grades (empty for one column to show that empty values are accepted)
                if i == 2 and _ == 1:
                    row.append('')
                else:
                    # Random grade between 60 and 95
                    import random
                    row.append(random.randint(60, 95))
            writer.writerow(row)
    
    return response

@login_required
def restore_database_backup(request):
    """Restore the database from a backup file."""
    if not hasattr(request.user, 'teacher'):
        messages.error(request, 'You need to be a teacher to perform this action.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        # Define backup folder path
        backup_folder = os.path.join(settings.BASE_DIR, 'backup')
        backup_db_path = os.path.join(backup_folder, 'db.sqlite3')
        
        # Check if backup exists
        if not os.path.exists(backup_db_path):
            messages.error(request, 'No backup database found. Please ensure a backup exists in the backup folder.')
            return redirect('teacher_dashboard')
            
        try:
            # Get the current database path from settings
            db_path = settings.DATABASES['default']['NAME']
            
            # Create a temporary backup of the current database just in case
            temp_backup_path = os.path.join(settings.BASE_DIR, 'db_temp_backup.sqlite3')
            shutil.copy2(db_path, temp_backup_path)
            
            # Copy the backup database to replace the current one
            shutil.copy2(backup_db_path, db_path)
            
            messages.success(request, 'Database has been successfully restored from backup!')
            
            # Set a flag to restart the server after the response has been sent
            restart_server = True
            
            # Return the response first
            response = redirect('teacher_dashboard')
            
            # Use a separate thread to restart the server after the response is sent
            import threading
            import sys
            import subprocess
            
            def restart_django_server():
                # Wait a moment for the response to be sent
                import time
                time.sleep(2)
                
                # Get the current script name (manage.py)
                script = sys.argv[0]
                
                # Get the current working directory
                cwd = os.getcwd()
                
                # Check if we're in a virtual environment
                if 'VIRTUAL_ENV' in os.environ:
                    # Use the virtual environment's Python interpreter
                    python_executable = os.path.join(os.environ['VIRTUAL_ENV'], 'Scripts', 'python.exe')
                    
                    # On Linux/Mac the path might be different
                    if not os.path.exists(python_executable):
                        python_executable = os.path.join(os.environ['VIRTUAL_ENV'], 'bin', 'python')
                else:
                    # Try to detect virtual environment
                    venv_dir = os.path.join(settings.BASE_DIR, 'venv')
                    if os.path.exists(venv_dir):
                        if os.path.exists(os.path.join(venv_dir, 'Scripts', 'python.exe')):
                            # Windows
                            python_executable = os.path.join(venv_dir, 'Scripts', 'python.exe')
                        else:
                            # Linux/Mac
                            python_executable = os.path.join(venv_dir, 'bin', 'python')
                    else:
                        # Fallback to system Python (likely won't work if Django is in a venv)
                        python_executable = sys.executable
                
                # Restart the server using subprocess
                # This will kill the current process and start a new one
                subprocess.Popen([python_executable, script, 'runserver'], cwd=cwd)
                
                # Force exit the current process
                sys.exit(0)
            
            if restart_server:
                # Start a thread that will restart the server
                threading.Thread(target=restart_django_server).start()
                
            return response
            
        except Exception as e:
            # If something goes wrong, try to restore from the temporary backup
            if os.path.exists(temp_backup_path):
                try:
                    shutil.copy2(temp_backup_path, db_path)
                    messages.error(request, f'Error restoring database: {str(e)}. Original database has been preserved.')
                except:
                    messages.error(request, f'Critical error: Failed to restore database AND failed to restore original. Error: {str(e)}')
            else:
                messages.error(request, f'Error restoring database: {str(e)}')
        finally:
            # Clean up the temporary backup
            if os.path.exists(temp_backup_path):
                os.remove(temp_backup_path)
    
    return redirect('teacher_dashboard')