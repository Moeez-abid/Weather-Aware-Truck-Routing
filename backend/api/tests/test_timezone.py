from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.http import HttpResponse
from django.test import Client

from routing.domain import LatLon
from trips.tests.helpers import FakeWeather, forecast_from
from weather.forecast import WeatherError

START = datetime(2026, 11, 10, 6, 0, tzinfo=UTC)


def get(**params: Any) -> HttpResponse:
    return Client().get("/api/timezone", params)


@patch("api.views.get_weather_client")
def test_returns_the_timezone_of_the_position(get_client: MagicMock) -> None:
    weather = FakeWeather(lambda position: forecast_from(START, timezone="America/Denver"))
    get_client.return_value = weather

    response = get(lat=39.74, lon=-104.99)

    assert response.status_code == 200
    assert response.json() == {"timezone": "America/Denver"}
    assert weather.calls == [[LatLon(39.74, -104.99)]]


@pytest.mark.parametrize(
    "params",
    [{}, {"lat": 40}, {"lon": -100}, {"lat": 91, "lon": -100}, {"lat": 40, "lon": 181}, {"lat": "x", "lon": 1}],
)
@patch("api.views.get_weather_client")
def test_invalid_positions_are_rejected(get_client: MagicMock, params: dict[str, Any]) -> None:
    response = get(**params)

    assert response.status_code == 400
    assert response.json()["error"]
    get_client.assert_not_called()


@patch("api.views.get_weather_client")
def test_weather_failure_is_a_bad_gateway(get_client: MagicMock) -> None:
    get_client.return_value.forecasts.side_effect = WeatherError("The weather service failed.")

    response = get(lat=40, lon=-100)

    assert response.status_code == 502
    assert response.json() == {"error": "The weather service failed."}


def test_only_get_is_allowed() -> None:
    assert Client().post("/api/timezone").status_code == 405
