"""Request limits per connection. The rates are set in settings.REST_FRAMEWORK."""

from rest_framework.throttling import AnonRateThrottle


class GeocodeThrottle(AnonRateThrottle):
    scope = "geocode"


class TimezoneThrottle(AnonRateThrottle):
    scope = "timezone"


class TripPlanThrottle(AnonRateThrottle):
    scope = "trip_plan"


class HeatmapThrottle(AnonRateThrottle):
    scope = "heatmap"
