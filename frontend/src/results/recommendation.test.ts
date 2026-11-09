import { describe, expect, it } from "vitest";

import type { Checkpoint, PlannedRoute, RiskLevel, TripPlan } from "../api/types";
import {
  defaultRouteId,
  rankedRoutes,
  recommendationReason,
  riskDrivers,
  riskSegments,
  routeById,
} from "./recommendation";

function route(id: string, overrides: Partial<PlannedRoute> = {}): PlannedRoute {
  return {
    id,
    distance_miles: 100,
    duration_seconds: 7200,
    arrival: "2026-11-09T12:00:00-06:00",
    average_risk: 0,
    miles_by_risk: { low: 100, moderate: 0, high: 0, severe: 0, no_travel: 0 },
    geometry: [],
    corridor: [],
    checkpoints: [],
    ...overrides,
  };
}

function miles(values: Partial<Record<RiskLevel, number>>): Record<RiskLevel, number> {
  return { low: 0, moderate: 0, high: 0, severe: 0, no_travel: 0, ...values };
}

function plan(routes: PlannedRoute[], ranked = routes.map((item) => item.id), recommended: string | null = ranked[0]!): TripPlan {
  return {
    departure: "2026-11-09T09:00:00-06:00",
    timezone: "America/Chicago",
    recommended_route_id: recommended,
    ranked_route_ids: ranked,
    routes,
  };
}

function checkpoint(risk: RiskLevel, factors: Partial<Checkpoint["risk_factors"]>): Checkpoint {
  return {
    lat: 40,
    lon: -100,
    mile: 0,
    eta: "2026-11-09T09:00:00-06:00",
    timezone: "America/Chicago",
    risk,
    risk_factors: { wind: "low", rain: "low", snow: "low", ...factors },
    weather: { wind_mph: 0, rain_in_hr: 0, snow_in_hr: 0 },
  };
}

describe("finding routes", () => {
  it("finds a route by id", () => {
    const b = route("B");

    expect(routeById(plan([route("A"), b]), "B")).toBe(b);
  });

  it("fails loudly for an unknown route", () => {
    expect(() => routeById(plan([route("A")]), "Z")).toThrow();
  });

  it("orders routes as the backend ranked them", () => {
    const result = rankedRoutes(plan([route("A"), route("B"), route("C")], ["C", "A", "B"]));

    expect(result.map((item) => item.id)).toEqual(["C", "A", "B"]);
  });

  it("shows the recommended route first", () => {
    expect(defaultRouteId(plan([route("A"), route("B")], ["B", "A"], "B"))).toBe("B");
  });

  it("falls back to the top-ranked route when none is recommended", () => {
    expect(defaultRouteId(plan([route("A"), route("B")], ["B", "A"], null))).toBe("B");
  });
});

describe("recommendationReason", () => {
  it("says when there was nothing to compare", () => {
    expect(recommendationReason(plan([route("A")]))).toBe("It is the only route found for this trip.");
  });

  it("names No Travel miles first", () => {
    const routes = [
      route("A", { miles_by_risk: miles({ low: 100, severe: 50 }) }),
      route("B", { miles_by_risk: miles({ low: 80, no_travel: 20 }) }),
    ];

    expect(recommendationReason(plan(routes))).toBe("Fewest No Travel miles: 0 mi, against 20 mi on Route B.");
  });

  it("then Severe miles", () => {
    const routes = [
      route("A", { miles_by_risk: miles({ low: 90, severe: 10, high: 90 }) }),
      route("B", { miles_by_risk: miles({ low: 58, severe: 42 }) }),
    ];

    expect(recommendationReason(plan(routes))).toBe("Fewest Severe miles: 10 mi, against 42 mi on Route B.");
  });

  it("then High miles", () => {
    const routes = [
      route("A", { miles_by_risk: miles({ low: 95, high: 5 }) }),
      route("B", { miles_by_risk: miles({ low: 70, high: 30 }) }),
    ];

    expect(recommendationReason(plan(routes))).toBe("Fewest High miles: 5.0 mi, against 30 mi on Route B.");
  });

  it("then average risk", () => {
    const routes = [route("A", { average_risk: 0.1 }), route("B", { average_risk: 0.35 })];

    expect(recommendationReason(plan(routes))).toBe("Lowest average risk: 0.10, against 0.35 on Route B.");
  });

  it("then travel time", () => {
    const routes = [route("A", { duration_seconds: 3600 }), route("B", { duration_seconds: 9000 })];

    expect(recommendationReason(plan(routes))).toBe("Weather risk matches Route B, and this route is 1 h 30 min faster.");
  });

  it("admits a full tie", () => {
    expect(recommendationReason(plan([route("A"), route("B")]))).toBe(
      "It ties with Route B on weather risk and travel time.",
    );
  });

  it("compares against the runner-up, in ranked order", () => {
    const routes = [
      route("A", { average_risk: 0.9 }),
      route("B", { average_risk: 0.1 }),
      route("C", { average_risk: 0.5 }),
    ];

    expect(recommendationReason(plan(routes, ["B", "C", "A"]))).toBe(
      "Lowest average risk: 0.10, against 0.50 on Route C.",
    );
  });
});

describe("riskSegments", () => {
  it("lists only the levels present, worst first, with their share", () => {
    const segments = riskSegments(route("A", { miles_by_risk: miles({ low: 150, severe: 50 }) }));

    expect(segments).toEqual([
      { level: "severe", miles: 50, percent: 25 },
      { level: "low", miles: 150, percent: 75 },
    ]);
  });
});

describe("riskDrivers", () => {
  it("has no drivers at Low", () => {
    expect(riskDrivers(checkpoint("low", {}))).toEqual([]);
  });

  it("names the factor at the checkpoint's level", () => {
    expect(riskDrivers(checkpoint("high", { rain: "high", wind: "moderate" }))).toEqual(["rain"]);
  });

  it("names every factor tied at that level", () => {
    expect(riskDrivers(checkpoint("severe", { wind: "severe", snow: "severe" }))).toEqual(["wind", "snow"]);
  });
});
