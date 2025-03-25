from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path
from django.utils.html import format_html
from .models import Teacher, Student, Course, StudentGrade, PredictionModel, Prediction
from .signals import create_attendance_courses

# Create an admin action to create attendance courses
def create_attendance_courses_action(modeladmin, request, queryset):
    created = create_attendance_courses()
    if created:
        modeladmin.message_user(request, "Attendance courses created successfully!")
    else:
        modeladmin.message_user(request, "No new attendance courses needed to be created.")

create_attendance_courses_action.short_description = "Create attendance courses for all levels"

# Custom Course admin with attendance courses creation action
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'level')
    list_filter = ('level',)
    search_fields = ('name', 'code')
    actions = [create_attendance_courses_action]
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('create-attendance-courses/', 
                 self.admin_site.admin_view(self.create_attendance_courses_view),
                 name='create_attendance_courses')
        ]
        return custom_urls + urls
    
    def create_attendance_courses_view(self, request):
        """Admin view to create attendance courses"""
        created = create_attendance_courses()
        if created:
            self.message_user(request, "Attendance courses created successfully!")
        else:
            self.message_user(request, "No new attendance courses needed to be created.")
        return HttpResponseRedirect("../")
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_attendance_button'] = True
        return super().changelist_view(request, extra_context=extra_context)

# Register with the default admin site
admin.site.register(Teacher)
admin.site.register(Student)
admin.site.register(Course, CourseAdmin)
admin.site.register(StudentGrade)
admin.site.register(PredictionModel)
admin.site.register(Prediction)
