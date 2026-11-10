import type { CanvasSource, Map as MapLibreMap } from "maplibre-gl";

import type { Heatmap } from "../api/types";
import { framePixels, paddedCorners } from "../forecast/frames";
import { FIRST_ROUTE_LAYER } from "./tripLayers";

const SOURCE = "forecast-heatmap";
const LAYER = "forecast-heatmap";

export interface HeatmapLayer {
  showHour: (hour: number) => void;
  remove: () => void;
}

/**
 * Adds a heatmap whose hours are all prepared up front. Showing an hour only copies one small
 * image to the map: no network request, no map data to process, and no React rendering.
 */
export function addHeatmapLayer(map: MapLibreMap, heatmap: Heatmap): HeatmapLayer {
  const canvas = document.createElement("canvas");
  // One transparent cell of border on every side, which the map's smoothing fades into.
  canvas.width = heatmap.columns + 2;
  canvas.height = heatmap.rows + 2;
  const context = canvas.getContext("2d")!;
  const frames = framePixels(heatmap).map((pixels) => new ImageData(pixels, heatmap.columns, heatmap.rows));
  context.putImageData(frames[0]!, 1, 1);

  map.addSource(SOURCE, {
    type: "canvas",
    canvas,
    // Not animated, because that would make the map redraw constantly even when nothing changes.
    animate: false,
    coordinates: paddedCorners(heatmap),
  });
  map.addLayer(
    {
      id: LAYER,
      type: "raster",
      source: SOURCE,
      // Blends between cells, so that a coarse grid doesn't look like blocks.
      paint: { "raster-resampling": "linear", "raster-fade-duration": 0 },
    },
    FIRST_ROUTE_LAYER,
  );

  return {
    showHour(hour) {
      context.putImageData(frames[hour]!, 1, 1);
      const source = map.getSource(SOURCE) as CanvasSource;
      // Together these copy the canvas to the map exactly once.
      source.play();
      source.pause();
      map.triggerRepaint();
    },
    remove() {
      map.removeLayer(LAYER);
      map.removeSource(SOURCE);
    },
  };
}
