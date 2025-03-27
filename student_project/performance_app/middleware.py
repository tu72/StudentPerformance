from django.utils.cache import patch_response_headers
from django.middleware.cache import UpdateCacheMiddleware, FetchFromCacheMiddleware

class StudentGradesCacheMiddleware:
    """
    Middleware that adds light caching for the student grades page.
    This helps improve performance when loading the page with many students.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Process the request
        response = self.get_response(request)
        
        # Only cache student_grades page GET requests
        if (request.path.startswith('/student-grades/') and 
            request.method == 'GET' and 
            not request.user.is_anonymous):
            
            # Add cache headers with a short timeout (10 seconds)
            # This provides a performance boost without making data too stale
            patch_response_headers(response, cache_timeout=10)
            
            # Mark this view as cacheable for improved speed
            response['Cache-Control'] = 'max-age=10, private'
        
        return response 