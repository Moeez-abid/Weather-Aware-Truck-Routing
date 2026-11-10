from collections.abc import Iterator
from unittest.mock import patch

import pytest
from django.core.cache import cache

from routing.places import City


class NoCities:
    def search(self, query: str) -> list[City]:
        return []


@pytest.fixture(autouse=True)
def offline_city_search() -> Iterator[None]:
    """Address search also asks Open-Meteo for cities. Tests never reach the real service."""
    with patch("api.views.get_city_search", return_value=NoCities()):
        yield


@pytest.fixture(autouse=True)
def empty_cache() -> Iterator[None]:
    """Searches and forecasts are cached, so each test starts without the last one's results."""
    cache.clear()
    yield
    cache.clear()
