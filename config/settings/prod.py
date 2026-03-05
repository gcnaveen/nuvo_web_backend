from .base import *

DEBUG = False
# Allow API Gateway and custom domain; extend as needed
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",")]