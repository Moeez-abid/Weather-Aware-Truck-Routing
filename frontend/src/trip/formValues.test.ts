import { describe, expect, it } from "vitest";

import type { Place } from "../api/types";
import {
  defaultDeparture,
  parseLoad,
  serverFieldErrors,
  timeZoneName,
  toTripRequest,
  validateTripForm,
  wallClock,
  type TripFormValues,
} from "./formValues";

const CHICAGO: Place = { label: "Chicago, IL", lat: 41.88, lon: -87.63 };
const DENVER: Place = { label: "Denver, CO", lat: 39.74, lon: -104.99 };
// 15:00 UTC is 09:00 in Chicago in November.
const NOW = new Date("2026-11-10T15:00:00Z");

function values(overrides: Partial<TripFormValues> = {}): TripFormValues {
  return {
    origin: CHICAGO,
    destination: DENVER,
    departure: "2026-11-10T10:00",
    load: "40000",
    interval: 25,
    ...overrides,
  };
}

describe("wallClock", () => {
  it("gives the local time in a timezone", () => {
    expect(wallClock(NOW, "America/Chicago")).toBe("2026-11-10T09:00");
    expect(wallClock(NOW, "America/Denver")).toBe("2026-11-10T08:00");
  });

  it("uses a 24-hour clock with midnight as 00", () => {
    expect(wallClock(new Date("2026-11-10T06:05:00Z"), "America/Chicago")).toBe("2026-11-10T00:05");
  });

  it("rolls back to the previous date when needed", () => {
    expect(wallClock(new Date("2026-11-10T02:00:00Z"), "America/Chicago")).toBe("2026-11-09T20:00");
  });

  it("follows daylight saving time", () => {
    expect(wallClock(new Date("2026-07-10T15:00:00Z"), "America/Chicago")).toBe("2026-07-10T10:00");
  });
});

describe("defaultDeparture", () => {
  it("rounds up to the next quarter hour in the origin's timezone", () => {
    expect(defaultDeparture("America/Chicago", new Date("2026-11-10T15:07:00Z"))).toBe("2026-11-10T09:15");
    expect(defaultDeparture("America/New_York", new Date("2026-11-10T15:07:00Z"))).toBe("2026-11-10T10:15");
  });

  it("stays put when already on a quarter hour", () => {
    expect(defaultDeparture("America/Chicago", new Date("2026-11-10T15:30:00Z"))).toBe("2026-11-10T09:30");
  });

  it("is never in the past", () => {
    expect(defaultDeparture("America/Chicago", new Date("2026-11-10T15:30:01Z"))).toBe("2026-11-10T09:45");
  });
});

describe("timeZoneName", () => {
  it("names the timezone for that time of year", () => {
    expect(timeZoneName("America/Chicago", NOW)).toBe("Central Standard Time");
    expect(timeZoneName("America/Chicago", new Date("2026-07-10T15:00:00Z"))).toBe("Central Daylight Time");
  });
});

describe("parseLoad", () => {
  it.each([
    ["40000", 40000],
    ["40,000", 40000],
    [" 40 000 ", 40000],
    ["0", 0],
    ["1250.5", 1250.5],
  ])("reads %s", (text, expected) => {
    expect(parseLoad(text)).toBe(expected);
  });

  it.each(["", "heavy", "-5", "1e5", "12.", "4,0k"])("rejects %j", (text) => {
    expect(parseLoad(text)).toBeNull();
  });
});

describe("validateTripForm", () => {
  it("accepts a complete trip", () => {
    expect(validateTripForm(values(), "America/Chicago", NOW)).toEqual({});
  });

  it("requires places chosen from the list", () => {
    const errors = validateTripForm(values({ origin: null, destination: null }), "America/Chicago", NOW);

    expect(errors.origin).toBe("Choose a starting place from the list.");
    expect(errors.destination).toBe("Choose a destination from the list.");
  });

  it.each(["", "2026-11"])("requires a departure, not %j", (departure) => {
    expect(validateTripForm(values({ departure }), "America/Chicago", NOW).departure).toBe(
      "Choose a departure date and time.",
    );
  });

  it("allows a departure up to 15 minutes ago", () => {
    expect(validateTripForm(values({ departure: "2026-11-10T08:45" }), "America/Chicago", NOW)).toEqual({});
  });

  it("rejects an older departure", () => {
    expect(validateTripForm(values({ departure: "2026-11-10T08:44" }), "America/Chicago", NOW).departure).toBe(
      "Departure time is in the past.",
    );
  });

  it("judges the past by the origin's timezone", () => {
    // 09:00 is the present in Chicago but already an hour ago in New York.
    const departure = "2026-11-10T09:00";

    expect(validateTripForm(values({ departure }), "America/Chicago", NOW)).toEqual({});
    expect(validateTripForm(values({ departure }), "America/New_York", NOW).departure).toBeDefined();
  });

  it("leaves the past check to the backend when the timezone is unknown", () => {
    expect(validateTripForm(values({ departure: "2020-01-01T00:00" }), null, NOW)).toEqual({});
  });

  it("requires a load", () => {
    expect(validateTripForm(values({ load: "  " }), "America/Chicago", NOW).load).toBe(
      "Enter the load weight in pounds.",
    );
  });

  it("requires a numeric load", () => {
    expect(validateTripForm(values({ load: "heavy" }), "America/Chicago", NOW).load).toBe(
      "Enter the load as a number of pounds.",
    );
  });

  it("allows the limits of the load range", () => {
    expect(validateTripForm(values({ load: "0" }), "America/Chicago", NOW)).toEqual({});
    expect(validateTripForm(values({ load: "200,000" }), "America/Chicago", NOW)).toEqual({});
  });

  it("rejects a load above the limit", () => {
    expect(validateTripForm(values({ load: "200001" }), "America/Chicago", NOW).load).toBe(
      "Load can't be more than 200,000 lb.",
    );
  });
});

describe("toTripRequest", () => {
  it("sends only coordinates, with the load as a number", () => {
    expect(toTripRequest(values({ load: "40,000", interval: 10 }))).toEqual({
      origin: { lat: 41.88, lon: -87.63 },
      destination: { lat: 39.74, lon: -104.99 },
      departure: "2026-11-10T10:00",
      load_lb: 40000,
      interval_miles: 10,
    });
  });

  it("refuses an incomplete trip", () => {
    expect(() => toTripRequest(values({ origin: null }))).toThrow();
  });
});

describe("serverFieldErrors", () => {
  it("maps backend field names to form fields", () => {
    expect(
      serverFieldErrors({
        load_lb: ["Too heavy."],
        interval_miles: ["Not an option."],
        departure: ["Departure time is in the past."],
      }),
    ).toEqual({
      load: "Too heavy.",
      interval: "Not an option.",
      departure: "Departure time is in the past.",
    });
  });

  it("finds messages nested under a position", () => {
    expect(serverFieldErrors({ origin: { lat: ["Out of range."] } })).toEqual({ origin: "Out of range." });
  });

  it("ignores fields the form doesn't have", () => {
    expect(serverFieldErrors({ non_field_errors: ["Invalid."] })).toEqual({});
  });
});
