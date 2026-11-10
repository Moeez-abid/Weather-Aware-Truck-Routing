import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set. See .env.example.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
# Vercel sets these to the deployment's own vercel.app hostnames, without the scheme.
ALLOWED_HOSTS += [
    host
    for name in ("VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_BRANCH_URL", "VERCEL_URL")
    if (host := os.environ.get(name))
]
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")

INSTALLED_APPS = [
    "corsheaders",
    "rest_framework",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# The API is stateless: trips are calculated per request and nothing is stored.
DATABASES = {}

USE_TZ = True
TIME_ZONE = "UTC"

# Holds weather forecasts. Django's default of 300 entries is smaller than one trip's heatmap.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "OPTIONS": {"MAX_ENTRIES": 2000},
    }
}

TOMTOM_API_KEY = os.environ.get("TOMTOM_API_KEY", "")

# httpx logs full request URLs at INFO level, and TomTom URLs contain the API key.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "loggers": {"httpx": {"level": "WARNING"}},
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "api.exceptions.handle_api_exception",
    # Per connection. These protect the TomTom and Open-Meteo quotas on a public link rather than
    # act as a security boundary: a normal trip uses a handful of calls, and typing an address a few
    # dozen searches.
    "DEFAULT_THROTTLE_RATES": {
        "geocode": "600/hour",
        "timezone": "300/hour",
        "trip_plan": "60/hour",
        "heatmap": "60/hour",
    },
}

if not DEBUG:
    # Vercel ends HTTPS at its edge and passes the original scheme on in this header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    # The API sets no cookies, but these keep the deployment checklist clean if that changes.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

SILENCED_SYSTEM_CHECKS = [
    # CSRF protects cookie-based sessions. This API has no sessions, cookies or logins.
    "security.W003",
    # The API runs on a subdomain of vercel.app, whose other subdomains it doesn't control,
    # so HSTS can't safely cover subdomains or be submitted to the browser preload list.
    "security.W005",
    "security.W021",
]
