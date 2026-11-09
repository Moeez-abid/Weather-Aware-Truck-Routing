import { describe, expect, it } from "vitest";

import { formatDuration, formatLocalTime, formatMiles, formatPounds } from "./format";

describe("formatDuration", () => {
  it.each([
    [0, "0 min"],
    [2700, "45 min"],
    [3600, "1 h"],
    [56_340, "15 h 39 min"],
    [3599.6, "1 h"],
    [89, "1 min"],
  ])("formats %d seconds", (seconds, expected) => {
    expect(formatDuration(seconds)).toBe(expected);
  });
});

describe("formatMiles", () => {
  it.each([
    [0, "0 mi"],
    [0.4, "0.4 mi"],
    [9.94, "9.9 mi"],
    [10, "10 mi"],
    [1005.6, "1,006 mi"],
  ])("formats %d miles", (miles, expected) => {
    expect(formatMiles(miles)).toBe(expected);
  });
});

describe("formatPounds", () => {
  it("groups the thousands", () => {
    expect(formatPounds(40000)).toBe("40,000 lb");
  });
});

describe("formatLocalTime", () => {
  it("shows the weekday and time in the place's own timezone", () => {
    expect(formatLocalTime("2026-11-09T17:05:32-06:00", "America/Chicago")).toBe("Mon 5:05 PM CST");
  });

  it("converts to the timezone it is given", () => {
    expect(formatLocalTime("2026-11-09T17:05:32-06:00", "America/Denver")).toBe("Mon 4:05 PM MST");
  });

  it("uses the weekday at that place", () => {
    expect(formatLocalTime("2026-11-10T01:30:00-06:00", "America/Denver")).toBe("Tue 12:30 AM MST");
  });
});
