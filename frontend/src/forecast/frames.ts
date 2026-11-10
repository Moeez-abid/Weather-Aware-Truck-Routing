/** Prepares the heatmap's hourly frames, kept free of the browser so it can be tested. */

import type { Heatmap, RiskLevel } from "../api/types";
import { formatLocalTime } from "../results/format";
import { RISK_COLOR, RISK_LEVELS } from "../risk/levels";

const BYTES_PER_PIXEL = 4;
const MS_PER_HOUR = 3_600_000;
const NO_FORECAST = "-";

/** Low is a faint wash, so that the corridor stays readable and real risk stands out. */
const HEAT_OPACITY: Record<RiskLevel, number> = {
  low: 0.12,
  moderate: 0.5,
  high: 0.62,
  severe: 0.72,
  no_travel: 0.82,
};

function pixelColor(level: RiskLevel): [number, number, number, number] {
  const hex = parseInt(RISK_COLOR[level].slice(1), 16);
  return [hex >> 16, (hex >> 8) & 255, hex & 255, Math.round(HEAT_OPACITY[level] * 255)];
}

const PALETTE = RISK_LEVELS.map(pixelColor);

/**
 * Turns each frame into RGBA pixels, one pixel per grid cell. Cells outside the corridor and
 * hours the forecast doesn't reach stay transparent, so they are never mistaken for Low.
 */
export function framePixels(heatmap: Heatmap): Uint8ClampedArray<ArrayBuffer>[] {
  const size = heatmap.columns * heatmap.rows * BYTES_PER_PIXEL;
  return heatmap.frames.map((frame) => {
    const pixels = new Uint8ClampedArray(size);
    heatmap.cells.forEach((cell, index) => {
      const code = frame[index]!;
      if (code !== NO_FORECAST) {
        pixels.set(PALETTE[Number(code)]!, cell * BYTES_PER_PIXEL);
      }
    });
    return pixels;
  });
}

function mercatorY(lat: number): number {
  return Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
}

function mercatorLatitude(y: number): number {
  return (Math.atan(Math.exp(y)) * 360) / Math.PI - 90;
}

/**
 * The grid's corners grown by one cell on every side. Drawing the frames inside a transparent
 * border lets the map's smoothing fade the corridor's outer edge instead of ending it hard.
 */
export function paddedCorners(heatmap: Heatmap): [[number, number], [number, number], [number, number], [number, number]] {
  const cellWidth = (heatmap.east - heatmap.west) / heatmap.columns;
  const north = mercatorY(heatmap.north);
  const south = mercatorY(heatmap.south);
  const cellHeight = (north - south) / heatmap.rows;
  const west = heatmap.west - cellWidth;
  const east = heatmap.east + cellWidth;
  const top = mercatorLatitude(north + cellHeight);
  const bottom = mercatorLatitude(south - cellHeight);
  return [
    [west, top],
    [east, top],
    [east, bottom],
    [west, bottom],
  ];
}

export function hasMissingForecast(heatmap: Heatmap): boolean {
  return heatmap.frames.some((frame) => frame.includes(NO_FORECAST));
}

/** The actual time of each slider hour, counted in real hours from the departure. */
export function forecastHourLabels(departure: string, timeZone: string, hours: number): string[] {
  const start = new Date(departure).getTime();
  return Array.from({ length: hours }, (_, hour) =>
    formatLocalTime(new Date(start + hour * MS_PER_HOUR).toISOString(), timeZone),
  );
}
