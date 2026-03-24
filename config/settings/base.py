import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv("SECRET_KEY")

DEBUG = False

ALLOWED_HOSTS = []

# On Lambda, skip drf_yasg to avoid "No package metadata was found" (metadata stripped by deploy)
_INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "apps.accounts",
    "apps.users",
    "apps.common",
    "apps.master",
    "apps.events",
]
if not os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    _INSTALLED_APPS.insert(_INSTALLED_APPS.index("corsheaders") + 1, "drf_yasg")
INSTALLED_APPS = _INSTALLED_APPS

MIDDLEWARE = [
    "apps.common.error_middleware.GlobalExceptionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.accounts.middleware.JWTAuthenticationMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ]},
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# MongoDB via MongoEngine — only connect if MONGO_URI is set (required on Lambda)
MONGO_URI = os.getenv("MONGO_URI")
if MONGO_URI:
    from mongoengine import connect
    connect(host=MONGO_URI)
else:
    import logging
    logging.warning("MONGO_URI not set — MongoDB operations will fail. Set it in Lambda environment.")

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOW_ALL_ORIGINS = True

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ]
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS") == "True"


S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")

# On AWS Lambda, AWS provides temporary credentials via AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_SESSION_TOKEN.
# Do NOT pass those explicitly to boto3 unless you also pass the session token.
# We only use explicit keys on Lambda if you provided S3_ACCESS_KEY_ID/S3_SECRET_ACCESS_KEY.
if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    AWS_ACCESS_KEY_ID = S3_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY = S3_SECRET_ACCESS_KEY
else:
    AWS_ACCESS_KEY_ID = S3_ACCESS_KEY_ID or os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = S3_SECRET_ACCESS_KEY or os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME")

AWS_S3_BASE_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"

LOCATION_SERVER_URL = os.getenv("LOCATION_SERVER_URL")
LOCATION_SERVER_TIMEOUT = 5   # seconds, optional

# settings.py additions:
 
# PhonePe (sandbox)
PHONEPE_MERCHANT_ID  = os.environ.get("PHONEPE_MERCHANT_ID",  "PGTESTPAYUAT")
PHONEPE_SALT_KEY     = os.environ.get("PHONEPE_SALT_KEY",     "")
PHONEPE_SALT_INDEX   = os.environ.get("PHONEPE_SALT_INDEX",   "1")
PHONEPE_BASE_URL     = os.environ.get("PHONEPE_BASE_URL",     "https://api-preprod.phonepe.com/apis/pg-sandbox")
PHONEPE_REDIRECT_URL = os.environ.get("PHONEPE_REDIRECT_URL", "https://yourdomain.com/api/events/payment/callback/")
PHONEPE_CALLBACK_URL = os.environ.get("PHONEPE_CALLBACK_URL", "https://yourdomain.com/api/events/payment/webhook/")
 
# Location tracking C++ server
LOCATION_SERVER_URL     = os.environ.get("LOCATION_SERVER_URL",     "http://localhost:9090")
LOCATION_SERVER_TIMEOUT = os.environ.get("LOCATION_SERVER_TIMEOUT", "5")