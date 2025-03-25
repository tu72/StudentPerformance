from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import *

class UserRegistrationForm(UserCreationForm):
    """Form for user registration with additional fields for student/teacher profiles."""
    email = forms.EmailField()
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    ]
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect)
    
    # Only keeping the student ID field, removing department
    id_number = forms.CharField(max_length=20, required=False, help_text='Required for students')
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'role', 'id_number']
    
    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        id_number = cleaned_data.get('id_number')
        
        if role == 'student' and not id_number:
            self.add_error('id_number', 'Student ID is required for student accounts.')
        
        return cleaned_data

class CourseForm(forms.ModelForm):
    """Form for creating and updating courses."""
    class Meta:
        model = Course
        fields = ['name', 'code', 'level']
        
    def clean_code(self):
        code = self.cleaned_data.get('code')
        
        # Check if course with this code already exists
        if Course.objects.filter(code=code).exists() and not self.instance.pk:
            raise forms.ValidationError("A course with this code already exists. Please use a different code.")
        
        return code

class GradeUploadForm(forms.Form):
    csv_file = forms.FileField(
        label='Select a CSV file',
        help_text='CSV file must have student IDs in the first column and course codes in the header row.'
    )