import { lazy, Suspense } from "react";

import { MapPlaceholder, MapPlate } from "./components/MapPlate";
import { TopBar } from "./components/TopBar";

// Loaded separately because the map library is most of the app's size. The page can paint first.
const MapView = lazy(() => import("./map/MapView"));

export function App() {
  return (
    <div className="grid h-full grid-rows-[auto_minmax(0,1fr)]">
      <TopBar />
      <main className="grid min-h-0 grid-rows-[minmax(16rem,42dvh)_minmax(0,1fr)] lg:grid-cols-[minmax(24rem,30rem)_minmax(0,1fr)] lg:grid-rows-1">
        <section
          aria-labelledby="trip-heading"
          className="order-2 flex min-h-0 flex-col overflow-y-auto border-hairline lg:order-1 lg:border-r"
        >
          <div className="p-6 lg:p-8">
            <h1 id="trip-heading" className="text-[2.5rem] leading-[1.05] tracking-[-0.02em] text-balance lg:text-[3.25rem]">
              Find the safest route for this load.
            </h1>
            <p className="mt-5 max-w-[34rem] text-body text-ink-muted">
              Clearhaul reads the forecast for the hour your truck reaches each point on the way,
              then recommends the route with the least risk.
            </p>
          </div>
          <div aria-hidden="true" className="dot-matrix mx-6 mb-6 min-h-16 flex-1 lg:mx-8 lg:mb-8" />
        </section>

        <MapPlate className="order-1 lg:order-2">
          <Suspense fallback={<MapPlaceholder />}>
            <MapView />
          </Suspense>
        </MapPlate>
      </main>
    </div>
  );
}
