from django.test import Client


def test_health_returns_ok() -> None:
    response = Client().get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_rejects_other_methods() -> None:
    response = Client().post("/api/health", data={}, content_type="application/json")

    assert response.status_code == 405


def test_allowed_origin_receives_cors_header() -> None:
    response = Client().get("/api/health", HTTP_ORIGIN="http://localhost:5173")

    assert response["Access-Control-Allow-Origin"] == "http://localhost:5173"


def test_unknown_origin_receives_no_cors_header() -> None:
    response = Client().get("/api/health", HTTP_ORIGIN="https://example.com")

    assert "Access-Control-Allow-Origin" not in response
