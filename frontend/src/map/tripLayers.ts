/** The map's trip layers: route lines, trip ends and risk-shaped checkpoint markers. */

import type { GeoJSONSource, Map as MapLibreMap, SymbolLayerSpecification } from "maplibre-gl";

import type { TripPlan } from "../api/types";
import { NO_TRAVEL_BAR, RISK_COLOR, RISK_LEVELS, RISK_SHAPE } from "../risk/levels";
import { checkpointFeatures, endpointFeatures, planBounds, routeFeatures } from "./mapData";

const INK = "#16181a";
const OTHER_ROUTE = "#8b8e93";
const ROUTE_SOURCE = "trip-routes";
const CHECKPOINT_SOURCE = "trip-checkpoints";
const ENDPOINT_SOURCE = "trip-endpoints";

const OTHER_LINES = "routes-other";
/** The lowest route layer, which anything drawn under the routes has to be added before. */
export const FIRST_ROUTE_LAYER = OTHER_LINES;
const SELECTED_CASING = "routes-selected-casing";
const SELECTED_LINE = "routes-selected";
export const ROUTE_HIT_AREA = "routes-hit";
const OTHER_CHECKPOINTS = "checkpoints-other";
export const SELECTED_CHECKPOINTS = "checkpoints-selected";
export const CLICKABLE_LAYERS = [SELECTED_CHECKPOINTS, OTHER_CHECKPOINTS, ROUTE_HIT_AREA];

const MARKER_SIZE = 20;
const NO_ROUTE = "";

function isRoute(routeId: string): ["==", ["get", string], string] {
  return ["==", ["get", "routeId"], routeId];
}

function isOtherRoute(routeId: string): ["!=", ["get", string], string] {
  return ["!=", ["get", "routeId"], routeId];
}

function addRiskMarkers(map: MapLibreMap) {
  const pixelRatio = window.devicePixelRatio || 1;
  const size = Math.ceil(MARKER_SIZE * pixelRatio);
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const context = canvas.getContext("2d", { willReadFrequently: true })!;
  const box = 16;
  const scale = (size * 0.84) / box;

  for (const level of RISK_LEVELS) {
    context.resetTransform();
    context.clearRect(0, 0, size, size);
    context.translate(size * 0.08, size * 0.08);
    context.scale(scale, scale);

    const shape = new Path2D(RISK_SHAPE[level]);
    context.lineJoin = "round";
    context.lineWidth = 2.5;
    context.strokeStyle = "#ffffff";
    context.stroke(shape);
    context.fillStyle = RISK_COLOR[level];
    context.fill(shape);
    if (level === "no_travel") {
      context.fillStyle = "#ffffff";
      context.fill(new Path2D(NO_TRAVEL_BAR));
    }

    map.addImage(`risk-${level}`, context.getImageData(0, 0, size, size), { pixelRatio });
  }
}

function checkpointLayout(sizes: [number, number]): SymbolLayerSpecification["layout"] {
  return {
    "icon-image": ["concat", "risk-", ["get", "risk"]],
    "icon-size": ["interpolate", ["linear"], ["zoom"], 4, sizes[0], 9, sizes[1]],
    "icon-allow-overlap": true,
    "icon-ignore-placement": true,
    "symbol-sort-key": ["get", "level"],
  };
}

/** Adds the empty trip layers. Call once, after the base map has loaded. */
export function addTripLayers(map: MapLibreMap) {
  const empty = routeFeatures(null);
  map.addSource(ROUTE_SOURCE, { type: "geojson", data: empty });
  map.addSource(CHECKPOINT_SOURCE, { type: "geojson", data: empty });
  map.addSource(ENDPOINT_SOURCE, { type: "geojson", data: empty });
  addRiskMarkers(map);

  // Lines go under the base map's labels, so that place names stay readable.
  const firstLabel = map.getStyle().layers.find((layer) => layer.type === "symbol")?.id;
  const lineLayout = { "line-cap": "round", "line-join": "round" } as const;

  map.addLayer(
    {
      id: OTHER_LINES,
      type: "line",
      source: ROUTE_SOURCE,
      layout: lineLayout,
      paint: { "line-color": OTHER_ROUTE, "line-width": 3 },
      filter: isOtherRoute(NO_ROUTE),
    },
    firstLabel,
  );
  map.addLayer(
    {
      id: SELECTED_CASING,
      type: "line",
      source: ROUTE_SOURCE,
      layout: lineLayout,
      paint: { "line-color": "#ffffff", "line-width": 7 },
      filter: isRoute(NO_ROUTE),
    },
    firstLabel,
  );
  map.addLayer(
    {
      id: SELECTED_LINE,
      type: "line",
      source: ROUTE_SOURCE,
      layout: lineLayout,
      paint: { "line-color": INK, "line-width": 4 },
      filter: isRoute(NO_ROUTE),
    },
    firstLabel,
  );
  // Invisible and wide, so that a route is easy to tap with a finger.
  map.addLayer({
    id: ROUTE_HIT_AREA,
    type: "line",
    source: ROUTE_SOURCE,
    layout: lineLayout,
    paint: { "line-color": INK, "line-width": 18, "line-opacity": 0.001 },
  });

  map.addLayer({
    id: "trip-origin-destination",
    type: "circle",
    source: ENDPOINT_SOURCE,
    paint: {
      "circle-radius": 11,
      "circle-color": ["case", ["==", ["get", "end"], "destination"], INK, "#ffffff"],
      "circle-stroke-color": INK,
      "circle-stroke-width": 2,
    },
  });

  map.addLayer({
    id: OTHER_CHECKPOINTS,
    type: "symbol",
    source: CHECKPOINT_SOURCE,
    layout: checkpointLayout([0.45, 0.7]),
    filter: isOtherRoute(NO_ROUTE),
  });
  map.addLayer({
    id: SELECTED_CHECKPOINTS,
    type: "symbol",
    source: CHECKPOINT_SOURCE,
    layout: checkpointLayout([0.7, 1]),
    filter: isRoute(NO_ROUTE),
  });
}

/** Draws a plan, or clears the map when there is none, and frames all of its routes. */
export function showPlan(map: MapLibreMap, plan: TripPlan | null) {
  (map.getSource(ROUTE_SOURCE) as GeoJSONSource).setData(routeFeatures(plan));
  (map.getSource(CHECKPOINT_SOURCE) as GeoJSONSource).setData(checkpointFeatures(plan));
  (map.getSource(ENDPOINT_SOURCE) as GeoJSONSource).setData(endpointFeatures(plan));
  if (plan) {
    map.fitBounds(planBounds(plan), { padding: 56, duration: 600 });
  }
}

/** Brings one route forward. Filters are used so that no route data has to be processed again. */
export function highlightRoute(map: MapLibreMap, routeId: string | null) {
  const id = routeId ?? NO_ROUTE;
  map.setFilter(OTHER_LINES, isOtherRoute(id));
  map.setFilter(SELECTED_CASING, isRoute(id));
  map.setFilter(SELECTED_LINE, isRoute(id));
  map.setFilter(OTHER_CHECKPOINTS, isOtherRoute(id));
  map.setFilter(SELECTED_CHECKPOINTS, isRoute(id));
}
