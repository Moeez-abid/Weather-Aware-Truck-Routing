import os

# Tests must not depend on a developer's local .env values.
os.environ["DJANGO_SECRET_KEY"] = "test-secret-key"
os.environ["CORS_ALLOWED_ORIGINS"] = "http://localhost:5173"

from .settings import *  # noqa: E402,F403
