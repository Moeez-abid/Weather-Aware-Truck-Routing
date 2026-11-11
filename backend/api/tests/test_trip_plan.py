import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from django.http import HttpResponse
from django.test import Client

from routing.domain import LatLon, NoRouteError, ProviderError, Route, RouteTooComplexError, TimingPoint
from trips.tests.helpers import FakeRouter, FakeWeather, forecast_from, straight_route
from weather.forecast import ForecastUnavailableError, LocationForecast, WeatherError

CHICAGO = ZoneInfo("America/Chicago")
NOW = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
FORECAST_START = NOW - timedelta(hours=12)


def body(**overrides: Any) -> dict[str, Any]:
    departure = (NOW + timedelta(hours=3)).astimezone(CHICAGO).replace(tzinfo=None)
    values: dict[str, Any] = {
        "origin": {"lat": 40.0, "lon": -100.0},
        "destination": {"lat": 40.0, "lon": -95.0},
        "departure": departure.isoformat(timespec="minutes"),
        "load_lb": 20_000,
        "interval_miles": 25,
    }
    return {**values, **overrides}


def without(field: str) -> dict[str, Any]:
    values = body()
    del values[field]
    return values


def post(payload: Any) -> HttpResponse:
    return Client().post("/api/trips/plan", data=json.dumps(payload), content_type="application/json")


def calm(position: LatLon) -> LocationForecast:
    return forecast_from(FORECAST_START)


@pytest.fixture
def router() -> Iterator[MagicMock]:
    with patch("api.views.get_tomtom_client") as get_client:
        get_client.return_value = FakeRouter([straight_route(60, 2)])
        yield get_client


@pytest.fixture
def weather() -> Iterator[MagicMock]:
    with patch("api.views.get_weather_client") as get_client:
        get_client.return_value = FakeWeather(calm)
        yield get_client


@pytest.mark.usefixtures("router", "weather")
def test_returns_routes_with_summaries_and_checkpoints() -> None:
    response = post(body())

    assert response.status_code == 200
    plan = response.json()
    assert plan["timezone"] == "America/Chicago"
    assert plan["recommended_route_id"] == "A"
    assert plan["ranked_route_ids"] == ["A"]
    assert plan["closures_checked"] is True

    route = plan["routes"][0]
    assert route["id"] == "A"
    assert route["distance_miles"] == 60
    assert route["duration_seconds"] == 7200
    assert route["average_risk"] == 0
    assert route["miles_by_risk"] == {"low": 60, "moderate": 0, "high": 0, "severe": 0, "no_travel": 0}
    assert [checkpoint["mile"] for checkpoint in route["checkpoints"]] == [0, 25, 50, 60]

    first = route["checkpoints"][0]
    assert first["lat"] == 40
    assert first["lon"] == -100
    assert first["timezone"] == "America/Chicago"
    assert first["risk"] == "low"
    assert first["risk_factors"] == {"wind": "low", "rain": "low", "snow": "low"}
    assert first["weather"] == {"wind_mph": 5, "rain_in_hr": 0, "snow_in_hr": 0}


@pytest.mark.usefixtures("router", "weather")
def test_times_are_local_with_an_offset() -> None:
    plan = post(body()).json()

    departure = NOW + timedelta(hours=3)
    assert plan["departure"] == departure.astimezone(CHICAGO).isoformat()
    route = plan["routes"][0]
    assert route["checkpoints"][0]["eta"] == plan["departure"]
    assert datetime.fromisoformat(route["arrival"]) == departure + timedelta(hours=2)
    assert route["arrival"] == route["checkpoints"][-1]["eta"]


@pytest.mark.usefixtures("router", "weather")
def test_geometry_is_longitude_first_and_simplified() -> None:
    geometry = post(body()).json()["routes"][0]["geometry"]

    assert geometry == [[-100.0, 40.0], [-95.0, 40.0]]


