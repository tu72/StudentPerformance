from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
import numpy as np
import os
import json
import pickle
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.svm import SVR
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sklearn.model_selection import train_test_split
from django.conf import settings
from .models import Course, Student, StudentGrade
from .prediction_models import EnhancedPredictionModel, ModelFeature, ModelTrainingData, ModelPrediction
import math
import random

# Utility function to get the appropriate model class
def get_model_class(algorithm):
    if algorithm == 'LinearRegression':
        return LinearRegression()
    elif algorithm == 'GradientBoostingRegressor':
        return GradientBoostingRegressor()
    elif algorithm == 'RandomForest':
        return RandomForestRegressor()
    elif algorithm == 'SupportVectorRegression':
        return SVR()
    else:
        # Default to gradient boosting
        return GradientBoostingRegressor()

@login_required
def create_model(request):
    """Create a new prediction model."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        # Extract form data
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        course_id = request.POST.get('course_id')
        target_course_id = request.POST.get('target_course')
        feature_course_ids = request.POST.getlist('feature_courses')
        algorithm = request.POST.get('algorithm', 'GradientBoosting')
        train_test_split_value = float(request.POST.get('train_test_split', 20)) / 100  # Convert percentage to fraction
        
        # Basic validation
        if not all([name, target_course_id, feature_course_ids]):
            messages.error(request, 'Please provide a name, target course, and at least one feature course.')
            return redirect('create_model_page', course_id=course_id)
            
        # Create model
        model = EnhancedPredictionModel.objects.create(
            name=name,
            description=description,
            creator=request.user,
            target_course_id=target_course_id,
            algorithm=algorithm,
            train_test_split=train_test_split_value
        )
        
        # Create feature relationships
        for feature_id in feature_course_ids:
            ModelFeature.objects.create(
                model=model,
                course_id=feature_id
            )
        
        messages.success(request, f'Model "{name}" created. Now select the training data.')
        return redirect('data_selection', model_id=model.id)
    
    # GET request means we were called directly - redirect to course page
    return redirect('teacher_dashboard')

@login_required
def data_selection(request, model_id):
    """Select students for training the model."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    model = get_object_or_404(EnhancedPredictionModel, id=model_id)
    
    # Get all courses involved (target + features)
    all_courses = [model.target_course] + list(Course.objects.filter(
        id__in=model.features.values_list('course_id', flat=True)
    ))
    
    # Find students with grades for all these courses
    eligible_students = []
    all_students = Student.objects.all()
    
    for student in all_students:
        # Check if student has grades for all required courses
        student_grades = StudentGrade.objects.filter(student=student, course__in=all_courses)
        
        if student_grades.count() == len(all_courses):
            # Check if all grades are not None
            if all(grade.grade is not None for grade in student_grades):
                # Get target grade for display
                try:
                    target_grade = StudentGrade.objects.get(
                        student=student, course=model.target_course
                    ).grade
                except StudentGrade.DoesNotExist:
                    target_grade = None
                
                # Calculate data completeness score (100% if all required data exists)
                data_completeness = 100
                
                student.target_grade = target_grade
                student.data_completeness = data_completeness
                eligible_students.append(student)
    
    context = {
        'model': model,
        'eligible_students': eligible_students,
    }
    
    return render(request, 'prediction/data_selection.html', context)

