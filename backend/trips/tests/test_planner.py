from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from risk.classification import RiskLevel
from routing.domain import LatLon, NoRouteError
from trips.planner import InvalidDepartureError, TripPlan, TripRequest, plan_trip
from trips.tests.helpers import (
    DESTINATION,
    ORIGIN,
    FakeRouter,
    FakeWeather,
    forecast_from,
    straight_route,
)
from weather.forecast import ForecastUnavailableError, LocationForecast

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
FORECAST_START = datetime(2026, 11, 10, 6, 0, tzinfo=UTC)
# 09:30 in Chicago, which is 15:30 UTC in November.
LOCAL_DEPARTURE = datetime(2026, 11, 10, 9, 30)
DEPARTURE_UTC = datetime(2026, 11, 10, 15, 30, tzinfo=UTC)


def trip(**overrides: Any) -> TripRequest:
    values: dict[str, Any] = {
        "origin": ORIGIN,
        "destination": DESTINATION,
        "local_departure": LOCAL_DEPARTURE,
        "load_lb": 20_000,
        "interval_miles": 25,
    }
    return TripRequest(**{**values, **overrides})


def calm(position: LatLon) -> LocationForecast:
    return forecast_from(FORECAST_START)


def plan(routes: list[Any], by_position: Any = calm, now: datetime = NOW, **overrides: Any) -> TripPlan:
    return plan_trip(trip(**overrides), FakeRouter(routes), FakeWeather(by_position), now=now)


def hours_after_departure(hour_of_forecast: int) -> float:
    return hour_of_forecast - (DEPARTURE_UTC - FORECAST_START).total_seconds() / 3600


def test_departure_is_read_as_local_time_at_the_origin() -> None:
    router = FakeRouter([straight_route(60, 1)])

    result = plan_trip(trip(), router, FakeWeather(calm), now=NOW)

    assert result.departure == DEPARTURE_UTC
    assert result.timezone == "America/Chicago"
    assert router.calls[0]["departure"] == DEPARTURE_UTC


def test_timezone_comes_from_the_origin() -> None:
    weather = FakeWeather(lambda position: forecast_from(FORECAST_START, timezone="America/Denver"))

    result = plan_trip(trip(), FakeRouter([straight_route(60, 1)]), weather, now=NOW)

    assert weather.calls[0] == [ORIGIN]
    assert result.departure == datetime(2026, 11, 10, 16, 30, tzinfo=UTC)
    assert result.timezone == "America/Denver"


def test_eta_stays_correct_across_a_daylight_saving_change() -> None:
    # Clocks in Chicago go back at 07:00 UTC on 1 November 2026.
    now = datetime(2026, 10, 31, 20, 0, tzinfo=UTC)
    start = datetime(2026, 10, 31, 5, 0, tzinfo=UTC)

    result = plan(
        [straight_route(100, 10)],
        lambda position: forecast_from(start),
        now=now,
        local_departure=datetime(2026, 10, 31, 20, 0),
    )

    assert result.departure == datetime(2026, 11, 1, 1, 0, tzinfo=UTC)
    assert result.routes[0].checkpoints[-1].checkpoint.eta == datetime(2026, 11, 1, 11, 0, tzinfo=UTC)


@pytest.mark.parametrize("minutes_late", [0, 14, 15])
def test_departure_a_moment_ago_is_accepted(minutes_late: int) -> None:
    now = DEPARTURE_UTC + timedelta(minutes=minutes_late)

    assert plan([straight_route(60, 1)], now=now).departure == DEPARTURE_UTC


def test_past_departure_is_rejected_before_routing() -> None:
    router = FakeRouter([straight_route(60, 1)])

    with pytest.raises(InvalidDepartureError):
        plan_trip(
            trip(), router, FakeWeather(calm), now=DEPARTURE_UTC + timedelta(minutes=15, seconds=1)
        )

    assert router.calls == []


def test_departure_beyond_the_forecast_is_rejected_before_routing() -> None:
    router = FakeRouter([straight_route(60, 1)])
    weather = FakeWeather(lambda position: forecast_from(FORECAST_START, hours=4))

    with pytest.raises(ForecastUnavailableError):
        plan_trip(trip(), router, weather, now=NOW)

    assert router.calls == []


def test_trip_that_outlasts_the_forecast_is_rejected() -> None:
    # The forecast runs for 24 hours from 06:00, and the trip departs at 15:30 for 20 hours.
    with pytest.raises(ForecastUnavailableError):
        plan([straight_route(1000, 20)], lambda position: forecast_from(FORECAST_START, hours=24))


def test_route_errors_are_passed_on() -> None:
    class NoRoutes(FakeRouter):
        def calculate_routes(self, *args: Any, **kwargs: Any) -> list[Any]:
            raise NoRouteError("No truck route could be found.")

    with pytest.raises(NoRouteError):
        plan_trip(trip(), NoRoutes([]), FakeWeather(calm), now=NOW)


def test_load_reaches_the_router_and_the_risk_rules() -> None:
    router = FakeRouter([straight_route(60, 1)])
    windy = FakeWeather(lambda position: forecast_from(FORECAST_START, wind=lambda hour: 47.0))

    light = plan_trip(trip(load_lb=30_000), router, windy, now=NOW)
    heavy = plan_trip(trip(load_lb=30_001), router, windy, now=NOW)

    assert router.calls[0]["load_lb"] == 30_000
    assert light.routes[0].checkpoints[0].risk.level == RiskLevel.SEVERE
    assert heavy.routes[0].checkpoints[0].risk.level == RiskLevel.NO_TRAVEL


