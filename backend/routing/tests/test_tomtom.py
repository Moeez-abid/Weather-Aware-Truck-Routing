import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from routing.domain import LatLon, NoRouteError, ProviderError, RouteTooComplexError
from routing.tomtom import TomTomClient, get_tomtom_client, gross_weight_kg

FIXTURES = Path(__file__).parent / "fixtures"
API_KEY = "secret-key"
ORIGIN = LatLon(44.9778, -93.265)
DESTINATION = LatLon(44.974, -93.2277)
DEPARTURE = datetime(2026, 11, 10, 15, 30, tzinfo=UTC)


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def client_returning(
    body: Any, status: int = 200, seen: list[httpx.Request] | None = None
) -> TomTomClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=body)

    return TomTomClient(API_KEY, transport=httpx.MockTransport(handler))


def client_raising(error: Callable[[httpx.Request], Exception]) -> TomTomClient:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error(request)

    return TomTomClient(API_KEY, transport=httpx.MockTransport(handler))


def route_call(client: TomTomClient, **kwargs: Any) -> list[Any]:
    return client.calculate_routes(ORIGIN, DESTINATION, DEPARTURE, 40_000, **kwargs)


def test_parses_all_routes_from_a_real_response() -> None:
    routes = route_call(client_returning(fixture("tomtom_routes")), max_alternatives=2)

    assert [len(route.points) for route in routes] == [181, 143, 162]
    assert [route.distance_m for route in routes] == [5594, 4381, 4065]
    assert [route.duration_s for route in routes] == [615, 569, 626]
    assert routes[0].points[0] == LatLon(44.97777, -93.26503)


def test_timing_spans_each_route() -> None:
    for route in route_call(client_returning(fixture("tomtom_routes"))):
        assert route.timing[0].point_index == 0
        assert route.timing[0].distance_m == 0
        assert route.timing[0].elapsed_s == 0
        assert route.timing[-1].point_index == len(route.points) - 1
        assert route.timing[-1].distance_m == route.distance_m
        assert route.timing[-1].elapsed_s == route.duration_s


def test_route_through_a_waypoint_keeps_timing_aligned_with_points() -> None:
    route = route_call(client_returning(fixture("tomtom_via_route")))[0]

    assert len(route.points) == 325
    assert route.timing[-1].point_index == 324
    assert route.points[114] == route.points[115]


def test_gross_weight_adds_the_empty_truck() -> None:
    assert gross_weight_kg(40_000) == 33_112
    assert gross_weight_kg(0) == 14_969


def test_route_request_asks_for_a_truck_route() -> None:
    seen: list[httpx.Request] = []

    route_call(client_returning(fixture("tomtom_routes"), seen=seen), max_alternatives=2)

    request = seen[0]
    assert request.url.path == (
        "/routing/1/calculateRoute/44.977800,-93.265000:44.974000,-93.227700/json"
    )
    assert request.url.params["travelMode"] == "truck"
    assert request.url.params["vehicleCommercial"] == "true"
    assert request.url.params["vehicleWeight"] == "33112"
    assert request.url.params["vehicleMaxSpeed"] == "105"
    assert request.url.params["maxAlternatives"] == "2"
    assert request.url.params["departAt"] == "2026-11-10T15:30:00Z"
    assert request.url.params["instructionsType"] == "coded"
    assert request.url.params["key"] == API_KEY


def test_waypoint_goes_between_origin_and_destination() -> None:
    seen: list[httpx.Request] = []

    route_call(client_returning(fixture("tomtom_via_route"), seen=seen), via=LatLon(44.965, -93.245))

    assert seen[0].url.path == (
        "/routing/1/calculateRoute/"
        "44.977800,-93.265000:44.965000,-93.245000:44.974000,-93.227700/json"
    )


def test_departure_is_converted_to_utc() -> None:
    seen: list[httpx.Request] = []
    chicago = timezone(timedelta(hours=-6))

    client_returning(fixture("tomtom_routes"), seen=seen).calculate_routes(
        ORIGIN, DESTINATION, datetime(2026, 11, 10, 9, 30, tzinfo=chicago), 40_000
    )

    assert seen[0].url.params["departAt"] == "2026-11-10T15:30:00Z"


def test_departure_without_timezone_is_rejected() -> None:
    with pytest.raises(ValueError):
        client_returning(fixture("tomtom_routes")).calculate_routes(
            ORIGIN, DESTINATION, datetime(2026, 11, 10, 9, 30), 40_000
        )


@pytest.mark.parametrize("code", ["NO_ROUTE_FOUND", "MAP_MATCHING_FAILURE"])
def test_undrivable_trips_raise_no_route(code: str) -> None:
    body = {"formatVersion": "0.0.12", "detailedError": {"message": "Engine error", "code": code}}

    with pytest.raises(NoRouteError):
        route_call(client_returning(body, status=400))


def test_empty_route_list_raises_no_route() -> None:
    with pytest.raises(NoRouteError):
        route_call(client_returning({"routes": []}))


@pytest.mark.parametrize("status", [400, 403, 429, 500, 503])
def test_other_http_errors_raise_provider_error(status: int) -> None:
    with pytest.raises(ProviderError):
        route_call(client_returning({"detailedError": {"code": "OTHER"}}, status=status))


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"routes": [{}]},
        {"routes": [{"legs": [], "summary": {}, "guidance": {"instructions": []}}]},
    ],
)
def test_malformed_routes_raise_provider_error(body: dict[str, Any]) -> None:
    with pytest.raises(ProviderError):
        route_call(client_returning(body))