@pytest.mark.usefixtures("weather")
def test_corridor_is_much_lighter_than_the_drawn_line(router: MagicMock) -> None:
    # Bends of about 0.005 degrees: visible on the map but irrelevant to the heatmap grid.
    points = tuple(LatLon(40 + (i % 2) * 0.005, -100 + i * 0.05) for i in range(101))
    length = 60 * 1609.344
    router.return_value = FakeRouter(
        [Route(points, length, 7200, (TimingPoint(0, 0, 0), TimingPoint(100, length, 7200)))]
    )

    route = post(body()).json()["routes"][0]

    assert len(route["geometry"]) == 101
    assert route["corridor"] == [[-100.0, 40.0], [-95.0, 40.0]]


@pytest.mark.usefixtures("router")
def test_risk_names_cover_no_travel(weather: MagicMock) -> None:
    weather.return_value = FakeWeather(lambda position: forecast_from(FORECAST_START, wind=lambda hour: 60.0))

    plan = post(body()).json()

    route = plan["routes"][0]
    assert plan["recommended_route_id"] is None
    assert route["checkpoints"][0]["risk"] == "no_travel"
    assert route["checkpoints"][0]["risk_factors"]["wind"] == "no_travel"
    assert route["miles_by_risk"]["no_travel"] == 60


@pytest.mark.usefixtures("weather")
@pytest.mark.parametrize("interval", [10, 25, 50, "25"])
def test_supported_intervals(router: MagicMock, interval: Any) -> None:
    response = post(body(interval_miles=interval))

    assert response.status_code == 200
    miles = [checkpoint["mile"] for checkpoint in response.json()["routes"][0]["checkpoints"]]
    assert miles[1] == int(interval)


@pytest.mark.usefixtures("router", "weather")
def test_interval_defaults_to_25_miles() -> None:
    response = post(without("interval_miles"))

    assert response.json()["routes"][0]["checkpoints"][1]["mile"] == 25


@pytest.mark.usefixtures("router", "weather")
@pytest.mark.parametrize("load", [0, 200_000])
def test_load_limits_are_inclusive(load: int) -> None:
    assert post(body(load_lb=load)).status_code == 200


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        (without("origin"), "origin"),
        (without("destination"), "destination"),
        (without("departure"), "departure"),
        (without("load_lb"), "load_lb"),
        (body(origin={"lat": 91, "lon": -100}), "origin"),
        (body(origin={"lat": -91, "lon": -100}), "origin"),
        (body(origin={"lat": 40}), "origin"),
        (body(origin="Chicago"), "origin"),
        (body(destination={"lat": 40, "lon": 181}), "destination"),
        (body(destination={"lat": 40, "lon": -181}), "destination"),
        (body(destination={"lat": "nan", "lon": -95}), "destination"),
        (body(destination={"lat": 40, "lon": "inf"}), "destination"),
        (body(load_lb=-1), "load_lb"),
        (body(load_lb=200_001), "load_lb"),
        (body(load_lb="nan"), "load_lb"),
        (body(load_lb="heavy"), "load_lb"),
        (body(interval_miles=15), "interval_miles"),
        (body(departure="tomorrow"), "departure"),
        (body(departure="2026-11-10T09:30:00Z"), "departure"),
        (body(departure="2026-11-10T09:30:00-06:00"), "departure"),
        (body(destination={"lat": 40.001, "lon": -100.0}), "destination"),
    ],
)
def test_invalid_requests_name_the_field(
    router: MagicMock, weather: MagicMock, payload: dict[str, Any], field: str
) -> None:
    response = post(payload)

    assert response.status_code == 400
    assert field in response.json()["fields"]
    assert response.json()["error"]
    router.assert_not_called()
    weather.assert_not_called()


@pytest.mark.usefixtures("router", "weather")
@pytest.mark.parametrize("payload", [[], [1, 2], "text", 5])
def test_body_that_is_not_an_object_is_rejected(payload: Any) -> None:
    assert post(payload).status_code == 400


