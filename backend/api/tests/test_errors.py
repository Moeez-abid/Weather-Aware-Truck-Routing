import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.test import Client

from api.throttles import GeocodeThrottle, HeatmapThrottle, TimezoneThrottle, TripPlanThrottle
from config import settings as production_settings

BACKEND = Path(__file__).resolve().parents[2]


def test_wrong_method_uses_the_api_error_shape() -> None:
    response = Client().get("/api/trips/plan")

    assert response.status_code == 405
    assert set(response.json()) == {"error"}


def test_malformed_json_uses_the_api_error_shape() -> None:
    response = Client().post("/api/trips/plan", data="{oops", content_type="application/json")

    assert response.status_code == 400
    assert set(response.json()) == {"error"}


@pytest.fixture
def two_searches_an_hour(monkeypatch: pytest.MonkeyPatch) -> Any:
    cache.clear()
    monkeypatch.setattr(GeocodeThrottle, "rate", "2/hour", raising=False)
    yield
    cache.clear()


@pytest.mark.usefixtures("two_searches_an_hour")
@patch("api.views.get_tomtom_client")
def test_requests_over_the_limit_are_refused_with_a_clear_message(get_client: MagicMock) -> None:
    get_client.return_value.geocode.return_value = []
    client = Client()

    assert client.get("/api/geocode", {"q": "Dallas"}).status_code == 200
    assert client.get("/api/geocode", {"q": "Dallas"}).status_code == 200
    refused = client.get("/api/geocode", {"q": "Dallas"})

    assert refused.status_code == 429
    assert refused.json() == {
        "error": "Too many requests from this connection. Please wait a few minutes and try again."
    }
    assert int(refused["Retry-After"]) > 0
    assert get_client.return_value.geocode.call_count == 2


@pytest.mark.usefixtures("two_searches_an_hour")
@patch("api.views.get_tomtom_client")
def test_limits_are_counted_per_connection(get_client: MagicMock) -> None:
    get_client.return_value.geocode.return_value = []

    for _ in range(2):
        Client(REMOTE_ADDR="203.0.113.1").get("/api/geocode", {"q": "Dallas"})

    assert Client(REMOTE_ADDR="203.0.113.2").get("/api/geocode", {"q": "Dallas"}).status_code == 200


def test_every_limited_endpoint_has_a_production_rate() -> None:
    rates = production_settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]

    for throttle in (GeocodeThrottle, TimezoneThrottle, TripPlanThrottle, HeatmapThrottle):
        assert throttle.scope in rates
    assert rates["trip_plan"] == "60/hour"
    assert rates["heatmap"] == "60/hour"


def production_value(expression: str, **env: str) -> Any:
    """Imports the real settings in a fresh process, as the production server would."""
    script = f"import json, config.settings as s; print(json.dumps({expression}))"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND,
        env={**os.environ, "DJANGO_SECRET_KEY": "x", "DJANGO_DEBUG": "false", **env},
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_vercel_hostnames_are_allowed() -> None:
    hosts = production_value(
        "s.ALLOWED_HOSTS",
        DJANGO_ALLOWED_HOSTS="api.example.com",
        VERCEL_PROJECT_PRODUCTION_URL="clearhaul-api.vercel.app",
        VERCEL_BRANCH_URL="clearhaul-api-git-main.vercel.app",
        VERCEL_URL="clearhaul-api-abc123.vercel.app",
    )

    assert hosts == [
        "api.example.com",
        "clearhaul-api.vercel.app",
        "clearhaul-api-git-main.vercel.app",
        "clearhaul-api-abc123.vercel.app",
    ]


def test_no_hosts_are_allowed_by_default() -> None:
    clean = {name: "" for name in ("VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_BRANCH_URL", "VERCEL_URL")}

    assert production_value("s.ALLOWED_HOSTS", DJANGO_ALLOWED_HOSTS="", **clean) == []


def test_production_trusts_the_proxy_for_https() -> None:
    values = production_value("[s.SECURE_PROXY_SSL_HEADER, s.SECURE_SSL_REDIRECT, s.SECURE_HSTS_SECONDS]")

    assert values == [["HTTP_X_FORWARDED_PROTO", "https"], True, 31_536_000]


def test_development_does_not_force_https() -> None:
    assert production_value("getattr(s, 'SECURE_SSL_REDIRECT', False)", DJANGO_DEBUG="true") is False
