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
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'role']
    
    def clean(self):
        cleaned_data = super().clean()
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