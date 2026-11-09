from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from api.serializers import TripPlanRequestSerializer, to_trip_request, trip_plan_payload
from routing.domain import NoRouteError, RoutingError
from routing.tomtom import get_tomtom_client
from trips.planner import InvalidDepartureError, plan_trip
from weather.forecast import ForecastUnavailableError, WeatherError
from weather.open_meteo import get_weather_client

GEOCODE_MIN_QUERY_LENGTH = 2
GEOCODE_MAX_QUERY_LENGTH = 200


@api_view(["GET"])
def health(request: Request) -> Response:
    return Response({"status": "ok"})


@api_view(["GET"])
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


@api_view(["POST"])
def trip_plan(request: Request) -> Response:
    serializer = TripPlanRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"error": "Please check the trip details.", "fields": serializer.errors}, status=400
        )

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
