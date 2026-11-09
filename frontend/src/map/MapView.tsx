import { Map as MapLibreMap, Marker, NavigationControl, Popup, setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import type { Checkpoint, TripPlan } from "../api/types";
import { MapPlaceholder } from "../components/MapPlate";
import { CheckpointDetail } from "../results/CheckpointDetail";
import { routeById } from "../results/recommendation";
import { routeLabelPosition } from "./mapData";
import { addTripLayers, CLICKABLE_LAYERS, highlightRoute, showPlan } from "./tripLayers";

// MapLibre can't find its worker by itself once a bundler has moved its files.
setWorkerUrl(workerUrl);

// A quiet, near-monochrome base map, so that risk colors are the only strong color on it.
const MAP_STYLE = "https://tiles.openfreemap.org/styles/positron";
const CONTIGUOUS_US: [[number, number], [number, number]] = [
  [-125, 24.5],
  [-66.5, 49.5],
];

const ROUTE_LABEL_CLASS =
  "grid size-7 cursor-pointer place-items-center border border-ink bg-ground font-mono text-sm text-ink transition-colors";
const SELECTED_LABEL_CLASSES = ["bg-ink!", "text-ground!"];

type MapStatus = "loading" | "ready" | "failed";

export interface CheckpointFocus {
  routeId: string;
  index: number;
}

interface OpenPopup {
  checkpoint: Checkpoint;
  element: HTMLElement;
}

interface MapViewProps {
  plan: TripPlan | null;
  selectedRouteId: string | null;
  focusedCheckpoint: CheckpointFocus | null;
  onSelectRoute: (routeId: string) => void;
}

export default function MapView({ plan, selectedRouteId, focusedCheckpoint, onSelectRoute }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const popupRef = useRef<Popup | null>(null);
  const labelsRef = useRef(new Map<string, Marker>());
  const [status, setStatus] = useState<MapStatus>("loading");
  const [openPopup, setOpenPopup] = useState<OpenPopup | null>(null);

  useEffect(() => {
    let map: MapLibreMap;
    try {
      map = new MapLibreMap({
        container: containerRef.current!,
        style: MAP_STYLE,
        bounds: CONTIGUOUS_US,
        fitBoundsOptions: { padding: 32 },
        attributionControl: { compact: false },
        // Routes are read north-up, and a rotated map would only make them harder to compare.
        dragRotate: false,
        pitchWithRotate: false,
      });
    } catch {
      // Thrown when the browser can't provide WebGL.
      setStatus("failed");
      return;
    }

    map.touchZoomRotate.disableRotation();
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    map.once("load", () => {
      addTripLayers(map);
      mapRef.current = map;
      setStatus("ready");
    });
    // Later errors are single tiles that fail, which the map recovers from by itself.
    map.on("error", () => setStatus((current) => (current === "loading" ? "failed" : current)));

    return () => {
      mapRef.current = null;
      map.remove();
    };
  }, []);

  function showCheckpoint(checkpoint: Checkpoint) {
    const map = mapRef.current;
    if (!map) {
      return;
    }
    popupRef.current?.remove();
    const element = document.createElement("div");
    const popup = new Popup({ maxWidth: "20rem", offset: 14 })
      .setLngLat([checkpoint.lon, checkpoint.lat])
      .setDOMContent(element)
      .addTo(map);
    popup.on("close", () => setOpenPopup((current) => (current?.element === element ? null : current)));
    popupRef.current = popup;
    setOpenPopup({ checkpoint, element });
  }

  useEffect(() => {
    const map = mapRef.current;
    if (status !== "ready" || !map) {
      return;
    }
    popupRef.current?.remove();
    showPlan(map, plan);

    const labels = labelsRef.current;
    plan?.routes.forEach((route, order) => {
      const element = document.createElement("button");
      element.type = "button";
      element.className = ROUTE_LABEL_CLASS;
      element.textContent = route.id;
      element.setAttribute("aria-label", `Select route ${route.id}`);
      element.addEventListener("click", (event) => {
        event.stopPropagation();
        onSelectRoute(route.id);
      });
      labels.set(route.id, new Marker({ element }).setLngLat(routeLabelPosition(route, order)).addTo(map));
    });

    return () => {
      labels.forEach((label) => label.remove());
      labels.clear();
    };
  }, [plan, status, onSelectRoute]);

  useEffect(() => {
    const map = mapRef.current;
    if (status !== "ready" || !map) {
      return;
    }
    highlightRoute(map, selectedRouteId);
    labelsRef.current.forEach((label, routeId) => {
      for (const name of SELECTED_LABEL_CLASSES) {
        label.getElement().classList.toggle(name, routeId === selectedRouteId);
      }
    });
  }, [selectedRouteId, plan, status]);

  useEffect(() => {
    const map = mapRef.current;
    if (status !== "ready" || !map || !plan) {
      return;
    }
    const handleClick = (event: { point: { x: number; y: number } }) => {
      const feature = map.queryRenderedFeatures([event.point.x, event.point.y], { layers: CLICKABLE_LAYERS })[0];
      if (!feature) {
        return;
      }
      const { routeId, index } = feature.properties as { routeId: string; index?: number };
      onSelectRoute(routeId);
      if (index !== undefined) {
        showCheckpoint(routeById(plan, routeId).checkpoints[index]!);
      }
    };
    const handleMove = (event: { point: { x: number; y: number } }) => {
      const hit = map.queryRenderedFeatures([event.point.x, event.point.y], { layers: CLICKABLE_LAYERS }).length > 0;
      map.getCanvas().style.cursor = hit ? "pointer" : "";
    };
    map.on("click", handleClick);
    map.on("mousemove", handleMove);
    return () => {
      map.off("click", handleClick);
      map.off("mousemove", handleMove);
    };
  }, [plan, status, onSelectRoute]);

  useEffect(() => {
    const map = mapRef.current;
    if (status !== "ready" || !map || !plan || !focusedCheckpoint) {
      return;
    }
    const checkpoint = routeById(plan, focusedCheckpoint.routeId).checkpoints[focusedCheckpoint.index]!;
    map.easeTo({ center: [checkpoint.lon, checkpoint.lat], duration: 400 });
    showCheckpoint(checkpoint);
    // Runs only when a checkpoint is chosen from the list, not on every change to the plan.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusedCheckpoint]);

  return (
    <div className="absolute inset-0">
      <div ref={containerRef} className="size-full" />
      {status === "loading" && <MapPlaceholder />}
      {status === "failed" && (
        <div className="absolute inset-0 grid place-items-center bg-ground p-6 text-center">
          <p role="alert" className="max-w-xs text-body">
            The map couldn&rsquo;t load. Refresh the page to try again.
          </p>
        </div>
      )}
      {openPopup && createPortal(<CheckpointDetail checkpoint={openPopup.checkpoint} />, openPopup.element)}
    </div>
  );
}
