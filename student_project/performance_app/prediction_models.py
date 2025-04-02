from django.db import models
from django.contrib.auth.models import User
from .models import Course, Student, StudentGrade

class EnhancedPredictionModel(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    target_course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='target_for_models')
    
    # Model configuration
    algorithm = models.CharField(max_length=50, default='GradientBoosting')
    train_test_split = models.FloatField(default=0.2)  # 20% test data by default
    
    # Model performance metrics
    r_squared = models.FloatField(null=True, blank=True)
    rmse = models.FloatField(null=True, blank=True)
    mae = models.FloatField(null=True, blank=True)
    mape = models.FloatField(null=True, blank=True)
    
    # Serialized model file
    model_file = models.FileField(upload_to='prediction_models/', null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} - Predicting {self.target_course.code}"
        
    class Meta:
        ordering = ['-created_at']

class ModelFeature(models.Model):
    model = models.ForeignKey(EnhancedPredictionModel, on_delete=models.CASCADE, related_name='features')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    importance = models.FloatField(null=True, blank=True)  # Will be populated after training
    
    def __str__(self):
        return f"{self.model.name} - Feature: {self.course.code}"
        
    class Meta:
        unique_together = ('model', 'course')

class ModelTrainingData(models.Model):
    model = models.ForeignKey(EnhancedPredictionModel, on_delete=models.CASCADE, related_name='training_data')
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    included_in_training = models.BooleanField(default=True)  # Flag for train/test split
    
    def __str__(self):
        return f"Training data for {self.model.name} - Student: {self.student.name}"
        
    class Meta:
        unique_together = ('model', 'student')

class ModelTestPrediction(models.Model):
    """Stores test set prediction results during model training for evaluation purposes"""
    model = models.ForeignKey(EnhancedPredictionModel, on_delete=models.CASCADE, related_name='test_predictions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True)  # Optional link to student
    actual_grade = models.FloatField()
    predicted_grade = models.FloatField()
    absolute_error = models.FloatField()  # |actual - predicted|
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        if self.student:
            return f"Test prediction for {self.student.name} in {self.model.target_course.code}"
        return f"Test prediction for {self.model.target_course.code}"
    
    class Meta:
        ordering = ['-created_at']

class ModelPrediction(models.Model):
    model = models.ForeignKey(EnhancedPredictionModel, on_delete=models.CASCADE, related_name='predictions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    predicted_grade = models.FloatField()
    actual_grade = models.FloatField(null=True, blank=True)  # Can be filled in later
    confidence = models.FloatField(null=True, blank=True)  # Prediction confidence (0-1)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Prediction for {self.student.name} in {self.model.target_course.code}"
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ('model', 'student')  # Ensure only one prediction per student per model 