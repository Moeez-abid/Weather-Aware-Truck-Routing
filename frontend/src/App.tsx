import { lazy, Suspense } from "react";

import { MapPlaceholder, MapPlate } from "./components/MapPlate";
import { TopBar } from "./components/TopBar";
import { serverFieldErrors } from "./trip/formValues";
import { TripForm } from "./trip/TripForm";
import { useTripPlan, type TripPlanState } from "./trip/useTripPlan";

// Loaded separately because the map library is most of the app's size. The page can paint first.
const MapView = lazy(() => import("./map/MapView"));

function PlanStatus({ state }: { state: TripPlanState }) {
  switch (state.status) {
    case "idle":
      return null;
    case "loading":
      return (
        <p role="status" className="text-sm text-ink-muted">
          Finding truck routes and reading the forecast along each one. This can take up to 15 seconds.
        </p>
      );
    case "error":
      // When the problem belongs to a field, the message is shown beside that field instead.
      if (Object.keys(serverFieldErrors(state.error.fields)).length > 0) {
        return null;
      }
      return (
        <p role="alert" className="text-sm text-alert">
          {state.error.message}
        </p>
      );
    case "success": {
      const { routes, recommended_route_id: recommended } = state.plan;
      return (
        <p role="status" className="text-sm">
          {routes.length} {routes.length === 1 ? "route" : "routes"} found.{" "}
          {recommended ? `Route ${recommended} is recommended.` : "No route is safe at this departure time."}
        </p>
      );
    }
  }
}

export function App() {
  const { state, submit } = useTripPlan();

  return (
    <div className="grid h-full grid-rows-[auto_minmax(0,1fr)]">
      <TopBar />
      <main className="grid min-h-0 grid-rows-[minmax(16rem,38dvh)_minmax(0,1fr)] lg:grid-cols-[minmax(24rem,30rem)_minmax(0,1fr)] lg:grid-rows-1">
        <section
          aria-labelledby="trip-heading"
          className="order-2 flex min-h-0 flex-col gap-6 overflow-y-auto border-hairline p-6 lg:order-1 lg:border-r lg:p-8"
        >
          <div>
            <h1 id="trip-heading" className="text-[2.5rem] leading-[1.05] tracking-[-0.02em] text-balance">
              Find the safest route for this load.
            </h1>
            <p className="mt-4 text-body text-ink-muted">
              Clearhaul reads the forecast for the hour your truck reaches each point on the way.
            </p>
          </div>
          <TripForm
            onSubmit={submit}
            isSubmitting={state.status === "loading"}
            serverError={state.status === "error" ? state.error : null}
          />
          <PlanStatus state={state} />
          <div aria-hidden="true" className="dot-matrix hidden min-h-0 flex-1 lg:block" />
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
