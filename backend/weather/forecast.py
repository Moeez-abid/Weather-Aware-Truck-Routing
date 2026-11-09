"""Hourly forecast for one location, and the weather it gives at a moment in time."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from risk.classification import WeatherSample

SECONDS_PER_HOUR = 3600


class WeatherError(Exception):
    """The weather could not be retrieved. The message is safe to show to users."""


class ForecastUnavailableError(WeatherError):
    """The forecast has no usable data for the requested time."""


def _value(series: Sequence[float | None], index: int) -> float:
    # Missing weather must stop the calculation, because treating it as calm would report Low risk.
    if 0 <= index < len(series) and (value := series[index]) is not None:
        return value
    raise ForecastUnavailableError("The weather forecast does not cover this time.")


@dataclass(frozen=True, slots=True)
class LocationForecast:
    """Hourly values, where index 0 is `first_hour` (Unix seconds) and each step is one hour.

    Wind is the instant value at that hour. Rain and snow are totals for the hour ending at
    that timestamp, so the value for 10:00-11:00 is stored at 11:00.
    """

    timezone: str
    first_hour: int
    wind_mph: tuple[float | None, ...]
    rain_in_hr: tuple[float | None, ...]
    snow_in_hr: tuple[float | None, ...]

    def sample_at(self, when: datetime) -> WeatherSample:
        if when.tzinfo is None:
            raise ValueError("Forecast lookup time must include a timezone.")

        hour, seconds_into_hour = divmod(when.timestamp() - self.first_hour, SECONDS_PER_HOUR)
        hour = int(hour)

        wind = _value(self.wind_mph, hour)
        if seconds_into_hour:
            wind += (_value(self.wind_mph, hour + 1) - wind) * seconds_into_hour / SECONDS_PER_HOUR

        return WeatherSample(
            wind_mph=wind,
            rain_in_hr=_value(self.rain_in_hr, hour + 1),
            snow_in_hr=_value(self.snow_in_hr, hour + 1),
        )
