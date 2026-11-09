/** Turns a trip plan into what the map draws, kept free of the map library so it can be tested. */

import type { FeatureCollection, LineString, Point } from "geojson";

import type { LonLat, PlannedRoute, RiskLevel, TripPlan } from "../api/types";
import { RISK_LEVELS } from "../risk/levels";

export interface RouteProperties {
  routeId: string;
}

export interface CheckpointProperties {
  routeId: string;
  index: number;
  risk: RiskLevel;
  /** Higher values are drawn on top, so the worst risk stays visible where markers overlap. */
  level: number;
}

function collection<G extends LineString | Point, P>(
  features: { geometry: G; properties: P }[],
): FeatureCollection<G, P> {
  return {
    type: "FeatureCollection",
    features: features.map((feature) => ({ type: "Feature", ...feature })),
  };
}

export function routeFeatures(plan: TripPlan | null): FeatureCollection<LineString, RouteProperties> {
  return collection(
    (plan?.routes ?? []).map((route) => ({
      geometry: { type: "LineString", coordinates: route.geometry },
      properties: { routeId: route.id },
    })),
  );
}

export function checkpointFeatures(plan: TripPlan | null): FeatureCollection<Point, CheckpointProperties> {
  return collection(
    (plan?.routes ?? []).flatMap((route) =>
      route.checkpoints.map((checkpoint, index) => ({
        geometry: { type: "Point" as const, coordinates: [checkpoint.lon, checkpoint.lat] },
        properties: {
          routeId: route.id,
          index,
          risk: checkpoint.risk,
          level: RISK_LEVELS.indexOf(checkpoint.risk),
        },
      })),
    ),
  );
}

/** The trip's two ends, which every route shares. */
export function endpointFeatures(plan: TripPlan | null): FeatureCollection<Point, { end: "origin" | "destination" }> {
  const route = plan?.routes[0];
  if (!route) {
    return collection<Point, { end: "origin" | "destination" }>([]);
  }
  return collection([
    { geometry: { type: "Point", coordinates: route.geometry[0]! }, properties: { end: "origin" as const } },
    { geometry: { type: "Point", coordinates: route.geometry.at(-1)! }, properties: { end: "destination" as const } },
  ]);
}

/** The southwest and northeast corners of a box around every route. */
export function planBounds(plan: TripPlan): [LonLat, LonLat] {
  const points = plan.routes.flatMap((route) => route.geometry);
  const lons = points.map(([lon]) => lon);
  const lats = points.map(([, lat]) => lat);
  return [
    [Math.min(...lons), Math.min(...lats)],
    [Math.max(...lons), Math.max(...lats)],
  ];
}

// Spread along each route, because routes often share their first and last stretches.
const LABEL_POSITIONS = [0.5, 0.35, 0.65];

/** Where to place a route's letter on the map. `order` is the route's position in the plan. */
export function routeLabelPosition(route: PlannedRoute, order: number): LonLat {
  const fraction = LABEL_POSITIONS[order % LABEL_POSITIONS.length]!;
  return route.geometry[Math.floor((route.geometry.length - 1) * fraction)]!;
}
