import { Map as MapLibreMap, NavigationControl, setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { useEffect, useRef, useState } from "react";

import { MapPlaceholder } from "../components/MapPlate";

// MapLibre can't find its worker by itself once a bundler has moved its files.
setWorkerUrl(workerUrl);

// A quiet, near-monochrome base map, so that risk colors are the only strong color on it.
const MAP_STYLE = "https://tiles.openfreemap.org/styles/positron";
const CONTIGUOUS_US: [[number, number], [number, number]] = [
  [-125, 24.5],
  [-66.5, 49.5],
];

type MapStatus = "loading" | "ready" | "failed";

export default function MapView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<MapStatus>("loading");

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
    map.once("load", () => setStatus("ready"));
    // Later errors are single tiles that fail, which the map recovers from by itself.
    map.on("error", () => setStatus((current) => (current === "loading" ? "failed" : current)));

    return () => map.remove();
  }, []);

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
    </div>
  );
}
