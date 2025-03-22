// Custom JavaScript for Student Performance Prediction System

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Feather icons
    if (typeof feather !== 'undefined') {
        feather.replace();
    }
    
    // Initialize tooltips if Bootstrap is available
    if (typeof bootstrap !== 'undefined') {
        var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // Form validation enhancement
    const forms = document.querySelectorAll('.needs-validation');
    
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            
            form.classList.add('was-validated');
        }, false);
    });
    
    // Show/hide student/teacher specific fields in registration form
    const roleInputs = document.querySelectorAll('input[name="role"]');
    const studentFields = document.getElementById('student-fields');
    const teacherFields = document.getElementById('teacher-fields');
    
    if (roleInputs.length > 0 && studentFields && teacherFields) {
        roleInputs.forEach(input => {
            input.addEventListener('change', function() {
                if (this.value === 'student') {
                    studentFields.style.display = 'block';
                    teacherFields.style.display = 'none';
                } else if (this.value === 'teacher') {
                    studentFields.style.display = 'none';
                    teacherFields.style.display = 'block';
                }
            });
            
            // Initialize based on default selection
            if (input.checked) {
                if (input.value === 'student') {
                    studentFields.style.display = 'block';
                    teacherFields.style.display = 'none';
                } else if (input.value === 'teacher') {
                    studentFields.style.display = 'none';
                    teacherFields.style.display = 'block';
                }
            }
        });
    }
    
    // Add auto-dismiss to alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
    
    // Create charts if Chart.js is available and there are chart containers
    if (typeof Chart !== 'undefined') {
        // Performance trend chart
        const performanceCtx = document.getElementById('performanceTrendChart');
        if (performanceCtx) {
            new Chart(performanceCtx, {
                type: 'line',
                data: {
                    labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6'],
                    datasets: [{
                        label: 'Actual Performance',
                        data: [65, 70, 68, 72, 75, 78],
                        borderColor: 'rgb(75, 192, 192)',
                        tension: 0.1,
                        fill: false
                    },
                    {
                        label: 'Predicted Performance',
                        data: [64, 68, 70, 73, 76, 80],
                        borderColor: 'rgb(255, 159, 64)',
                        borderDash: [5, 5],
                        tension: 0.1,
                        fill: false
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100
                        }
                    }
                }
            });
        }
        
        // Attendance chart
        const attendanceCtx = document.getElementById('attendanceChart');
        if (attendanceCtx) {
            new Chart(attendanceCtx, {
                type: 'bar',
                data: {
                    labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6'],
                    datasets: [{
                        label: 'Attendance Rate (%)',
                        data: [90, 85, 100, 80, 95, 100],
                        backgroundColor: 'rgba(54, 162, 235, 0.5)',
                        borderColor: 'rgb(54, 162, 235)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100
                        }
                    }
                }
            });
        }
        
        // Study habits chart
        const studyHabitsCtx = document.getElementById('studyHabitsChart');
        if (studyHabitsCtx) {
            new Chart(studyHabitsCtx, {
                type: 'bar',
                data: {
                    labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                    datasets: [{
                        label: 'Study Hours',
                        data: [2, 3, 1.5, 2.5, 1, 4, 3],
                        backgroundColor: 'rgba(153, 102, 255, 0.5)',
                        borderColor: 'rgb(153, 102, 255)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }
    }
});

// Function to confirm deletion
function confirmDelete(message) {
    return confirm(message || 'Are you sure you want to delete this item?');
}

// Function to handle file uploads with preview
function handleFileUpload(inputId, previewId) {
    const input = document.getElementById(inputId);
    const preview = document.getElementById(previewId);
    
    if (input && preview) {
        input.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    preview.innerHTML = `<div class="alert alert-info">File selected: ${file.name}</div>`;
                };
                reader.readAsDataURL(file);
            }
        });
    }
}