@pytest.mark.usefixtures("router", "weather")
def test_invalid_json_is_rejected() -> None:
    response = Client().post("/api/trips/plan", data="{not json", content_type="application/json")

    assert response.status_code == 400


def test_only_post_is_allowed() -> None:
    assert Client().get("/api/trips/plan").status_code == 405


@pytest.mark.usefixtures("router", "weather")
def test_past_departure_is_reported_on_the_departure_field() -> None:
    departure = (NOW - timedelta(days=1)).astimezone(CHICAGO).replace(tzinfo=None)

    response = post(body(departure=departure.isoformat()))

    assert response.status_code == 400
    assert response.json()["error"] == "Departure time is in the past."
    assert response.json()["fields"] == {"departure": ["Departure time is in the past."]}


@pytest.mark.usefixtures("weather")
def test_missing_route_is_unprocessable(router: MagicMock) -> None:
    router.return_value = MagicMock()
    router.return_value.calculate_routes.side_effect = NoRouteError("No truck route could be found.")

    response = post(body())

    assert response.status_code == 422
    assert response.json() == {"error": "No truck route could be found."}


class ClosedAtDepartureRouter(FakeRouter):
    def calculate_routes(self, *args: Any, use_departure_time: bool = True, **kwargs: Any) -> list[Route]:
        if use_departure_time:
            raise NoRouteError("No truck route could be found.")
        return super().calculate_routes(*args, **kwargs)


@pytest.mark.usefixtures("router", "weather")
def test_a_trip_blocked_by_closures_at_departure_says_they_were_not_checked(router: MagicMock) -> None:
    router.return_value = ClosedAtDepartureRouter([straight_route(60, 2)])

    response = post(body())

    assert response.status_code == 200
    assert response.json()["closures_checked"] is False
    assert response.json()["routes"][0]["distance_miles"] == 60


@pytest.mark.usefixtures("router")
def test_trip_beyond_the_forecast_is_unprocessable(weather: MagicMock) -> None:
    weather.return_value = MagicMock()
    weather.return_value.forecasts.side_effect = ForecastUnavailableError("Too far ahead.")

    response = post(body())

    assert response.status_code == 422
    assert response.json() == {"error": "Too far ahead."}


@pytest.mark.usefixtures("weather")
def test_routing_service_failure_is_a_bad_gateway(router: MagicMock) -> None:
    router.side_effect = ProviderError("The routing service failed.")

    response = post(body())

    assert response.status_code == 502
    assert response.json() == {"error": "The routing service failed."}


@pytest.mark.usefixtures("router")
def test_weather_service_failure_is_a_bad_gateway(weather: MagicMock) -> None:
    weather.return_value = MagicMock()
    weather.return_value.forecasts.side_effect = WeatherError("The weather service failed.")

    response = post(body())

    assert response.status_code == 502
    assert response.json() == {"error": "The weather service failed."}


@pytest.mark.usefixtures("weather")
def test_too_many_checkpoints_points_to_the_interval(router: MagicMock) -> None:
    router.return_value = FakeRouter([straight_route(1_600, 30, lat=40.0 + index) for index in range(3)])

    response = post(body(interval_miles=10))

    assert response.status_code == 422
    assert "Choose 25 miles" in response.json()["error"]
    assert response.json()["fields"]["interval_miles"] == [response.json()["error"]]


@pytest.mark.usefixtures("weather")
def test_a_trip_too_long_for_any_interval_has_no_field(router: MagicMock) -> None:
    router.return_value = FakeRouter([straight_route(8_000, 100, lat=40.0 + index) for index in range(3)])

    response = post(body(interval_miles=50))

    assert response.status_code == 422
    assert "fields" not in response.json()


@pytest.mark.usefixtures("weather")
def test_a_route_too_long_to_calculate_is_unprocessable(router: MagicMock) -> None:
    router.return_value.calculate_routes = MagicMock(side_effect=RouteTooComplexError("Too long."))

    response = post(body())

    assert response.status_code == 422
    assert response.json() == {"error": "Too long."}
