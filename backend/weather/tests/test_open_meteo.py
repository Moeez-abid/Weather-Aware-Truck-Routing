import json
import math
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from django.core.cache import cache

from risk.classification import RiskLevel, assess
from routing.domain import LatLon
from weather.forecast import ForecastUnavailableError, WeatherError
from weather.open_meteo import OpenMeteoClient, get_weather_client, snap_position

FIXTURES = Path(__file__).parent / "fixtures"
FIRST_HOUR = 1_794_204_000
CHICAGO = LatLon(41.9, -87.65)
DENVER = LatLon(39.75, -105.0)


@pytest.fixture(autouse=True)
def empty_cache() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


def real_response() -> list[dict[str, Any]]:
    return json.loads((FIXTURES / "open_meteo_two_locations.json").read_text())


def location(**hourly: Any) -> dict[str, Any]:
    series = {
        "time": [FIRST_HOUR, FIRST_HOUR + 3600],
        "wind_speed_10m": [5.0, 6.0],
        "rain": [0.0, 0.0],
        "showers": [0.0, 0.0],
        "snowfall": [0.0, 0.0],
    }
    return {"timezone": "America/Chicago", "hourly": {**series, **hourly}}


def latitudes(request: httpx.Request) -> list[str]:
    return request.url.params["latitude"].split(",")


