import type { Heatmap, HeatmapRequest, Place, Position, TripPlan, TripRequest } from "./types";

/** A failed request. `message` is safe to show to the user. */
export class ApiError extends Error {
  readonly status: number;
  /** Validation errors by request field, when the backend rejected the input. */
  readonly fields: Record<string, unknown>;

  constructor(message: string, status: number, fields: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fields = fields;
  }
}

const UNREACHABLE = "Can't reach the server. Check your connection and try again.";
const FAILED = "Something went wrong on the server. Please try again.";

function apiUrl(path: string): string {
  // Empty means the API is served from the same origin as the app.
  const base = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");
  return `${base}/api${path}`;
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), init);
  } catch (error) {
    if (init.signal?.aborted) {
      throw error;
    }
    throw new ApiError(UNREACHABLE, 0);
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const details = (body ?? {}) as { error?: string; fields?: Record<string, unknown> };
    throw new ApiError(details.error ?? FAILED, response.status, details.fields);
  }
  if (body === null) {
    throw new ApiError(FAILED, response.status);
  }
  return body as T;
}

function post<T>(path: string, payload: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
}

export function checkHealth(signal?: AbortSignal): Promise<{ status: string }> {
  return request("/health", { signal });
}

export async function searchPlaces(query: string, signal?: AbortSignal): Promise<Place[]> {
  const { results } = await request<{ results: Place[] }>(
    `/geocode?q=${encodeURIComponent(query)}`,
    { signal },
  );
  return results;
}

export async function getTimeZone(position: Position, signal?: AbortSignal): Promise<string> {
  const { timezone } = await request<{ timezone: string }>(
    `/timezone?lat=${position.lat}&lon=${position.lon}`,
    { signal },
  );
  return timezone;
}

export function planTrip(trip: TripRequest, signal?: AbortSignal): Promise<TripPlan> {
  return post("/trips/plan", trip, signal);
}

export function fetchHeatmap(heatmap: HeatmapRequest, signal?: AbortSignal): Promise<Heatmap> {
  return post("/heatmap", heatmap, signal);
}
