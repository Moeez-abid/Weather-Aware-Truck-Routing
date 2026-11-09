from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from risk.classification import WeatherSample
from weather.forecast import ForecastUnavailableError, LocationForecast

START = datetime(2026, 11, 10, 0, 0, tzinfo=UTC)


def forecast(**overrides: Any) -> LocationForecast:
    values: dict[str, Any] = {
        "timezone": "America/Chicago",
        "first_hour": int(START.timestamp()),
        "wind_mph": (10.0, 20.0, 40.0, 30.0),
        "rain_in_hr": (0.0, 0.11, 0.22, 0.33),
        "snow_in_hr": (0.0, 0.5, 1.5, 2.5),
    }
    return LocationForecast(**{**values, **overrides})


def at(hours: float) -> datetime:
    return START + timedelta(hours=hours)


def test_exact_hour_uses_the_wind_at_that_hour() -> None:
    assert forecast().sample_at(at(1)).wind_mph == 20


def test_wind_is_interpolated_between_hours() -> None:
    assert forecast().sample_at(at(1.25)).wind_mph == pytest.approx(25)
    assert forecast().sample_at(at(2.5)).wind_mph == pytest.approx(35)


def test_wind_on_the_hour_does_not_need_the_next_hour() -> None:
    sample = forecast(wind_mph=(10.0, 20.0, None, None)).sample_at(at(1))

    assert sample.wind_mph == 20


@pytest.mark.parametrize(
    ("hours", "rain", "snow"),
    [
        (0, 0.11, 0.5),
        (0.5, 0.11, 0.5),
        (0.99, 0.11, 0.5),
        (1, 0.22, 1.5),
        (2.5, 0.33, 2.5),
    ],
)
def test_precipitation_comes_from_the_hour_containing_the_time(
    hours: float, rain: float, snow: float
) -> None:
    sample = forecast().sample_at(at(hours))

    assert sample.rain_in_hr == rain
    assert sample.snow_in_hr == snow


def test_returns_a_weather_sample() -> None:
    assert forecast().sample_at(at(0)) == WeatherSample(10.0, 0.11, 0.5)


def test_time_is_compared_as_an_instant_not_a_wall_clock() -> None:
    chicago = timezone(timedelta(hours=-6))

    local = forecast().sample_at(datetime(2026, 11, 9, 19, 0, tzinfo=chicago))

    assert local == forecast().sample_at(at(1))


def test_naive_time_is_rejected() -> None:
    with pytest.raises(ValueError):
        forecast().sample_at(datetime(2026, 11, 10, 1, 0))


@pytest.mark.parametrize("hours", [-0.01, -1, 3, 3.5, 100])
def test_times_outside_the_forecast_are_unavailable(hours: float) -> None:
    with pytest.raises(ForecastUnavailableError):
        forecast().sample_at(at(hours))


@pytest.mark.parametrize(
    ("field", "series", "hours"),
    [
        ("wind_mph", (10.0, None, 40.0, 30.0), 1),
        ("wind_mph", (10.0, 20.0, None, 30.0), 1.5),
        ("rain_in_hr", (0.0, 0.1, None, 0.3), 1),
        ("snow_in_hr", (0.0, 0.5, None, 2.5), 1.5),
    ],
)
def test_missing_values_are_never_treated_as_calm(
    field: str, series: tuple[float | None, ...], hours: float
) -> None:
    with pytest.raises(ForecastUnavailableError):
        forecast(**{field: series}).sample_at(at(hours))