def echo_handler(seen: list[httpx.Request]) -> Callable[[httpx.Request], httpx.Response]:
    """Answer with one location per requested latitude, carrying that latitude as the wind."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = [location(wind_speed_10m=[abs(float(lat)), 0.0]) for lat in latitudes(request)]
        return httpx.Response(200, json=body)

    return handler


def client_with(handler: Callable[[httpx.Request], httpx.Response], **kwargs: Any) -> OpenMeteoClient:
    return OpenMeteoClient(transport=httpx.MockTransport(handler), sleep=lambda _: None, **kwargs)


def client_returning(body: Any, status: int = 200) -> OpenMeteoClient:
    return client_with(lambda request: httpx.Response(status, json=body))


def grid(count: int) -> list[LatLon]:
    return [LatLon(30 + i // 100 * 0.25, -100 + i % 100 * 0.25) for i in range(count)]


def test_parses_a_real_response() -> None:
    body = real_response()

    chicago, denver = client_returning(body).forecasts([CHICAGO, DENVER])

    raw = body[0]["hourly"]
    assert chicago.timezone == "America/Chicago"
    assert denver.timezone == "America/Denver"
    assert chicago.first_hour == raw["time"][0]
    assert chicago.wind_mph == tuple(raw["wind_speed_10m"])
    assert chicago.snow_in_hr == tuple(raw["snowfall"])
    assert chicago.rain_in_hr == tuple(
        round(rain + showers, 3) for rain, showers in zip(raw["rain"], raw["showers"], strict=True)
    )
    assert len(chicago.wind_mph) == len(raw["time"])


def test_single_location_response_is_a_bare_object() -> None:
    forecasts = client_returning(location()).forecasts([CHICAGO])

    assert len(forecasts) == 1
    assert forecasts[0].first_hour == FIRST_HOUR


def test_request_asks_for_the_units_the_risk_rules_use() -> None:
    seen: list[httpx.Request] = []

    client_with(echo_handler(seen)).forecasts([CHICAGO, DENVER])

    params = seen[0].url.params
    assert params["latitude"] == "41.90,39.75"
    assert params["longitude"] == "-87.65,-105.00"
    assert params["hourly"] == "wind_speed_10m,rain,showers,snowfall"
    assert params["wind_speed_unit"] == "mph"
    assert params["precipitation_unit"] == "inch"
    assert params["timezone"] == "auto"
    assert params["timeformat"] == "unixtime"
    assert params["forecast_days"] == "14"


def test_showers_count_as_rain() -> None:
    body = location(rain=[0.0, 0.0], showers=[0.3, 0.0])

    forecast = client_returning(body).forecasts([CHICAGO])[0]

    assert forecast.rain_in_hr[0] == 0.3


def test_rain_plus_showers_lands_in_the_correct_band() -> None:
    body = location(rain=[0.0, 0.09], showers=[0.0, 0.01])
    forecast = client_returning(body).forecasts([CHICAGO])[0]

    sample = forecast.sample_at(datetime.fromtimestamp(FIRST_HOUR, UTC))

    assert sample.rain_in_hr == 0.1
    assert assess(sample, 10_000).rain == RiskLevel.MODERATE


@pytest.mark.parametrize(
    ("rain", "showers"), [([None, 0.0], [0.0, 0.0]), ([0.0, 0.0], [None, 0.0])]
)
def test_missing_rain_or_showers_stays_missing(rain: list[Any], showers: list[Any]) -> None:
    forecast = client_returning(location(rain=rain, showers=showers)).forecasts([CHICAGO])[0]

    assert forecast.rain_in_hr == (None, 0.0)


def test_null_in_a_response_is_unavailable_rather_than_calm() -> None:
    body = location(wind_speed_10m=[None, None])
    forecast = client_returning(body).forecasts([CHICAGO])[0]

    with pytest.raises(ForecastUnavailableError):
        forecast.sample_at(datetime.fromtimestamp(FIRST_HOUR, UTC))


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        (LatLon(41.8781, -87.6298), (41.88, -87.63)),
        (LatLon(39.7392, -104.9903), (39.74, -104.99)),
        (LatLon(30.25, -97.75), (30.25, -97.75)),
    ],
)
def test_positions_are_rounded_to_a_hundredth_of_a_degree(
    position: LatLon, expected: tuple[float, float]
) -> None:
    assert snap_position(position) == expected


def test_results_stay_in_the_requested_order() -> None:
    seen: list[httpx.Request] = []
    positions = grid(250)[::-1]

    forecasts = client_with(echo_handler(seen)).forecasts(positions)

    assert [forecast.wind_mph[0] for forecast in forecasts] == [position.lat for position in positions]


def test_large_requests_are_split_into_batches() -> None:
    seen: list[httpx.Request] = []

    client_with(echo_handler(seen)).forecasts(grid(250))

    assert sorted(len(latitudes(request)) for request in seen) == [50, 100, 100]


def test_nearby_positions_are_requested_once() -> None:
    seen: list[httpx.Request] = []

    forecasts = client_with(echo_handler(seen)).forecasts(
        [LatLon(41.881, -87.631), DENVER, LatLon(41.879, -87.629)]
    )

    assert len(latitudes(seen[0])) == 2
    assert forecasts[0] is forecasts[2]


def test_no_positions_makes_no_request() -> None:
    seen: list[httpx.Request] = []

    assert client_with(echo_handler(seen)).forecasts([]) == []
    assert seen == []


def test_cached_positions_are_not_requested_again() -> None:
    seen: list[httpx.Request] = []
    client = client_with(echo_handler(seen))

    first = client.forecasts([CHICAGO])
    second = client.forecasts([CHICAGO])

    assert len(seen) == 1
    assert second == first


def test_only_uncached_positions_are_requested() -> None:
    seen: list[httpx.Request] = []
    client = client_with(echo_handler(seen))
    client.forecasts([CHICAGO])

    forecasts = client.forecasts([DENVER, CHICAGO])

    assert latitudes(seen[1]) == ["39.75"]
    assert [forecast.wind_mph[0] for forecast in forecasts] == [39.75, 41.9]


def test_a_whole_heatmap_fits_in_the_cache() -> None:
    seen: list[httpx.Request] = []
    client = client_with(echo_handler(seen))
    client.forecasts(grid(1500))
    requests_made = len(seen)

    client.forecasts(grid(1500))

    assert len(seen) == requests_made


def test_cache_expires_after_fifteen_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []
    client = client_with(echo_handler(seen))
    now = time.time()
    client.forecasts([CHICAGO])

    monkeypatch.setattr(time, "time", lambda: now + 14 * 60)
    client.forecasts([CHICAGO])
    assert len(seen) == 1

    monkeypatch.setattr(time, "time", lambda: now + 16 * 60)
    client.forecasts([CHICAGO])
    assert len(seen) == 2


def test_batches_finished_before_a_failure_stay_cached() -> None:
    seen: list[httpx.Request] = []
    good = echo_handler(seen)
    failing = True

    def handler(request: httpx.Request) -> httpx.Response:
        if failing and "32.25" in latitudes(request):
            return httpx.Response(429, json={"error": True})
        return good(request)

    client = client_with(handler)
    positions = [*grid(100), LatLon(32.25, -100)]
    with pytest.raises(WeatherError):
        client.forecasts(positions)

    failing = False
    seen.clear()
    client.forecasts(positions)

    assert [latitudes(request) for request in seen] == [["32.25"]]


@pytest.mark.parametrize("first_failure", ["server", "network"])
def test_temporary_failures_are_retried(first_failure: str) -> None:
    waits: list[float] = []
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            if first_failure == "network":
                raise httpx.ConnectError("down")
            return httpx.Response(503, json={"error": True})
        return httpx.Response(200, json=location())

    client = OpenMeteoClient(transport=httpx.MockTransport(handler), sleep=waits.append)

    assert len(client.forecasts([CHICAGO])) == 1
    assert waits == [0.5]


def test_gives_up_after_three_attempts() -> None:
    waits: list[float] = []
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"error": True})

    client = OpenMeteoClient(transport=httpx.MockTransport(handler), sleep=waits.append)

    with pytest.raises(WeatherError):
        client.forecasts([CHICAGO])
    assert calls == 3
    assert waits == [0.5, 1.5]


@pytest.mark.parametrize("status", [400, 429])
def test_rejected_requests_are_not_retried(status: int) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, json={"error": True, "reason": "No"})

    with pytest.raises(WeatherError):
        client_with(handler).forecasts([CHICAGO])
    assert calls == 1


def test_rate_limit_tells_the_user_to_wait() -> None:
    with pytest.raises(WeatherError, match="try again in a minute"):
        client_returning({"error": True}, status=429).forecasts([CHICAGO])


@pytest.mark.parametrize(
    "body",
    [
        {},
        [],
        [location(), location()],
        {"hourly": {}},
        location(time=[]),
        location(time=[], wind_speed_10m=[], rain=[], showers=[], snowfall=[]),
        location(time=[FIRST_HOUR, FIRST_HOUR + 7200]),
        location(wind_speed_10m=[1.0]),
        location(snowfall=[1.0]),
        location(rain=[0.0]),
        location(rain=[0.0, 0.0, 0.0]),
        location(wind_speed_10m=[-1.0, 0.0]),
        location(snowfall=[-0.1, 0.0]),
        location(rain=["wet", 0.0]),
        {"hourly": location()["hourly"]},
        {**location(), "timezone": "Mars/Olympus_Mons"},
    ],
)
def test_malformed_responses_raise_weather_error(body: Any) -> None:
    with pytest.raises(WeatherError):
        client_returning(body).forecasts([CHICAGO])


def test_not_a_number_is_rejected() -> None:
    client = client_with(
        lambda request: httpx.Response(
            200,
            content=json.dumps(location(wind_speed_10m=[math.nan, 0.0])),
            headers={"content-type": "application/json"},
        )
    )

    with pytest.raises(WeatherError):
        client.forecasts([CHICAGO])


def test_non_json_response_raises_weather_error() -> None:
    client = client_with(lambda request: httpx.Response(200, text="<html>"))

    with pytest.raises(WeatherError):
        client.forecasts([CHICAGO])


def test_shared_client_is_reused() -> None:
    get_weather_client.cache_clear()

    assert get_weather_client() is get_weather_client()

    get_weather_client.cache_clear()
