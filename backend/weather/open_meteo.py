"""Open-Meteo forecast client.

Open-Meteo charges one call per location, up to its free limit of 600 per minute and
5,000 per hour, so forecasts are cached and repeated trips cost nothing. The charge does
not depend on the forecast length up to 14 days, so the full 14 days are always fetched
and one cached entry serves any departure time.
"""

import logging
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from itertools import batched, pairwise
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from django.core.cache import cache

from routing.domain import LatLon
from weather.forecast import SECONDS_PER_HOUR, LocationForecast, WeatherError

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS = 30
FORECAST_DAYS = 14
BATCH_SIZE = 100
MAX_PARALLEL_REQUESTS = 4
RETRY_DELAYS_SECONDS = (0.5, 1.5)
CACHE_SECONDS = 15 * 60

INVALID_RESPONSE = "The weather service returned an invalid response."


def snap_position(position: LatLon) -> LatLon:
    # 0.01 degrees is about 0.7 miles, which is finer than any forecast model.
    return LatLon(round(position.lat, 2), round(position.lon, 2))


def _cache_key(position: LatLon) -> str:
    return f"open-meteo:{position.lat:.2f},{position.lon:.2f}"


def _combined_rain(rain: float | None, showers: float | None) -> float | None:
    if rain is None or showers is None:
        return None
    # Rounded because 0.09 + 0.01 is 0.09999999999999999 in floats, one band too low.
    return round(rain + showers, 3)


def _parse_location(raw: dict[str, Any]) -> LocationForecast:
    hourly = raw["hourly"]
    times = hourly["time"]
    if not times or any(later - earlier != SECONDS_PER_HOUR for earlier, later in pairwise(times)):
        raise ValueError("Forecast hours must be consecutive.")

    wind = tuple(hourly["wind_speed_10m"])
    rain = tuple(
        _combined_rain(*pair) for pair in zip(hourly["rain"], hourly["showers"], strict=True)
    )
    snow = tuple(hourly["snowfall"])
    for series in (wind, rain, snow):
        if len(series) != len(times):
            raise ValueError("Forecast series must match the forecast hours.")
        if any(value is not None and not value >= 0 for value in series):
            raise ValueError("Forecast values must not be negative.")

    ZoneInfo(raw["timezone"])  # Raises for a name that could not be used to show local times.

    return LocationForecast(
        timezone=raw["timezone"],
        first_hour=times[0],
        wind_mph=wind,
        rain_in_hr=rain,
        snow_in_hr=snow,
    )


class OpenMeteoClient:
    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = httpx.Client(timeout=TIMEOUT_SECONDS, transport=transport)
        self._sleep = sleep

    def _request(self, params: dict[str, Any]) -> Any:
        for delay in (*RETRY_DELAYS_SECONDS, None):
            try:
                response = self._http.get(FORECAST_URL, params=params)
            except httpx.HTTPError:
                failure = "The weather service could not be reached."
            else:
                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError:
                        raise WeatherError(INVALID_RESPONSE) from None

                logger.warning("Open-Meteo returned HTTP %s", response.status_code)
                # The limit resets once a minute, which is too long to hold a request open.
                if response.status_code == 429:
                    raise WeatherError(
                        "The weather service limit has been reached. Please try again in a minute."
                    )
                if response.status_code < 500:
                    raise WeatherError("The weather service rejected the request.")
                failure = "The weather service returned an error."

            if delay is None:
                raise WeatherError(failure)
            self._sleep(delay)

        raise AssertionError("unreachable")

    def _fetch_batch(self, positions: Sequence[LatLon]) -> list[LocationForecast]:
        data = self._request(
            {
                "latitude": ",".join(f"{position.lat:.2f}" for position in positions),
                "longitude": ",".join(f"{position.lon:.2f}" for position in positions),
                "hourly": "wind_speed_10m,rain,showers,snowfall",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "auto",
                "timeformat": "unixtime",
                "forecast_days": FORECAST_DAYS,
            }
        )
        # Open-Meteo returns a bare object instead of a list for a single location.
        locations = data if isinstance(data, list) else [data]
        if len(locations) != len(positions):
            raise WeatherError(INVALID_RESPONSE)
        try:
            return [_parse_location(location) for location in locations]
        except (KeyError, TypeError, ValueError):
            raise WeatherError(INVALID_RESPONSE) from None

    def forecasts(self, positions: Sequence[LatLon]) -> list[LocationForecast]:
        """Return one forecast per position, in the same order."""
        snapped = [snap_position(position) for position in positions]
        keys = {position: _cache_key(position) for position in snapped}

        cached = cache.get_many(keys.values())
        found = {position: cached[key] for position, key in keys.items() if key in cached}

        missing = [position for position in keys if position not in found]
        batches = [list(batch) for batch in batched(missing, BATCH_SIZE)]
        if batches:
            with ThreadPoolExecutor(MAX_PARALLEL_REQUESTS) as pool:
                for batch, forecasts in zip(batches, pool.map(self._fetch_batch, batches), strict=True):
                    fresh = dict(zip(batch, forecasts, strict=True))
                    # Saved per batch so that a later failure doesn't waste the calls already spent.
                    cache.set_many({keys[position]: fresh[position] for position in batch}, CACHE_SECONDS)
                    found.update(fresh)

        return [found[position] for position in snapped]


@lru_cache(maxsize=1)
def get_weather_client() -> OpenMeteoClient:
    return OpenMeteoClient()
