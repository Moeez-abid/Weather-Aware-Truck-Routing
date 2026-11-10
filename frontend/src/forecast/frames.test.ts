import { describe, expect, it } from "vitest";

import type { Heatmap } from "../api/types";
import { forecastHourLabels, framePixels, hasMissingForecast } from "./frames";

function heatmap(frames: string[], cells = [0, 3, 5], columns = 3, rows = 2): Heatmap {
  return { columns, rows, west: -101, south: 39, east: -98, north: 41, cells, frames };
}

function pixel(pixels: Uint8ClampedArray, index: number): number[] {
  return Array.from(pixels.slice(index * 4, index * 4 + 4));
}

describe("framePixels", () => {
  it("makes one image per frame, sized to the grid", () => {
    const frames = framePixels(heatmap(["000", "111"]));

    expect(frames).toHaveLength(2);
    expect(frames[0]).toHaveLength(3 * 2 * 4);
  });

  it("colors each corridor cell at its grid position", () => {
    const [frame] = framePixels(heatmap(["034"]));

    expect(pixel(frame!, 0)).toEqual([47, 143, 102, 51]);
    expect(pixel(frame!, 3)).toEqual([196, 35, 43, 184]);
    expect(pixel(frame!, 5)).toEqual([59, 17, 80, 209]);
  });

  it("leaves cells outside the corridor transparent", () => {
    const [frame] = framePixels(heatmap(["444"]));

    for (const outside of [1, 2, 4]) {
      expect(pixel(frame!, outside)).toEqual([0, 0, 0, 0]);
    }
  });

  it("leaves hours without a forecast transparent rather than Low", () => {
    const [frame] = framePixels(heatmap(["-1-"]));

    expect(pixel(frame!, 0)).toEqual([0, 0, 0, 0]);
    expect(pixel(frame!, 5)).toEqual([0, 0, 0, 0]);
    expect(pixel(frame!, 3)).toEqual([224, 171, 0, 128]);
  });

  it("keeps each hour separate", () => {
    const frames = framePixels(heatmap(["000", "222"]));

    expect(pixel(frames[0]!, 0)).not.toEqual(pixel(frames[1]!, 0));
    expect(pixel(frames[1]!, 0)).toEqual([227, 111, 18, 158]);
  });

  it("makes stronger risk more opaque", () => {
    const [frame] = framePixels(heatmap(["01234", ], [0, 1, 2, 3, 4], 5, 1));

    const opacities = [0, 1, 2, 3, 4].map((cell) => pixel(frame!, cell)[3]!);
    expect(opacities).toEqual([...opacities].sort((a, b) => a - b));
    expect(new Set(opacities).size).toBe(5);
  });
});

describe("hasMissingForecast", () => {
  it("is false when every hour has data", () => {
    expect(hasMissingForecast(heatmap(["000", "111"]))).toBe(false);
  });

  it("is true when any hour lacks data", () => {
    expect(hasMissingForecast(heatmap(["000", "1-1"]))).toBe(true);
  });
});

describe("forecastHourLabels", () => {
  it("starts at the departure and has one label per hour", () => {
    const labels = forecastHourLabels("2026-11-09T11:00:00-06:00", "America/Chicago", 49);

    expect(labels).toHaveLength(49);
    expect(labels[0]).toBe("Mon 11:00 AM CST");
    expect(labels[1]).toBe("Mon 12:00 PM CST");
    expect(labels[48]).toBe("Wed 11:00 AM CST");
  });

  it("counts real hours across a daylight saving change", () => {
    const labels = forecastHourLabels("2026-10-31T20:00:00-05:00", "America/Chicago", 11);

    expect(labels[0]).toBe("Sat 8:00 PM CDT");
    expect(labels[10]).toBe("Sun 5:00 AM CST");
  });
});