@login_required
def train_model(request, model_id):
    """Train the model with selected students."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    model = get_object_or_404(EnhancedPredictionModel, id=model_id)
    
    if request.method == 'POST':
        # Get selected students
        selected_student_ids = request.POST.getlist('selected_students')
        
        if not selected_student_ids:
            messages.error(request, 'Please select at least one student for training.')
            return redirect('data_selection', model_id=model.id)
        
        # Clear any existing training data
        ModelTrainingData.objects.filter(model=model).delete()
        
        # Create training data entries
        for student_id in selected_student_ids:
            ModelTrainingData.objects.create(
                model=model,
                student_id=student_id
            )
        
        # Simulate training immediately (in a real app, this would be a background task)
        train_model_algorithm(model)
        
        messages.success(request, f'Model "{model.name}" has been trained successfully.')
        return redirect('model_detail', model_id=model.id)
    
    # Prepare data for the view
    training_count = ModelTrainingData.objects.filter(model=model).count()
    
    context = {
        'model': model,
        'training_count': training_count
    }
    
    return render(request, 'prediction/train.html', context)

def train_model_algorithm(model):
    """Perform the actual model training."""
    # Get all the training data
    training_data = ModelTrainingData.objects.filter(model=model)
    student_ids = training_data.values_list('student_id', flat=True)
    
    # Get features and target
    feature_courses = Course.objects.filter(
        id__in=model.features.values_list('course_id', flat=True)
    )
    target_course = model.target_course
    
    # Prepare data arrays
    X = []  # Feature values
    y = []  # Target values
    
    for student_id in student_ids:
        student = Student.objects.get(id=student_id)
        # Get features
        feature_values = []
        for course in feature_courses:
            try:
                grade = StudentGrade.objects.get(student=student, course=course).grade
                feature_values.append(grade)
            except (StudentGrade.DoesNotExist, AttributeError):
                # Skip this student if any data is missing
                continue
        
        # Get target
        try:
            target_grade = StudentGrade.objects.get(student=student, course=target_course).grade
            if target_grade is None:
                continue
        except (StudentGrade.DoesNotExist, AttributeError):
            continue
        
        X.append(feature_values)
        y.append(target_grade)
    
    # Make sure we have enough data
    if len(X) < 5:
        model.r_squared = 0
        model.rmse = 0
        model.mae = 0
        model.save()
        return
    
    # Split into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=model.train_test_split, random_state=42
    )
    
    # Convert to numpy arrays
    X_train = np.array(X_train)
    X_test = np.array(X_test)
    y_train = np.array(y_train)
    y_test = np.array(y_test)
    
    # Get the right model algorithm
    algorithm = get_model_class(model.algorithm)
    
    # Train the model
    algorithm.fit(X_train, y_train)
    
    # Make predictions on test set
    y_pred = algorithm.predict(X_test)
    
    # Calculate metrics
    r2 = r2_score(y_test, y_pred)
    rmse = math.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    
    # Update model with metrics
    model.r_squared = r2
    model.rmse = rmse
    model.mae = mae
    model.save()
    
    # Save the trained model to a file
    model_dir = os.path.join(settings.MEDIA_ROOT, 'prediction_models')
    os.makedirs(model_dir, exist_ok=True)
    
    model_filename = f"enhanced_model_{model.id}.pkl"
    model_path = os.path.join(model_dir, model_filename)
    
    with open(model_path, 'wb') as f:
        pickle.dump(algorithm, f)
    
    # Update the model file path
    model.model_file = f"prediction_models/{model_filename}"
    model.save()
    
    # Update feature importance (for applicable algorithms)
    if hasattr(algorithm, 'feature_importances_'):
        importances = algorithm.feature_importances_
        
        # Normalize to percentages
        if sum(importances) > 0:
            importances = [100 * (imp / sum(importances)) for imp in importances]
            
            # Update feature importance values
            for i, feature in enumerate(model.features.all()):
                if i < len(importances):
                    feature.importance = importances[i]
                    feature.save()

@login_required
def model_detail(request, model_id):
    """Display model details and metrics."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    model = get_object_or_404(EnhancedPredictionModel, id=model_id)
    
    # Get recent predictions
    predictions = ModelPrediction.objects.filter(model=model).order_by('-created_at')[:5]
    
    # Generate random test data for the scatter plot (in a real app, this would be real test data)
    test_predictions = []
    for i in range(10):
        actual = random.uniform(50, 95)
        error = random.uniform(-15, 15)
        predicted = max(0, min(100, actual + error))
        
        test_predictions.append({
            'actual_grade': actual,
            'predicted_grade': predicted
        })
    
    context = {
        'model': model,
        'predictions': predictions,
        'test_predictions': test_predictions
    }
    
    return render(request, 'prediction/model_detail.html', context)

@login_required
def edit_model(request, model_id):
    """Edit an existing model's parameters."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    model = get_object_or_404(EnhancedPredictionModel, id=model_id)
    
    # For now, redirect back to model detail with a message
    messages.info(request, 'Model editing is not yet implemented.')
    return redirect('model_detail', model_id=model.id)

@login_required
def retrain_model(request, model_id):
    """Retrain an existing model with the same parameters."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    model = get_object_or_404(EnhancedPredictionModel, id=model_id)
    
    # Retrain the model
    train_model_algorithm(model)
    
    messages.success(request, f'Model "{model.name}" has been retrained successfully.')
    return redirect('model_detail', model_id=model.id)

