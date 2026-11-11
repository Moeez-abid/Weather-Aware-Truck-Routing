import { describe, expect, it } from "vitest";

import type { Checkpoint, LonLat, PlannedRoute, RiskLevel, TripPlan } from "../api/types";
import { checkpointFeatures, endpointFeatures, planBounds, routeFeatures, routeLabelPosition } from "./mapData";

function checkpoint(lon: number, lat: number, risk: RiskLevel): Checkpoint {
  return {
    lat,
    lon,
    mile: 0,
    eta: "2026-11-09T09:00:00-06:00",
    timezone: "America/Chicago",
    risk,
    risk_factors: { wind: "low", rain: "low", snow: "low" },
    weather: { wind_mph: 0, rain_in_hr: 0, snow_in_hr: 0 },
  };
}

function route(id: string, geometry: LonLat[], checkpoints: Checkpoint[] = []): PlannedRoute {
  return {
    id,
    distance_miles: 100,
    duration_seconds: 3600,
    arrival: "2026-11-09T10:00:00-06:00",
    average_risk: 0,
    miles_by_risk: { low: 100, moderate: 0, high: 0, severe: 0, no_travel: 0 },
    geometry,
    corridor: geometry,
    checkpoints,
  };
}

function plan(routes: PlannedRoute[]): TripPlan {
  return {
    departure: "2026-11-09T09:00:00-06:00",
    timezone: "America/Chicago",
    recommended_route_id: "A",
    ranked_route_ids: routes.map((item) => item.id),
    routes,
    closures_checked: true,
  };
}

const LINE_A: LonLat[] = [
  [-100, 40],
  [-99, 41],
  [-98, 39],
];
const LINE_B: LonLat[] = [
  [-100, 40],
  [-97, 43],
  [-98, 39],
];

describe("routeFeatures", () => {
  it("draws each route as a line tagged with its id", () => {
    const result = routeFeatures(plan([route("A", LINE_A), route("B", LINE_B)]));

    expect(result.type).toBe("FeatureCollection");
    expect(result.features.map((feature) => feature.properties.routeId)).toEqual(["A", "B"]);
    expect(result.features[1]!.geometry).toEqual({ type: "LineString", coordinates: LINE_B });
    expect(result.features[0]!.type).toBe("Feature");
  });

  it("is empty with no plan", () => {
    expect(routeFeatures(null).features).toEqual([]);
  });
});

describe("checkpointFeatures", () => {
  it("places every checkpoint of every route, longitude first", () => {
    const result = checkpointFeatures(
      plan([
        route("A", LINE_A, [checkpoint(-100, 40, "low"), checkpoint(-99, 41, "severe")]),
        route("B", LINE_B, [checkpoint(-97, 43, "no_travel")]),
      ]),
    );

    expect(result.features.map((feature) => feature.geometry.coordinates)).toEqual([
      [-100, 40],
      [-99, 41],
      [-97, 43],
    ]);
    expect(result.features.map((feature) => feature.properties)).toEqual([
      { routeId: "A", index: 0, risk: "low", level: 0 },
      { routeId: "A", index: 1, risk: "severe", level: 3 },
      { routeId: "B", index: 0, risk: "no_travel", level: 4 },
    ]);
  });

  it("is empty with no plan", () => {
    expect(checkpointFeatures(null).features).toEqual([]);
  });
});

describe("endpointFeatures", () => {
  it("marks the first and last points of the trip", () => {
    const result = endpointFeatures(plan([route("A", LINE_A)]));

    expect(result.features.map((feature) => [feature.properties.end, feature.geometry.coordinates])).toEqual([
      ["origin", [-100, 40]],
      ["destination", [-98, 39]],
    ]);
  });

  it("is empty with no plan", () => {
    expect(endpointFeatures(null).features).toEqual([]);
  });
});

describe("planBounds", () => {
  it("encloses every route", () => {
    expect(planBounds(plan([route("A", LINE_A), route("B", LINE_B)]))).toEqual([
      [-100, 39],
      [-97, 43],
    ]);
  });
});

describe("routeLabelPosition", () => {
  const line: LonLat[] = Array.from({ length: 21 }, (_, index) => [index, 0]);

  it("spreads the labels along their routes so they don't stack", () => {
    expect(routeLabelPosition(route("A", line), 0)).toEqual([10, 0]);
    expect(routeLabelPosition(route("B", line), 1)).toEqual([7, 0]);
    expect(routeLabelPosition(route("C", line), 2)).toEqual([13, 0]);
  });
});
