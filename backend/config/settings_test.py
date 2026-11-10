import os

# Tests must not depend on a developer's local .env values.
os.environ["DJANGO_SECRET_KEY"] = "test-secret-key"
os.environ["CORS_ALLOWED_ORIGINS"] = "http://localhost:5173"
os.environ["TOMTOM_API_KEY"] = "test-tomtom-key"
# Tests run with production behaviour, whatever DJANGO_DEBUG says in a local .env.
os.environ["DJANGO_DEBUG"] = "false"

from .settings import *  # noqa: E402,F403

# The test client speaks plain HTTP, so it would otherwise be redirected to HTTPS.
SECURE_SSL_REDIRECT = False

# Throttling has its own tests, which set their own limits. Everywhere else it would only get in
# the way of tests that make many requests.
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {
        scope: "100000/hour" for scope in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]  # noqa: F405
    },
}
