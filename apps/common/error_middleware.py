from django.http import JsonResponse


class GlobalExceptionMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            return JsonResponse({
                "success": False,
                "message": "Internal server error",
                "data": {}
            }, status=500)