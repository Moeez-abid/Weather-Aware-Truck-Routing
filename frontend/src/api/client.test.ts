import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, checkHealth, fetchHeatmap, planTrip, searchPlaces } from "./client";
import type { HeatmapRequest, TripRequest } from "./types";

const fetchMock = vi.fn<typeof fetch>();

const TRIP: TripRequest = {
  origin: { lat: 41.88, lon: -87.63 },
  destination: { lat: 39.74, lon: -104.99 },
  departure: "2026-11-10T09:30",
  load_lb: 40000,
  interval_miles: 25,
};

const HEATMAP: HeatmapRequest = {
  routes: [
    [
      [-87.63, 41.88],
      [-104.99, 39.74],
    ],
  ],
  departure: "2026-11-10T09:30:00-06:00",
  load_lb: 40000,
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function lastCall(): { url: string; init: RequestInit } {
  const [url, init] = fetchMock.mock.lastCall!;
  return { url: String(url), init: init! };
}

async function failure(promise: Promise<unknown>): Promise<ApiError> {
  const error = await promise.catch((caught: unknown) => caught);
  expect(error).toBeInstanceOf(ApiError);
  return error as ApiError;
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("VITE_API_BASE_URL", "https://api.example.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  fetchMock.mockReset();
});

describe("requests", () => {
  it("checks the health endpoint", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: "ok" }));

    await expect(checkHealth()).resolves.toEqual({ status: "ok" });
    expect(lastCall().url).toBe("https://api.example.test/api/health");
  });

  it("encodes the search text and returns the places", async () => {
    const places = [{ label: "Dallas, TX", lat: 32.77, lon: -96.79 }];
    fetchMock.mockResolvedValue(jsonResponse({ results: places }));

    await expect(searchPlaces("A&B, TX?")).resolves.toEqual(places);
    expect(lastCall().url).toBe("https://api.example.test/api/geocode?q=A%26B%2C%20TX%3F");
  });

  it("posts the trip as JSON", async () => {
    const plan = { routes: [] };
    fetchMock.mockResolvedValue(jsonResponse(plan));

    await expect(planTrip(TRIP)).resolves.toEqual(plan);

    const { url, init } = lastCall();
    expect(url).toBe("https://api.example.test/api/trips/plan");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body as string)).toEqual(TRIP);
  });

  it("posts the heatmap request as JSON", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ frames: [] }));

    await fetchHeatmap(HEATMAP);

    const { url, init } = lastCall();
    expect(url).toBe("https://api.example.test/api/heatmap");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual(HEATMAP);
  });

  it("passes the abort signal to fetch", async () => {
    const controller = new AbortController();
    fetchMock.mockResolvedValue(jsonResponse({ results: [] }));

    await searchPlaces("Dallas", controller.signal);

    expect(lastCall().init.signal).toBe(controller.signal);
  });

  it("tolerates a trailing slash on the base URL", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.test/");
    fetchMock.mockResolvedValue(jsonResponse({ status: "ok" }));

    await checkHealth();

    expect(lastCall().url).toBe("https://api.example.test/api/health");
  });

  it("uses the same origin when no base URL is set", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "");
    fetchMock.mockResolvedValue(jsonResponse({ status: "ok" }));

    await checkHealth();

    expect(lastCall().url).toBe("/api/health");
  });
});

describe("errors", () => {
  it("uses the backend's message and status", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ error: "No truck route could be found." }, 422));

    const error = await failure(planTrip(TRIP));

    expect(error.message).toBe("No truck route could be found.");
    expect(error.status).toBe(422);
    expect(error.fields).toEqual({});
  });

  it("keeps validation errors by field", async () => {
    const fields = { departure: ["Departure time is in the past."] };
    fetchMock.mockResolvedValue(jsonResponse({ error: "Please check the trip details.", fields }, 400));

    const error = await failure(planTrip(TRIP));

    expect(error.status).toBe(400);
    expect(error.fields).toEqual(fields);
  });

  it("has a readable message when an error response isn't JSON", async () => {
    fetchMock.mockResolvedValue(new Response("<html>Bad gateway</html>", { status: 502 }));

    const error = await failure(planTrip(TRIP));

    expect(error.message).toBe("Something went wrong on the server. Please try again.");
    expect(error.status).toBe(502);
  });

  it("treats a successful response that isn't JSON as a failure", async () => {
    fetchMock.mockResolvedValue(new Response("<html></html>", { status: 200 }));

    await failure(checkHealth());
  });

  it("explains when the server can't be reached", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    const error = await failure(checkHealth());

    expect(error.message).toBe("Can't reach the server. Check your connection and try again.");
    expect(error.status).toBe(0);
  });

  it("lets an aborted request stay an abort", async () => {
    const controller = new AbortController();
    controller.abort();
    const abort = new DOMException("Aborted", "AbortError");
    fetchMock.mockRejectedValue(abort);

    await expect(searchPlaces("Dallas", controller.signal)).rejects.toBe(abort);
  });
});