def test_checkpoints_follow_the_chosen_interval() -> None:
    result = plan([straight_route(60, 1)], interval_miles=25)

    assert [item.checkpoint.mile for item in result.routes[0].checkpoints] == pytest.approx([0, 25, 50, 60])


def test_weather_is_read_at_each_checkpoints_eta_not_the_departure() -> None:
    # Wind is 0 mph until five hours after departure, then 50 mph.
    def rising(hour: int) -> float:
        return 50.0 if hours_after_departure(hour) >= 4.5 else 0.0

    result = plan(
        [straight_route(100, 10)],
        lambda position: forecast_from(FORECAST_START, wind=rising),
        interval_miles=50,
    )

    checkpoints = result.routes[0].checkpoints
    assert [item.checkpoint.mile for item in checkpoints] == pytest.approx([0, 50, 100])
    assert checkpoints[0].weather.wind_mph == 0
    assert checkpoints[1].weather.wind_mph == 50
    assert checkpoints[1].checkpoint.elapsed_s == pytest.approx(5 * 3600)
    assert checkpoints[2].risk.level == RiskLevel.SEVERE


def test_each_checkpoint_uses_the_forecast_for_its_own_position() -> None:
    def by_position(position: LatLon) -> LocationForecast:
        return forecast_from(FORECAST_START, snow=lambda hour: 2.5 if position.lon > -97 else 0.0)

    result = plan([straight_route(100, 2)], by_position, interval_miles=25)

    assert [item.risk.level for item in result.routes[0].checkpoints] == [
        RiskLevel.LOW,
        RiskLevel.LOW,
        RiskLevel.LOW,
        RiskLevel.SEVERE,
        RiskLevel.SEVERE,
    ]


def test_checkpoints_keep_their_own_timezone() -> None:
    def by_position(position: LatLon) -> LocationForecast:
        zone = "America/Denver" if position.lon < -97.5 else "America/Chicago"
        return forecast_from(FORECAST_START, timezone=zone)

    timezones = {item.timezone for item in plan([straight_route(100, 2)], by_position).routes[0].checkpoints}

    assert timezones == {"America/Denver", "America/Chicago"}


def test_every_routes_checkpoints_are_looked_up_in_one_request() -> None:
    weather = FakeWeather(calm)
    routes = [straight_route(60, 1), straight_route(70, 2, lat=41)]

    result = plan_trip(trip(), FakeRouter(routes), weather, now=NOW)

    expected = [item.checkpoint.position for route in result.routes for item in route.checkpoints]
    assert len(weather.calls) == 2
    assert weather.calls[1] == expected


def test_routes_get_their_own_weather_in_order() -> None:
    def by_position(position: LatLon) -> LocationForecast:
        return forecast_from(FORECAST_START, wind=lambda hour: position.lat)

    routes = [straight_route(60, 1, lat=30), straight_route(70, 2, lat=31), straight_route(80, 3, lat=32)]

    result = plan(routes, by_position)

    for route, expected in zip(result.routes, [30, 31, 32], strict=True):
        assert {item.weather.wind_mph for item in route.checkpoints} == {expected}


def test_routes_are_labelled_in_order() -> None:
    routes = [straight_route(60, 1, lat=30), straight_route(70, 2, lat=31), straight_route(80, 3, lat=32)]

    assert [route.id for route in plan(routes).routes] == ["A", "B", "C"]


def test_fewer_than_three_routes_are_still_planned() -> None:
    result = plan([straight_route(60, 1)])

    assert [route.id for route in result.routes] == ["A"]
    assert result.recommendation.recommended_route_id == "A"


def test_miles_by_risk_add_up_to_the_route_length() -> None:
    summary = plan([straight_route(60, 1)]).routes[0].summary

    assert sum(summary.miles_by_level.values()) == pytest.approx(60)
    assert summary.total_miles == pytest.approx(60)
    assert summary.duration_seconds == 3600


def test_safer_route_wins_even_when_it_is_slower() -> None:
    def by_position(position: LatLon) -> LocationForecast:
        return forecast_from(FORECAST_START, wind=lambda hour: 40.0 if position.lat == 30 else 5.0)

    result = plan([straight_route(60, 1, lat=30), straight_route(90, 3, lat=31)], by_position)

    assert result.recommendation.recommended_route_id == "B"
    assert result.recommendation.ranked_route_ids == ["B", "A"]


def test_equal_weather_goes_to_the_faster_route() -> None:
    result = plan([straight_route(90, 3, lat=30), straight_route(60, 1, lat=31)])

    assert result.recommendation.recommended_route_id == "B"


def test_no_route_is_recommended_when_all_have_no_travel_miles() -> None:
    def by_position(position: LatLon) -> LocationForecast:
        return forecast_from(FORECAST_START, wind=lambda hour: 60.0)

    result = plan([straight_route(60, 1, lat=30), straight_route(90, 3, lat=31)], by_position)

    assert result.recommendation.recommended_route_id is None
    assert len(result.recommendation.ranked_route_ids) == 2
