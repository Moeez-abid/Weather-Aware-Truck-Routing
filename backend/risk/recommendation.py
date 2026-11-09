"""Turn checkpoint risk levels into route totals and pick the best route."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise

from risk.classification import RiskLevel


@dataclass(frozen=True)
class CheckpointRisk:
    mile: float
    level: RiskLevel


@dataclass(frozen=True)
class RouteRiskSummary:
    route_id: str
    total_miles: float
    duration_seconds: float
    miles_by_level: Mapping[RiskLevel, float]
    average_risk: float

    @property
    def no_travel_miles(self) -> float:
        return self.miles_by_level[RiskLevel.NO_TRAVEL]

    @property
    def severe_miles(self) -> float:
        return self.miles_by_level[RiskLevel.SEVERE]

    @property
    def high_miles(self) -> float:
        return self.miles_by_level[RiskLevel.HIGH]


@dataclass(frozen=True)
class Recommendation:
    recommended_route_id: str | None
    ranked_route_ids: list[str]


def miles_covered(checkpoint_miles: Sequence[float]) -> list[float]:
    """Give each checkpoint half the gap on either side, so the shares add up to the route."""
    boundaries = [
        checkpoint_miles[0],
        *((a + b) / 2 for a, b in pairwise(checkpoint_miles)),
        checkpoint_miles[-1],
    ]
    return [end - start for start, end in pairwise(boundaries)]


def summarize_route(
    route_id: str, checkpoints: Sequence[CheckpointRisk], duration_seconds: float
) -> RouteRiskSummary:
    miles = [checkpoint.mile for checkpoint in checkpoints]
    if len(miles) < 2:
        raise ValueError("A route needs at least an origin and a destination checkpoint.")
    if any(later <= earlier for earlier, later in pairwise(miles)):
        raise ValueError("Checkpoint miles must be strictly increasing.")

    miles_by_level = dict.fromkeys(RiskLevel, 0.0)
    weighted_risk = 0.0
    for checkpoint, covered in zip(checkpoints, miles_covered(miles), strict=True):
        miles_by_level[checkpoint.level] += covered
        weighted_risk += int(checkpoint.level) * covered

    total_miles = miles[-1] - miles[0]
    return RouteRiskSummary(
        route_id=route_id,
        total_miles=total_miles,
        duration_seconds=duration_seconds,
        miles_by_level=miles_by_level,
        # Rounded here so the value shown to the driver is the value that was compared.
        average_risk=round(weighted_risk / total_miles, 2),
    )


def _rank_key(summary: RouteRiskSummary) -> tuple[float, float, float, float, float]:
    # No Travel is not in the brief's ranking, but it has to count as worse than Severe.
    return (
        summary.no_travel_miles,
        summary.severe_miles,
        summary.high_miles,
        summary.average_risk,
        summary.duration_seconds,
    )


def recommend(summaries: Sequence[RouteRiskSummary]) -> Recommendation:
    """Rank routes best first. No route is recommended if every one has No Travel miles."""
    if not summaries:
        raise ValueError("At least one route is required.")

    ranked = sorted(summaries, key=_rank_key)
    best = ranked[0]
    return Recommendation(
        recommended_route_id=best.route_id if best.no_travel_miles == 0 else None,
        ranked_route_ids=[summary.route_id for summary in ranked],
    )
