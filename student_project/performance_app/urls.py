from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import prediction_views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    # Basic pages
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    
    # Authentication
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='logout.html'), name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    
    # Course management
    path('add-course/', views.add_course, name='add_course'),
    path('course/<int:course_id>/input-grades/', views.course_grades, name='input_grades'),
    path('course/<int:course_id>/', views.course_detail, name='course_detail'),
    path('course/<int:course_id>/create-model/', views.create_model_page, name='create_model_page'),
    path('course/<int:course_id>/generate-predictions/', views.generate_predictions, name='generate_predictions'),
    
    # Teacher actions
    path('teacher/create-attendance-courses/', views.create_attendance_courses_view, name='create_attendance_courses'),
    
    # Student management
    path('course/<int:course_id>/add-student/', views.add_student_to_course, name='add_student_to_course'),
    path('course/<int:course_id>/remove-student/<int:student_id>/', views.remove_student_from_course, name='remove_student_from_course'),
    path('course/<int:course_id>/search-students/', views.search_students, name='search_students'),
    path('student-grades/', views.student_grades, name='student_grades'),
    path('students/promote-selected/', views.promote_selected_students, name='promote_selected_students'),
    path('students/add-to-level/<int:level>/', views.add_student_to_level, name='add_student_to_level'),
    path('upload-grades/', views.upload_grades, name='upload_grades'),
    path('download-grades-template/', views.download_grades_template, name='download_grades_template'),
    
    # Enhanced Prediction Models
    path('prediction/models/', prediction_views.list_models, name='prediction_models'),
    path('prediction/create/', prediction_views.create_model, name='create_model'),
    path('prediction/<int:model_id>/data/', prediction_views.data_selection, name='data_selection'),
    path('prediction/<int:model_id>/train/', prediction_views.train_model, name='train_model'),
    path('prediction/<int:model_id>/', prediction_views.model_detail, name='model_detail'),
    path('prediction/<int:model_id>/edit/', prediction_views.edit_model, name='edit_model'),
    path('prediction/<int:model_id>/retrain/', prediction_views.retrain_model, name='retrain_model'),
    path('prediction/<int:model_id>/delete/', prediction_views.delete_model, name='delete_model'),
    path('prediction/<int:model_id>/predict/', prediction_views.predict_form, name='predict_form'),
    path('prediction/<int:model_id>/make-prediction/', prediction_views.make_prediction, name='make_prediction'),
    path('prediction/<int:model_id>/prediction/<int:prediction_id>/', prediction_views.single_prediction, name='single_prediction'),
    path('prediction/<int:model_id>/history/', prediction_views.prediction_history, name='prediction_history'),
]