/** The backend's JSON contract. Field names match the API responses exactly. */

export type RiskLevel = "low" | "moderate" | "high" | "severe" | "no_travel";

export type CheckpointInterval = 10 | 25 | 50;

/** A point on a line, longitude first, as map libraries expect. */
export type LonLat = [lon: number, lat: number];

export interface Position {
  lat: number;
  lon: number;
}

export interface Place extends Position {
  label: string;
}

export interface TripRequest {
  origin: Position;
  destination: Position;
  /** Local time at the origin, with no UTC offset, such as 2026-11-10T09:30. */
  departure: string;
  load_lb: number;
  interval_miles: CheckpointInterval;
}

export interface Checkpoint extends Position {
  mile: number;
  /** ISO time with the UTC offset of this checkpoint's own timezone. */
  eta: string;
  timezone: string;
  risk: RiskLevel;
  risk_factors: Record<"wind" | "rain" | "snow", RiskLevel>;
  weather: {
    wind_mph: number;
    rain_in_hr: number;
    snow_in_hr: number;
  };
}

export interface PlannedRoute {
  id: string;
  distance_miles: number;
  duration_seconds: number;
  arrival: string;
  average_risk: number;
  miles_by_risk: Record<RiskLevel, number>;
  /** Detailed line for drawing the route on the map. */
  geometry: LonLat[];
  /** Lighter line to send back when requesting the heatmap. */
  corridor: LonLat[];
  checkpoints: Checkpoint[];
}

export interface TripPlan {
  departure: string;
  timezone: string;
  /** Null when every route has No Travel miles. */
  recommended_route_id: string | null;
  ranked_route_ids: string[];
  routes: PlannedRoute[];
}

export interface HeatmapRequest {
  routes: LonLat[][];
  /** The departure returned with the trip plan, including its UTC offset. */
  departure: string;
  load_lb: number;
}

export interface Heatmap {
  columns: number;
  rows: number;
  west: number;
  south: number;
  east: number;
  north: number;
  /** Flat index (row * columns + column) of each corridor cell, with row 0 at the north edge. */
  cells: number[];
  /**
   * One string per forecast hour, 0 to 48, with one character per entry in `cells`:
   * the risk level as a digit from 0 (Low) to 4 (No Travel), or "-" where there is no forecast.
   */
  frames: string[];
}
