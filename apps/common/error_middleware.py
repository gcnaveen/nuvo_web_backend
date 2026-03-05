import logging
import os

from django.http import JsonResponse

logger = logging.getLogger(__name__)


class GlobalExceptionMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            # Log full traceback to CloudWatch so you can see the real error
            logger.exception("Request failed: %s", e)
            payload = {
                "success": False,
                "message": "Internal server error",
                "data": {}
            }
            # In Lambda, optionally include error detail for debugging (set DEBUG_LAMBDA=1 in env)
            if os.getenv("DEBUG_LAMBDA") == "1":
                payload["debug_error"] = str(e)
            return JsonResponse(payload, status=500)