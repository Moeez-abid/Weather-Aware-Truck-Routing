import pytest

from risk.classification import RiskLevel
from risk.recommendation import (
    CheckpointRisk,
    RouteRiskSummary,
    miles_covered,
    recommend,
    summarize_route,
)

LOW = RiskLevel.LOW
MODERATE = RiskLevel.MODERATE
HIGH = RiskLevel.HIGH
SEVERE = RiskLevel.SEVERE
NO_TRAVEL = RiskLevel.NO_TRAVEL


def checkpoints(levels: list[RiskLevel], spacing: float = 10) -> list[CheckpointRisk]:
    return [CheckpointRisk(mile=i * spacing, level=level) for i, level in enumerate(levels)]


def summary(
    route_id: str,
    no_travel: float = 0,
    severe: float = 0,
    high: float = 0,
    average: float = 0,
    hours: float = 1,
) -> RouteRiskSummary:
    return RouteRiskSummary(
        route_id=route_id,
        total_miles=100,
        duration_seconds=hours * 3600,
        miles_by_level={
            LOW: 100 - no_travel - severe - high,
            MODERATE: 0,
            HIGH: high,
            SEVERE: severe,
            NO_TRAVEL: no_travel,
        },
        average_risk=average,
    )


def test_end_checkpoints_cover_half_a_gap() -> None:
    assert miles_covered([0, 10, 20, 30]) == [5, 10, 10, 5]


def test_shorter_final_gap_is_shared_between_its_checkpoints() -> None:
    assert miles_covered([0, 25, 50, 60]) == [12.5, 25, 17.5, 5]


def test_two_checkpoints_split_the_route() -> None:
    assert miles_covered([0, 7]) == [3.5, 3.5]


def test_level_miles_add_up_to_the_route_length() -> None:
    route = [
        CheckpointRisk(0, LOW),
        CheckpointRisk(25, HIGH),
        CheckpointRisk(50, SEVERE),
        CheckpointRisk(73.4, MODERATE),
    ]

    result = summarize_route("a", route, duration_seconds=3600)

    assert result.total_miles == pytest.approx(73.4)
    assert sum(result.miles_by_level.values()) == pytest.approx(73.4)


def test_miles_are_totalled_per_level() -> None:
    result = summarize_route(
        "a", checkpoints([LOW, SEVERE, SEVERE, HIGH, NO_TRAVEL]), duration_seconds=3600
    )

    assert result.miles_by_level == {
        LOW: 5,
        MODERATE: 0,
        HIGH: 10,
        SEVERE: 20,
        NO_TRAVEL: 5,
    }


def test_average_risk_is_weighted_by_distance() -> None:
    route = [CheckpointRisk(0, LOW), CheckpointRisk(90, LOW), CheckpointRisk(100, SEVERE)]

    # Covered miles are 45, 50 and 5, so the average is 3 * 5 / 100.
    assert summarize_route("a", route, duration_seconds=1).average_risk == 0.15


def test_average_risk_is_rounded_to_two_decimals() -> None:
    route = checkpoints([LOW, LOW, MODERATE, LOW])

    # Covered miles are 5, 10, 10 and 5, so the average is 10 / 30.
    assert summarize_route("a", route, duration_seconds=1).average_risk == 0.33


def test_summary_keeps_the_duration() -> None:
    assert summarize_route("a", checkpoints([LOW, LOW]), 5400).duration_seconds == 5400


@pytest.mark.parametrize(
    "route",
    [
        [],
        [CheckpointRisk(0, LOW)],
        [CheckpointRisk(0, LOW), CheckpointRisk(0, LOW)],
        [CheckpointRisk(10, LOW), CheckpointRisk(5, LOW)],
    ],
)
def test_invalid_checkpoints_are_rejected(route: list[CheckpointRisk]) -> None:
    with pytest.raises(ValueError):
        summarize_route("a", route, duration_seconds=1)


def test_no_routes_is_rejected() -> None:
    with pytest.raises(ValueError):
        recommend([])


def test_any_no_travel_ranks_below_any_amount_of_severe() -> None:
    result = recommend([summary("a", no_travel=1), summary("b", severe=90)])

    assert result.ranked_route_ids == ["b", "a"]
    assert result.recommended_route_id == "b"


def test_fewer_severe_miles_beats_fewer_high_miles() -> None:
    result = recommend([summary("a", severe=10), summary("b", severe=5, high=80)])

    assert result.recommended_route_id == "b"


def test_fewer_high_miles_beats_lower_average() -> None:
    result = recommend([summary("a", high=10, average=0.5), summary("b", high=5, average=2.0)])

    assert result.recommended_route_id == "b"


def test_lower_average_beats_shorter_time() -> None:
    result = recommend([summary("a", average=0.5, hours=5), summary("b", average=0.6, hours=1)])

    assert result.recommended_route_id == "a"


def test_shorter_time_decides_when_risk_is_equal() -> None:
    result = recommend([summary("a", hours=5), summary("b", hours=4)])

    assert result.recommended_route_id == "b"


def test_safer_route_wins_even_when_much_slower() -> None:
    result = recommend([summary("fast", severe=1, hours=2), summary("safe", hours=20)])

    assert result.recommended_route_id == "safe"


def test_averages_equal_after_rounding_fall_through_to_time() -> None:
    slow = summarize_route("slow", checkpoints([LOW, LOW, MODERATE, LOW]), duration_seconds=7200)
    fast = summarize_route(
        "fast",
        [
            CheckpointRisk(0, LOW),
            CheckpointRisk(10, LOW),
            CheckpointRisk(20.03, MODERATE),
            CheckpointRisk(30, LOW),
        ],
        duration_seconds=3600,
    )

    assert slow.average_risk == fast.average_risk
    assert recommend([slow, fast]).recommended_route_id == "fast"


def test_full_tie_keeps_the_routing_providers_order() -> None:
    result = recommend([summary("first"), summary("second")])

    assert result.ranked_route_ids == ["first", "second"]


def test_all_routes_are_ranked_best_first() -> None:
    result = recommend(
        [summary("worst", no_travel=5), summary("best"), summary("middle", severe=5)]
    )

    assert result.ranked_route_ids == ["best", "middle", "worst"]


def test_nothing_is_recommended_when_every_route_has_no_travel_miles() -> None:
    result = recommend([summary("a", no_travel=20), summary("b", no_travel=5)])

    assert result.recommended_route_id is None
    assert result.ranked_route_ids == ["b", "a"]


def test_no_travel_at_one_checkpoint_blocks_a_single_route() -> None:
    route = summarize_route("only", checkpoints([LOW, LOW, NO_TRAVEL]), duration_seconds=3600)

    assert recommend([route]).recommended_route_id is None
