from unittest.mock import MagicMock, patch

from django.test import Client

from routing.domain import LatLon, Place, ProviderError


def geocode(**params: str):
    return Client().get("/api/geocode", params)


@patch("api.views.get_tomtom_client")
def test_returns_matching_places(get_client: MagicMock) -> None:
    get_client.return_value.geocode.return_value = [
        Place("Dallas, TX", LatLon(32.77, -96.79)),
    ]

    response = geocode(q="  Dallas ")

    assert response.status_code == 200
    assert response.json() == {"results": [{"label": "Dallas, TX", "lat": 32.77, "lon": -96.79}]}
    get_client.return_value.geocode.assert_called_once_with("Dallas", 5)


@patch("api.views.get_tomtom_client")
def test_short_queries_do_not_call_the_provider(get_client: MagicMock) -> None:
    response = geocode(q="D")

    assert response.status_code == 200
    assert response.json() == {"results": []}
    get_client.assert_not_called()


@patch("api.views.get_tomtom_client")
def test_missing_query_returns_nothing(get_client: MagicMock) -> None:
    assert geocode().json() == {"results": []}
    get_client.assert_not_called()


@patch("api.views.get_tomtom_client")
def test_very_long_queries_are_rejected(get_client: MagicMock) -> None:
    response = geocode(q="x" * 201)

    assert response.status_code == 400
    get_client.assert_not_called()


@patch("api.views.get_tomtom_client")
def test_provider_failure_returns_bad_gateway(get_client: MagicMock) -> None:
    get_client.return_value.geocode.side_effect = ProviderError("The routing service failed.")

    response = geocode(q="Dallas")

    assert response.status_code == 502
    assert response.json() == {"error": "The routing service failed."}
