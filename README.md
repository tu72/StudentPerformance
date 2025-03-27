# Student Performance Prediction App

A Django web application for tracking student performance across courses and predicting future performance using machine learning.

## Features

- **Student Management**: Add, edit, and view student information
- **Course Management**: Create courses and manage enrollments
- **Grade Tracking**: Input and visualize student grades
- **Performance Prediction**: Build custom prediction models to forecast student performance

## Enhanced Prediction Models

The application includes an advanced machine learning system for creating customized prediction models:

1. **Create Model**: Select features (input courses), target (output course), and algorithm
2. **Data Selection**: Choose which students to include in the training dataset
3. **Model Training**: Train the model and view performance metrics
4. **Make Predictions**: Predict individual or batch student performance
5. **View Results**: Visualize prediction results and identify at-risk students

## Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Apply migrations:
   ```
   python manage.py migrate
   ```
4. Run the development server:
   ```
   python manage.py runserver
   ```

## Technical Details

- **Framework**: Django 4.2
- **Machine Learning**: scikit-learn
- **Supported Algorithms**:
  - Linear Regression
  - Gradient Boosting
  - Random Forest
  - Support Vector Regression 