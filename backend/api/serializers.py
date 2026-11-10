"""Validate trip requests and shape trip plans for the frontend."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from rest_framework import serializers

from risk.classification import RiskLevel
from routing.checkpoints import METERS_PER_MILE
from routing.domain import LatLon
from routing.geometry import haversine_m, simplify_path
from trips.heatmap import Heatmap
from trips.planner import (
    CHECKPOINT_INTERVALS_MILES,
    PlannedCheckpoint,
    PlannedRoute,
    TripPlan,
    TripRequest,
)

DEFAULT_INTERVAL_MILES = 25
MAX_LOAD_LB = 200_000
MIN_TRIP_METERS = METERS_PER_MILE
MAX_ROUTES = 3
MAX_PATH_POINTS = 20_000
# Web Mercator can't represent the poles, and no road comes close to this latitude.
MAX_PATH_LATITUDE = 85

# About 10 meters, which still follows the road at street zoom and removes about 90% of the points.
GEOMETRY_TOLERANCE_DEGREES = 0.0001
# About 0.7 miles. The frontend sends this lighter line back to request the heatmap, whose
# cells are at least 7 miles wide.
CORRIDOR_TOLERANCE_DEGREES = 0.01


def _parse_departure(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise serializers.ValidationError("Enter a valid date and time.") from None


class PositionSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)


class TripPlanRequestSerializer(serializers.Serializer):
    origin = PositionSerializer()
    destination = PositionSerializer()
    departure = serializers.CharField(help_text="Local time at the origin, without an offset.")
    load_lb = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LB)
    interval_miles = serializers.ChoiceField(
        choices=CHECKPOINT_INTERVALS_MILES, default=DEFAULT_INTERVAL_MILES
    )

    def validate_departure(self, value: str) -> datetime:
        departure = _parse_departure(value)
        if departure.tzinfo is not None:
            raise serializers.ValidationError("Send the local time at the origin, without an offset.")
        return departure

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if haversine_m(LatLon(**attrs["origin"]), LatLon(**attrs["destination"])) < MIN_TRIP_METERS:
            raise serializers.ValidationError(
                {"destination": ["Destination must be at least a mile from the origin."]}
            )
        return attrs


class PathField(serializers.Field):
    """A route line as sent by the trip plan: a list of [longitude, latitude] pairs."""

    default_error_messages = {"invalid": "Enter a list of [longitude, latitude] points."}

    def to_internal_value(self, data: Any) -> list[LatLon]:
        if not isinstance(data, list) or not 2 <= len(data) <= MAX_PATH_POINTS:
            self.fail("invalid")
        try:
            points = [LatLon(lat, lon) for lon, lat in data]
            valid = all(
                -MAX_PATH_LATITUDE <= point.lat <= MAX_PATH_LATITUDE and -180 <= point.lon <= 180
                for point in points
            )
        except (TypeError, ValueError):
            valid = False
        if not valid:
            self.fail("invalid")
        return points


class HeatmapRequestSerializer(serializers.Serializer):
    routes = serializers.ListField(child=PathField(), min_length=1, max_length=MAX_ROUTES)
    departure = serializers.CharField(help_text="The departure returned with the trip plan.")
    load_lb = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LB)

    def validate_departure(self, value: str) -> datetime:
        departure = _parse_departure(value)
        if departure.tzinfo is None:
            raise serializers.ValidationError("Include the UTC offset.")
        return departure


def to_trip_request(data: dict[str, Any]) -> TripRequest:
    return TripRequest(
        origin=LatLon(**data["origin"]),
        destination=LatLon(**data["destination"]),
        local_departure=data["departure"],
        load_lb=data["load_lb"],
        interval_miles=data["interval_miles"],
    )


def _level_name(level: RiskLevel) -> str:
    return level.name.lower()


def _local_iso(moment: datetime, timezone: str) -> str:
    return moment.astimezone(ZoneInfo(timezone)).replace(microsecond=0).isoformat()


def _checkpoint_payload(item: PlannedCheckpoint) -> dict[str, Any]:
    checkpoint = item.checkpoint
    return {
        "mile": round(checkpoint.mile, 1),
        "lat": round(checkpoint.position.lat, 5),
        "lon": round(checkpoint.position.lon, 5),
        "eta": _local_iso(checkpoint.eta, item.timezone),
        "timezone": item.timezone,
        "risk": _level_name(item.risk.level),
        "risk_factors": {
            "wind": _level_name(item.risk.wind),
            "rain": _level_name(item.risk.rain),
            "snow": _level_name(item.risk.snow),
        },
        "weather": {
            "wind_mph": round(item.weather.wind_mph, 2),
            "rain_in_hr": item.weather.rain_in_hr,
            "snow_in_hr": item.weather.snow_in_hr,
        },
    }


def _path_payload(route: PlannedRoute, tolerance_degrees: float) -> list[list[float]]:
    return [
        [round(point.lon, 5), round(point.lat, 5)]
        for point in simplify_path(route.route.points, tolerance_degrees)
    ]


def _route_payload(route: PlannedRoute) -> dict[str, Any]:
    last = route.checkpoints[-1]
    return {
        "id": route.id,
        "distance_miles": round(route.summary.total_miles, 1),
        "duration_seconds": route.summary.duration_seconds,
        "arrival": _local_iso(last.checkpoint.eta, last.timezone),
        "average_risk": route.summary.average_risk,
        "miles_by_risk": {
            _level_name(level): round(miles, 1)
            for level, miles in route.summary.miles_by_level.items()
        },
        "geometry": _path_payload(route, GEOMETRY_TOLERANCE_DEGREES),
        "corridor": _path_payload(route, CORRIDOR_TOLERANCE_DEGREES),
        "checkpoints": [_checkpoint_payload(item) for item in route.checkpoints],
    }


def trip_plan_payload(plan: TripPlan) -> dict[str, Any]:
    return {
        "departure": _local_iso(plan.departure, plan.timezone),
        "timezone": plan.timezone,
        "recommended_route_id": plan.recommendation.recommended_route_id,
        "ranked_route_ids": plan.recommendation.ranked_route_ids,
        "routes": [_route_payload(route) for route in plan.routes],
    }


def heatmap_payload(heatmap: Heatmap) -> dict[str, Any]:
    return {
        "columns": heatmap.columns,
        "rows": heatmap.rows,
        "west": round(heatmap.west, 6),
        "south": round(heatmap.south, 6),
        "east": round(heatmap.east, 6),
        "north": round(heatmap.north, 6),
        "cells": heatmap.cells,
        "frames": heatmap.frames,
    }
