import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.http import HttpResponse
from django.test import Client

from routing.domain import LatLon
from trips.tests.helpers import FakeWeather, forecast_from
from weather.forecast import LocationForecast, WeatherError

NOW = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
ROUTE = [[-100.0, 40.0], [-99.5, 40.0]]


def body(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "routes": [ROUTE],
        "departure": (NOW + timedelta(hours=3)).isoformat(),
        "load_lb": 20_000,
    }
    return {**values, **overrides}


def without(field: str) -> dict[str, Any]:
    values = body()
    del values[field]
    return values


def post(payload: Any) -> HttpResponse:
    return Client().post("/api/heatmap", data=json.dumps(payload), content_type="application/json")


def calm(position: LatLon) -> LocationForecast:
    return forecast_from(NOW - timedelta(hours=12))


@pytest.fixture
def weather() -> Iterator[MagicMock]:
    with patch("api.views.get_weather_client") as get_client:
        get_client.return_value = FakeWeather(calm)
        yield get_client


@pytest.mark.usefixtures("weather")
def test_returns_the_grid_and_all_frames() -> None:
    response = post(body())

    assert response.status_code == 200
    heatmap = response.json()
    assert set(heatmap) == {"columns", "rows", "west", "south", "east", "north", "cells", "frames"}
    assert heatmap["columns"] > 0
    assert heatmap["rows"] > 0
    assert heatmap["west"] < -100 < -99.5 < heatmap["east"]
    assert heatmap["south"] < 40 < heatmap["north"]
    assert len(heatmap["frames"]) == 49
    assert {len(frame) for frame in heatmap["frames"]} == {len(heatmap["cells"])}
    assert set(heatmap["frames"][0]) == {"0"}


@pytest.mark.usefixtures("weather")
def test_payload_stays_compact_for_a_cross_country_trip() -> None:
    path = [[-118.2, 34.0], [-105.0, 40.0], [-90.0, 41.5], [-74.0, 40.7]]

    response = post(body(routes=[path]))

    assert len(response.content) < 30_000


@pytest.mark.usefixtures("weather")
def test_accepts_up_to_three_routes() -> None:
    routes = [ROUTE, [[-100.0, 41.0], [-99.5, 41.0]], [[-100.0, 42.0], [-99.5, 42.0]]]

    assert post(body(routes=routes)).status_code == 200


@pytest.mark.usefixtures("weather")
def test_load_is_used(weather: MagicMock) -> None:
    weather.return_value = FakeWeather(
        lambda position: forecast_from(NOW - timedelta(hours=12), wind=lambda hour: 47.0)
    )

    assert set(post(body(load_lb=30_001)).json()["frames"][0]) == {"4"}
    assert set(post(body(load_lb=30_000)).json()["frames"][0]) == {"3"}


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        (without("routes"), "routes"),
        (without("departure"), "departure"),
        (without("load_lb"), "load_lb"),
        (body(routes=[]), "routes"),
        (body(routes=[ROUTE] * 4), "routes"),
        (body(routes="route"), "routes"),
        (body(routes=[[[-100.0, 40.0]]]), "routes"),
        (body(routes=[[[-100.0, 40.0]] * 20_001]), "routes"),
        (body(routes=["line"]), "routes"),
        (body(routes=[5]), "routes"),
        (body(routes=[[-100.0, 40.0]]), "routes"),
        (body(routes=[[[-100.0, 40.0], [-99.5]]]), "routes"),
        (body(routes=[[[-100.0, 40.0], [-99.5, 40.0, 1.0]]]), "routes"),
        (body(routes=[[[-100.0, 40.0], ["a", "b"]]]), "routes"),
        (body(routes=[[[-100.0, 40.0], "ab"]]), "routes"),
        (body(routes=[[[-100.0, 40.0], [None, 40.0]]]), "routes"),
        (body(routes=[[[-181.0, 40.0], [-99.5, 40.0]]]), "routes"),
        (body(routes=[[[181.0, 40.0], [-99.5, 40.0]]]), "routes"),
        (body(routes=[[[-100.0, 86.0], [-99.5, 40.0]]]), "routes"),
        (body(routes=[[[-100.0, -86.0], [-99.5, 40.0]]]), "routes"),
        (body(departure="soon"), "departure"),
        (body(departure="2026-11-10T09:30:00"), "departure"),
        (body(load_lb=-1), "load_lb"),
        (body(load_lb=200_001), "load_lb"),
    ],
)
def test_invalid_requests_name_the_field(
    weather: MagicMock, payload: dict[str, Any], field: str
) -> None:
    response = post(payload)

    assert response.status_code == 400
    assert field in response.json()["fields"]
    assert response.json()["error"]
    weather.assert_not_called()


def test_very_large_coordinates_are_rejected(weather: MagicMock) -> None:
    raw = json.dumps(body()).replace("-100.0", "1e999", 1)

    response = Client().post("/api/heatmap", data=raw, content_type="application/json")

    assert response.status_code == 400
    weather.assert_not_called()


def test_only_post_is_allowed() -> None:
    assert Client().get("/api/heatmap").status_code == 405


def test_weather_failure_is_a_bad_gateway(weather: MagicMock) -> None:
    weather.return_value = MagicMock()
    weather.return_value.forecasts.side_effect = WeatherError("The weather service failed.")

    response = post(body())

    assert response.status_code == 502
    assert response.json() == {"error": "The weather service failed."}


@pytest.mark.usefixtures("weather")
def test_an_old_departure_is_refused() -> None:
    response = post(body(departure=(NOW - timedelta(days=3)).isoformat()))

    assert response.status_code == 400
    assert response.json()["fields"]["departure"] == ["Departure time is in the past."]


@pytest.mark.usefixtures("weather")
def test_a_departure_beyond_the_forecast_is_refused() -> None:
    response = post(body(departure=(NOW + timedelta(days=30)).isoformat()))

    assert response.status_code == 400
    assert response.json()["fields"]["departure"] == ["The weather forecast doesn't reach this departure."]


def test_a_corridor_too_large_is_unprocessable(weather: MagicMock) -> None:
    globe = [[-170.0, 60.0], [0.0, 0.0], [170.0, -50.0]]

    response = post(body(routes=[globe]))

    assert response.status_code == 422
    assert "too large for the weather heatmap" in response.json()["error"]
    assert weather.return_value.calls == []
