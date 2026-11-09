"""Weather risk rules for a single checkpoint.

The thresholds come from the assessment brief. The brief's bands share their
edges (0.25 in/hr of rain is in both Moderate and High), so a value on an edge
goes to the higher band. The exception is the top of the rain and snow scales,
where No Travel is defined as strictly greater than the limit.
"""

import math
from dataclasses import dataclass
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


@dataclass(frozen=True)
class Thresholds:
    moderate: float
    high: float
    severe: float
    no_travel: float
    no_travel_includes_limit: bool

    def classify(self, value: float) -> RiskLevel:
        if value < self.moderate:
            return RiskLevel.LOW
        if value < self.high:
            return RiskLevel.MODERATE
        if value < self.severe:
            return RiskLevel.HIGH
        if value > self.no_travel or (self.no_travel_includes_limit and value == self.no_travel):
            return RiskLevel.NO_TRAVEL
        return RiskLevel.SEVERE


WIND_MPH = Thresholds(moderate=25, high=35, severe=45, no_travel=55, no_travel_includes_limit=True)
RAIN_IN_HR = Thresholds(
    moderate=0.10, high=0.25, severe=0.50, no_travel=1.00, no_travel_includes_limit=False
)
SNOW_IN_HR = Thresholds(
    moderate=0.5, high=1.0, severe=2.0, no_travel=3.0, no_travel_includes_limit=False
)

SEVERE_WIND_NO_TRAVEL_ABOVE_LB = 30_000
HIGH_WIND_SEVERE_ABOVE_LB = 40_000


@dataclass(frozen=True)
class WeatherSample:
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float

    def __post_init__(self) -> None:
        # Bad readings must fail loudly. A missing value must never pass as Low risk.
        for value in (self.wind_mph, self.rain_in_hr, self.snow_in_hr):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid weather reading: {value!r}")


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    wind: RiskLevel
    rain: RiskLevel
    snow: RiskLevel


def wind_risk(wind_mph: float, load_lb: float) -> RiskLevel:
    """Classify wind, then apply the load rules for the wind bands they cover."""
    level = WIND_MPH.classify(wind_mph)
    if level is RiskLevel.SEVERE and load_lb > SEVERE_WIND_NO_TRAVEL_ABOVE_LB:
        return RiskLevel.NO_TRAVEL
    if level is RiskLevel.HIGH and load_lb > HIGH_WIND_SEVERE_ABOVE_LB:
        return RiskLevel.SEVERE
    return level


def assess(sample: WeatherSample, load_lb: float) -> RiskAssessment:
    """Return each factor's level and the worst of them as the overall level."""
    if not math.isfinite(load_lb) or load_lb < 0:
        raise ValueError(f"Invalid load weight: {load_lb!r}")

    wind = wind_risk(sample.wind_mph, load_lb)
    rain = RAIN_IN_HR.classify(sample.rain_in_hr)
    snow = SNOW_IN_HR.classify(sample.snow_in_hr)
    return RiskAssessment(level=max(wind, rain, snow), wind=wind, rain=rain, snow=snow)