def test_route_without_matching_timing_is_rejected() -> None:
    body = fixture("tomtom_routes")
    body["routes"][0]["guidance"]["instructions"].pop()

    with pytest.raises(ProviderError):
        route_call(client_returning(body))


@pytest.mark.parametrize("field", ["pointIndex", "routeOffsetInMeters", "travelTimeInSeconds"])
def test_route_timing_that_goes_backwards_is_rejected(field: str) -> None:
    body = fixture("tomtom_routes")
    instructions = body["routes"][0]["guidance"]["instructions"]
    instructions[2][field] = instructions[1][field] - 1

    with pytest.raises(ProviderError):
        route_call(client_returning(body))


def test_non_json_response_raises_provider_error() -> None:
    client = TomTomClient(
        API_KEY, transport=httpx.MockTransport(lambda request: httpx.Response(200, text="<html>"))
    )

    with pytest.raises(ProviderError):
        route_call(client)


def test_network_errors_do_not_expose_the_api_key() -> None:
    client = client_raising(lambda request: httpx.ConnectError(f"failed: {request.url}"))

    with pytest.raises(ProviderError) as caught:
        route_call(client)

    assert API_KEY not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


def test_geocode_parses_a_real_response() -> None:
    places = client_returning(fixture("tomtom_geocode")).geocode("Dallas")

    assert [place.label for place in places] == ["Dallas, TX", "Dallas, GA", "Dallas, NC"]
    assert places[0].position == LatLon(32.7779765, -96.7962148)


def test_geocode_request_is_encoded_and_searches_every_country_in_english() -> None:
    seen: list[httpx.Request] = []

    client_returning({"results": []}, seen=seen).geocode("A/B, TX?")

    assert seen[0].url.raw_path.startswith(b"/search/2/geocode/A%20B%2C%20TX%3F.json?")
    assert seen[0].url.params["typeahead"] == "true"
    assert seen[0].url.params["language"] == "en-US"
    assert "countrySet" not in seen[0].url.params


def geocode_result(label: str, country_code: str, country: str) -> dict[str, Any]:
    return {
        "address": {"freeformAddress": label, "countryCode": country_code, "country": country},
        "position": {"lat": 1, "lon": 2},
    }


def test_geocode_adds_the_country_outside_the_us() -> None:
    response = {
        "results": [
            geocode_result("Islamabad, Punjab", "PK", "Pakistan"),
            geocode_result("Islamabad, Madarihat, West Bengal", "IN", "India"),
            geocode_result("Paris", "FR", "France"),
            geocode_result("Paris, TX", "US", "United States"),
        ]
    }

    places = client_returning(response).geocode("Islamabad")

    assert [place.label for place in places] == [
        "Islamabad, Punjab, Pakistan",
        "Islamabad, Madarihat, West Bengal, India",
        "Paris, France",
        "Paris, TX",
    ]


def test_geocode_keeps_the_label_when_the_country_is_missing() -> None:
    result = {"address": {"freeformAddress": "Somewhere"}, "position": {"lat": 1, "lon": 2}}

    assert client_returning({"results": [result]}).geocode("Somewhere")[0].label == "Somewhere"


def test_geocode_removes_duplicate_labels() -> None:
    result = {"address": {"freeformAddress": "Dallas, TX"}, "position": {"lat": 1, "lon": 2}}

    assert len(client_returning({"results": [result, result]}).geocode("Dallas")) == 1


def test_malformed_geocode_raises_provider_error() -> None:
    with pytest.raises(ProviderError):
        client_returning({"results": [{"address": {}}]}).geocode("Dallas")


def test_missing_api_key_raises_provider_error(settings: Any) -> None:
    settings.TOMTOM_API_KEY = ""
    get_tomtom_client.cache_clear()

    with pytest.raises(ProviderError):
        get_tomtom_client()

    get_tomtom_client.cache_clear()


def test_a_timeout_says_the_service_was_slow() -> None:
    client = client_raising(lambda request: httpx.ReadTimeout("slow", request=request))

    with pytest.raises(ProviderError, match="took too long"):
        route_call(client)


def test_a_route_request_can_be_given_its_own_time_limit() -> None:
    seen: list[httpx.Request] = []
    client = client_returning(fixture("tomtom_routes"), seen=seen)

    route_call(client, timeout_s=12.5)

    assert seen[0].extensions["timeout"]["read"] == 12.5


def test_geocode_turns_slashes_into_spaces() -> None:
    seen: list[httpx.Request] = []

    client_returning({"results": []}, seen=seen).geocode("../../etc\\x")

    assert seen[0].url.raw_path.startswith(b"/search/2/geocode/..%20..%20etc%20x.json?")


def test_geocode_marks_cities() -> None:
    city = {**geocode_result("Quetta, Baluchistan", "PK", "Pakistan"), "entityType": "Municipality"}
    street = geocode_result("Quetta Road, Somewhere", "PK", "Pakistan")

    places = client_returning({"results": [city, street]}).geocode("Quetta")

    assert [place.is_city for place in places] == [True, False]


def test_a_route_too_long_to_calculate_has_its_own_error() -> None:
    body = {"detailedError": {"code": "COMPUTE_TIME_LIMIT_EXCEEDED"}}

    with pytest.raises(RouteTooComplexError, match="too long for the routing service"):
        route_call(client_returning(body, status=500))
