import math

import pytest

from risk.classification import (
    RAIN_IN_HR,
    SNOW_IN_HR,
    WIND_MPH,
    RiskLevel,
    WeatherSample,
    assess,
    wind_risk,
)

LOW = RiskLevel.LOW
MODERATE = RiskLevel.MODERATE
HIGH = RiskLevel.HIGH
SEVERE = RiskLevel.SEVERE
NO_TRAVEL = RiskLevel.NO_TRAVEL

CALM = WeatherSample(wind_mph=0, rain_in_hr=0, snow_in_hr=0)


@pytest.mark.parametrize(
    ("wind_mph", "expected"),
    [
        (0, LOW),
        (24.9, LOW),
        (25, MODERATE),
        (34, MODERATE),
        (34.9, MODERATE),
        (35, HIGH),
        (44, HIGH),
        (44.9, HIGH),
        (45, SEVERE),
        (54, SEVERE),
        (54.9, SEVERE),
        (55, NO_TRAVEL),
        (90, NO_TRAVEL),
    ],
)
def test_wind_bands(wind_mph: float, expected: RiskLevel) -> None:
    assert WIND_MPH.classify(wind_mph) is expected


@pytest.mark.parametrize(
    ("rain_in_hr", "expected"),
    [
        (0, LOW),
        (0.09, LOW),
        (0.10, MODERATE),
        (0.24, MODERATE),
        (0.25, HIGH),
        (0.49, HIGH),
        (0.50, SEVERE),
        (0.99, SEVERE),
        (1.00, SEVERE),
        (1.01, NO_TRAVEL),
    ],
)
def test_rain_bands(rain_in_hr: float, expected: RiskLevel) -> None:
    assert RAIN_IN_HR.classify(rain_in_hr) is expected


@pytest.mark.parametrize(
    ("snow_in_hr", "expected"),
    [
        (0, LOW),
        (0.49, LOW),
        (0.5, MODERATE),
        (0.99, MODERATE),
        (1.0, HIGH),
        (1.99, HIGH),
        (2.0, SEVERE),
        (2.99, SEVERE),
        (3.0, SEVERE),
        (3.01, NO_TRAVEL),
    ],
)
def test_snow_bands(snow_in_hr: float, expected: RiskLevel) -> None:
    assert SNOW_IN_HR.classify(snow_in_hr) is expected


@pytest.mark.parametrize(
    ("wind_mph", "load_lb", "expected"),
    [
        # 55 mph and above is No Travel for any load.
        (55, 0, NO_TRAVEL),
        (70, 80_000, NO_TRAVEL),
        # 45-54 mph is No Travel only above 30,000 lb.
        (45, 30_000, SEVERE),
        (45, 30_001, NO_TRAVEL),
        (54, 30_000, SEVERE),
        (54.9, 30_001, NO_TRAVEL),
        # 35-44 mph is Severe only above 40,000 lb.
        (35, 40_000, HIGH),
        (35, 40_001, SEVERE),
        (44, 40_000, HIGH),
        (44.9, 40_001, SEVERE),
        # A load between the two limits changes nothing at 35-44 mph.
        (40, 35_000, HIGH),
        # Below 35 mph the load rules do not apply.
        (34.9, 80_000, MODERATE),
        (24.9, 80_000, LOW),
    ],
)
def test_load_rules(wind_mph: float, load_lb: float, expected: RiskLevel) -> None:
    assert wind_risk(wind_mph, load_lb) is expected


@pytest.mark.parametrize(
    ("sample", "expected"),
    [
        (CALM, LOW),
        (WeatherSample(wind_mph=30, rain_in_hr=0, snow_in_hr=0), MODERATE),
        (WeatherSample(wind_mph=30, rain_in_hr=0.3, snow_in_hr=0), HIGH),
        (WeatherSample(wind_mph=0, rain_in_hr=0.3, snow_in_hr=2.5), SEVERE),
        (WeatherSample(wind_mph=0, rain_in_hr=1.5, snow_in_hr=0), NO_TRAVEL),
        (WeatherSample(wind_mph=0, rain_in_hr=0, snow_in_hr=3.5), NO_TRAVEL),
    ],
)
def test_overall_level_is_the_worst_factor(sample: WeatherSample, expected: RiskLevel) -> None:
    assert assess(sample, load_lb=10_000).level is expected


def test_assessment_reports_each_factor() -> None:
    sample = WeatherSample(wind_mph=30, rain_in_hr=0.3, snow_in_hr=2.5)

    result = assess(sample, load_lb=10_000)

    assert (result.wind, result.rain, result.snow) == (MODERATE, HIGH, SEVERE)


def test_load_rule_can_set_the_overall_level() -> None:
    sample = WeatherSample(wind_mph=50, rain_in_hr=0.3, snow_in_hr=0)

    assert assess(sample, load_lb=30_000).level is SEVERE
    assert assess(sample, load_lb=30_001).level is NO_TRAVEL


def test_load_rule_does_not_lower_a_worse_factor() -> None:
    sample = WeatherSample(wind_mph=40, rain_in_hr=1.5, snow_in_hr=0)

    assert assess(sample, load_lb=40_001).level is NO_TRAVEL


def test_risk_levels_sort_by_severity() -> None:
    assert [int(level) for level in (LOW, MODERATE, HIGH, SEVERE, NO_TRAVEL)] == [0, 1, 2, 3, 4]


@pytest.mark.parametrize("bad_value", [-1, math.nan, math.inf])
@pytest.mark.parametrize("field", ["wind_mph", "rain_in_hr", "snow_in_hr"])
def test_invalid_weather_is_rejected(field: str, bad_value: float) -> None:
    readings = {"wind_mph": 0.0, "rain_in_hr": 0.0, "snow_in_hr": 0.0, field: bad_value}

    with pytest.raises(ValueError):
        WeatherSample(**readings)


def test_missing_weather_is_rejected() -> None:
    with pytest.raises(TypeError):
        WeatherSample(wind_mph=None, rain_in_hr=0, snow_in_hr=0)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_load", [-1, math.nan, math.inf])
def test_invalid_load_is_rejected(bad_load: float) -> None:
    with pytest.raises(ValueError):
        assess(CALM, load_lb=bad_load)