@login_required
def delete_model(request, model_id):
    """Delete a prediction model."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    model = get_object_or_404(EnhancedPredictionModel, id=model_id)
    
    if request.method == 'POST':
        model_name = model.name
        model.delete()
        messages.success(request, f'Model "{model_name}" has been deleted.')
        return redirect('teacher_dashboard')
    
    # GET requests should go to the model detail page
    return redirect('model_detail', model_id=model.id)

@login_required
def predict_form(request, model_id):
    """Show form for making predictions."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    model = get_object_or_404(EnhancedPredictionModel, id=model_id)
    
    # Get all students
    students = Student.objects.all().order_by('name')
    
    context = {
        'model': model,
        'students': students
    }
    
    return render(request, 'prediction/predict_form.html', context)

@login_required
def make_prediction(request, model_id):
    """Process prediction form and generate predictions."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    model = get_object_or_404(EnhancedPredictionModel, id=model_id)
    
    if request.method == 'POST':
        prediction_type = request.POST.get('prediction_type', 'single')
        
        # Get model algorithm from file
        model_path = os.path.join(settings.MEDIA_ROOT, model.model_file.name)
        try:
            with open(model_path, 'rb') as f:
                algorithm = pickle.load(f)
        except (FileNotFoundError, IOError):
            messages.error(request, 'Error loading the prediction model. Please retrain the model.')
            return redirect('predict_form', model_id=model.id)
        
        # Get feature courses
        feature_courses = Course.objects.filter(
            id__in=model.features.values_list('course_id', flat=True)
        )
        
        if prediction_type == 'single':
            # Get student
            student_id = request.POST.get('student_id')
            if not student_id:
                messages.error(request, 'Please select a student.')
                return redirect('predict_form', model_id=model.id)
            
            student = get_object_or_404(Student, id=student_id)
            
            # Get feature values
            feature_values = []
            features_data = []
            
            for feature in model.features.all():
                feature_id = feature.id
                course = feature.course
                
                # Check if there's a manual override
                manual_value = request.POST.get(f'feature_{feature_id}', '').strip()
                
                if manual_value:
                    # Use the manual value
                    grade_value = float(manual_value)
                else:
                    # Try to get the existing grade
                    try:
                        grade = StudentGrade.objects.get(student=student, course=course)
                        grade_value = grade.grade
                    except StudentGrade.DoesNotExist:
                        grade_value = None
                
                if grade_value is not None:
                    feature_values.append(grade_value)
                    features_data.append({
                        'course': course,
                        'grade': grade_value,
                        'importance': feature.importance or 0
                    })
                else:
                    # Missing data - redirect back to form with error
                    messages.error(request, 
                                  f'Missing grade data for {course.name}. Please provide a value or select a different student.')
                    return redirect('predict_form', model_id=model.id)
            
            # Make the prediction
            try:
                prediction_value = algorithm.predict([feature_values])[0]
                
                # Ensure prediction is within valid range
                prediction_value = max(0, min(100, prediction_value))
                
                # Calculate confidence based on model metrics and data completeness
                # Higher R-squared and lower RMSE mean more confidence
                r_squared_factor = model.r_squared if model.r_squared is not None else 0
                rmse_factor = min(1, model.rmse / 100) if model.rmse is not None else 1
                
                # Calculate confidence score (0-1)
                # Simple formula: (r_squared - normalized_rmse) / 2 + 0.5 to center around 0.5
                confidence_score = ((r_squared_factor - rmse_factor) / 2) + 0.5
                
                # Ensure confidence is within 0-1 range
                confidence_score = max(0, min(1, confidence_score))
                
                # Save the prediction with confidence
                prediction = ModelPrediction.objects.create(
                    model=model,
                    student=student,
                    predicted_grade=prediction_value,
                    confidence=confidence_score
                )
                
                # Redirect to single prediction result
                context = {
                    'model': model,
                    'prediction': prediction,
                    'features': features_data,
                    'is_single_prediction': True
                }
                
                return render(request, 'prediction/prediction_results.html', context)
                
            except Exception as e:
                messages.error(request, f'Error making prediction: {str(e)}')
                return redirect('predict_form', model_id=model.id)
                
        elif prediction_type == 'batch':
            # Get selected students
            student_ids = request.POST.getlist('student_ids')
            
            if not student_ids:
                messages.error(request, 'Please select at least one student for batch prediction.')
                return redirect('predict_form', model_id=model.id)
            
            students = Student.objects.filter(id__in=student_ids)
            predictions = []
            skipped_students = []
            
            for student in students:
                # Get feature values for this student
                feature_values = []
                has_all_features = True
                
                for feature in model.features.all():
                    course = feature.course
                    
                    try:
                        grade = StudentGrade.objects.get(student=student, course=course)
                        if grade.grade is not None:
                            feature_values.append(grade.grade)
                        else:
                            has_all_features = False
                            break
                    except StudentGrade.DoesNotExist:
                        has_all_features = False
                        break
                
                if has_all_features:
                    # Make prediction
                    try:
                        prediction_value = algorithm.predict([feature_values])[0]
                        
                        # Ensure prediction is within valid range
                        prediction_value = max(0, min(100, prediction_value))
                        
                        # Calculate confidence (same formula as above)
                        r_squared_factor = model.r_squared if model.r_squared is not None else 0
                        rmse_factor = min(1, model.rmse / 100) if model.rmse is not None else 1
                        confidence_score = ((r_squared_factor - rmse_factor) / 2) + 0.5
                        confidence_score = max(0, min(1, confidence_score))
                        
                        # Save prediction
                        prediction = ModelPrediction.objects.create(
                            model=model,
                            student=student,
                            predicted_grade=prediction_value,
                            confidence=confidence_score
                        )
                        
                        predictions.append(prediction)
                        
                    except Exception as e:
                        skipped_students.append(student.name)
                else:
                    skipped_students.append(student.name)
            
            if skipped_students:
                if len(skipped_students) <= 5:
                    messages.warning(request, 
                                    f'Skipped predictions for {", ".join(skipped_students)} due to missing data.')
                else:
                    messages.warning(request, 
                                   f'Skipped predictions for {len(skipped_students)} students due to missing data.')
            
            if not predictions:
                messages.error(request, 'Could not make predictions for any of the selected students due to missing data.')
                return redirect('predict_form', model_id=model.id)
            
            # Count predictions by status
            passing_count = sum(1 for p in predictions if p.predicted_grade >= 70)
            at_risk_count = sum(1 for p in predictions if 50 <= p.predicted_grade < 70)
            failing_count = sum(1 for p in predictions if p.predicted_grade < 50)
            
            context = {
                'model': model,
                'predictions': predictions,
                'is_single_prediction': False,
                'passing_count': passing_count,
                'at_risk_count': at_risk_count,
                'failing_count': failing_count
            }
            
            return render(request, 'prediction/prediction_results.html', context)
    
    # GET request, redirect to form
    return redirect('predict_form', model_id=model.id)

@login_required
def single_prediction(request, model_id, prediction_id):
    """View details for a single prediction."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    model = get_object_or_404(EnhancedPredictionModel, id=model_id)
    prediction = get_object_or_404(ModelPrediction, id=prediction_id, model=model)
    
    # Collect feature data (simplified version)
    features = []
    for feature in model.features.all():
        try:
            grade = StudentGrade.objects.get(student=prediction.student, course=feature.course)
            grade_value = grade.grade
        except StudentGrade.DoesNotExist:
            grade_value = None
            
        features.append({
            'course': feature.course,
            'grade': grade_value,
            'importance': feature.importance or 0
        })
    
    context = {
        'model': model,
        'prediction': prediction,
        'features': features,
        'is_single_prediction': True
    }
    
    return render(request, 'prediction/prediction_results.html', context)

@login_required
def prediction_history(request, model_id):
    """View prediction history for a model."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    model = get_object_or_404(EnhancedPredictionModel, id=model_id)
    predictions = ModelPrediction.objects.filter(model=model).order_by('-created_at')
    
    # For now, redirect to model detail with a message
    messages.info(request, 'Full prediction history view is not yet implemented.')
    return redirect('model_detail', model_id=model.id)

@login_required
def list_models(request):
    """List all prediction models."""
    if not hasattr(request.user, 'teacher'):
        messages.warning(request, 'You need to be a teacher to access this page.')
        return redirect('dashboard')
    
    # Get all models with their related data
    models = EnhancedPredictionModel.objects.select_related('target_course').prefetch_related('features__course').all()
    
    context = {
        'models': models,
    }
    
    return render(request, 'prediction/models_list.html', context) 