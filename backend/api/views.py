from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from routing.domain import RoutingError
from routing.tomtom import get_tomtom_client

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
