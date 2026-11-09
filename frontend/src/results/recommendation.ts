import type { Checkpoint, PlannedRoute, RiskLevel, TripPlan } from "../api/types";
import { RISK_LABEL, RISK_LEVELS } from "../risk/levels";
import { formatDuration, formatMiles } from "./format";

const RANKED_LEVELS: RiskLevel[] = ["no_travel", "severe", "high"];

export function routeById(plan: TripPlan, id: string): PlannedRoute {
  const route = plan.routes.find((candidate) => candidate.id === id);
  if (!route) {
    throw new Error(`The trip plan has no route ${id}.`);
  }
  return route;
}

/** Routes in the order the backend ranked them, best first. */
export function rankedRoutes(plan: TripPlan): PlannedRoute[] {
  return plan.ranked_route_ids.map((id) => routeById(plan, id));
}

/** The route to show first: the recommended one, or else the least bad. */
export function defaultRouteId(plan: TripPlan): string {
  return plan.recommended_route_id ?? plan.ranked_route_ids[0]!;
}

/** Explains the recommendation by the first ranking rule that separates the top two routes. */
export function recommendationReason(plan: TripPlan): string {
  const [best, next] = rankedRoutes(plan);
  if (!next) {
    return "It is the only route found for this trip.";
  }
  const other = `Route ${next!.id}`;

  for (const level of RANKED_LEVELS) {
    const ours = best!.miles_by_risk[level];
    const theirs = next.miles_by_risk[level];
    if (ours !== theirs) {
      return `Fewest ${RISK_LABEL[level]} miles: ${formatMiles(ours)}, against ${formatMiles(theirs)} on ${other}.`;
    }
  }

  if (best!.average_risk !== next.average_risk) {
    return `Lowest average risk: ${best!.average_risk.toFixed(2)}, against ${next.average_risk.toFixed(2)} on ${other}.`;
  }

  const saved = next.duration_seconds - best!.duration_seconds;
  if (saved > 0) {
    return `Weather risk matches ${other}, and this route is ${formatDuration(saved)} faster.`;
  }
  return `It ties with ${other} on weather risk and travel time.`;
}

export interface RiskSegment {
  level: RiskLevel;
  miles: number;
  /** Share of the route, from 0 to 100. */
  percent: number;
}

/** The levels a route actually has miles in, worst first. */
export function riskSegments(route: PlannedRoute): RiskSegment[] {
  const total = RISK_LEVELS.reduce((sum, level) => sum + route.miles_by_risk[level], 0);
  return [...RISK_LEVELS]
    .reverse()
    .filter((level) => route.miles_by_risk[level] > 0)
    .map((level) => ({
      level,
      miles: route.miles_by_risk[level],
      percent: (route.miles_by_risk[level] / total) * 100,
    }));
}

const WEATHER_FACTORS = ["wind", "rain", "snow"] as const;
export type WeatherFactor = (typeof WEATHER_FACTORS)[number];

/** The weather factors responsible for a checkpoint's risk level. Low has none. */
export function riskDrivers(checkpoint: Checkpoint): WeatherFactor[] {
  if (checkpoint.risk === "low") {
    return [];
  }
  return WEATHER_FACTORS.filter((factor) => checkpoint.risk_factors[factor] === checkpoint.risk);
}
