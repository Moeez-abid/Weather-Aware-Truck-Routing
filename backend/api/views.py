from typing import Any

from rest_framework.decorators import api_view, throttle_classes
from rest_framework.request import Request
from rest_framework.response import Response

from api.throttles import GeocodeThrottle, HeatmapThrottle, TimezoneThrottle, TripPlanThrottle
from api.serializers import (
    HeatmapRequestSerializer,
    PositionSerializer,
    TripPlanRequestSerializer,
    heatmap_payload,
    to_trip_request,
    trip_plan_payload,
)
from routing.domain import LatLon, NoRouteError, RoutingError
from routing.tomtom import get_tomtom_client
from trips.heatmap import build_heatmap
from trips.planner import InvalidDepartureError, plan_trip
from weather.forecast import ForecastUnavailableError, WeatherError
from weather.open_meteo import get_weather_client

GEOCODE_MIN_QUERY_LENGTH = 2
GEOCODE_MAX_QUERY_LENGTH = 200


def _invalid_request(errors: Any) -> Response:
    return Response({"error": "Please check the trip details.", "fields": errors}, status=400)


@api_view(["GET"])
def health(request: Request) -> Response:
    return Response({"status": "ok"})


@api_view(["GET"])
@throttle_classes([GeocodeThrottle])
def geocode(request: Request) -> Response:
    query = request.query_params.get("q", "").strip()
    if len(query) > GEOCODE_MAX_QUERY_LENGTH:
        return Response({"error": "Search text is too long."}, status=400)
    if len(query) < GEOCODE_MIN_QUERY_LENGTH:
        return Response({"results": []})

    try:
        places = get_tomtom_client().geocode(query)
    except RoutingError as error:
        return Response({"error": str(error)}, status=502)

    return Response(
        {
            "results": [
                {"label": place.label, "lat": place.position.lat, "lon": place.position.lon}
                for place in places
            ]
        }
    )


@api_view(["GET"])
@throttle_classes([TimezoneThrottle])
def origin_timezone(request: Request) -> Response:
    """Return a position's timezone, so the form can show and default to the origin's local time."""
    serializer = PositionSerializer(data=request.query_params)
    if not serializer.is_valid():
        return _invalid_request(serializer.errors)

    try:
        forecast = get_weather_client().forecasts([LatLon(**serializer.validated_data)])[0]
    except WeatherError as error:
        return Response({"error": str(error)}, status=502)

    return Response({"timezone": forecast.timezone})


@api_view(["POST"])
@throttle_classes([TripPlanThrottle])
def trip_plan(request: Request) -> Response:
    serializer = TripPlanRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return _invalid_request(serializer.errors)

    try:
        plan = plan_trip(
            to_trip_request(serializer.validated_data), get_tomtom_client(), get_weather_client()
        )
    except InvalidDepartureError as error:
        return Response({"error": str(error), "fields": {"departure": [str(error)]}}, status=400)
    except (NoRouteError, ForecastUnavailableError) as error:
        return Response({"error": str(error)}, status=422)
    except (RoutingError, WeatherError) as error:
        return Response({"error": str(error)}, status=502)

    return Response(trip_plan_payload(plan))


@api_view(["POST"])
@throttle_classes([HeatmapThrottle])
def heatmap(request: Request) -> Response:
    serializer = HeatmapRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return _invalid_request(serializer.errors)

    data = serializer.validated_data
    try:
        result = build_heatmap(data["routes"], data["departure"], data["load_lb"], get_weather_client())
    except WeatherError as error:
        return Response({"error": str(error)}, status=502)

    return Response(heatmap_payload(result))
