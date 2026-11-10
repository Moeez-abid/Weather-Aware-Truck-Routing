import { lazy, Suspense, useCallback, useRef, useState } from "react";

import type { TripPlan } from "./api/types";
import { MapPlaceholder, MapPlate } from "./components/MapPlate";
import { RecommendationSeal } from "./components/RecommendationSeal";
import { TopBar } from "./components/TopBar";
import { useServiceStatus, type ServiceStatus } from "./components/useServiceStatus";
import { ForecastBar } from "./forecast/ForecastBar";
import { useHeatmap } from "./forecast/useHeatmap";
import type { CheckpointFocus, MapHandle } from "./map/MapView";
import { defaultRouteId } from "./results/recommendation";
import { TripResults } from "./results/TripResults";
import { serverFieldErrors } from "./trip/formValues";
import { TripForm } from "./trip/TripForm";
import { useTripPlan, type TripPlanState } from "./trip/useTripPlan";

// Loaded separately because the map library is most of the app's size. The page can paint first.
const MapView = lazy(() => import("./map/MapView"));

function loadingMessage(service: ServiceStatus): string {
  return service === "connecting"
    ? "The server is starting up, so this first trip can take a little longer than usual."
    : "Finding truck routes and reading the forecast along each one. This can take up to 15 seconds.";
}

function PlanStatus({ state, service }: { state: TripPlanState; service: ServiceStatus }) {
  if (state.status === "loading") {
    return (
      <p role="status" className="text-sm text-ink-muted">
        {loadingMessage(service)}
      </p>
    );
  }
  // When the problem belongs to a field, the message is shown beside that field instead.
  if (state.status === "error" && Object.keys(serverFieldErrors(state.error.fields)).length === 0) {
    return (
      <p role="alert" className="text-sm text-alert">
        {state.error.message}
      </p>
    );
  }
  return null;
}

/** Shows that a plan is on its way, over the map that will hold it. */
function PlanningOverlay() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 z-10">
      <div className="h-0.5 overflow-hidden bg-hairline/60">
        <div className="progress-sweep h-full w-1/3 bg-ink" />
      </div>
      <p className="m-3 inline-block border border-hairline bg-ground px-2.5 py-1 font-mono text-label text-ink uppercase">
        Planning routes
      </p>
    </div>
  );
}

export function App() {
  const service = useServiceStatus();
  const { state, submit } = useTripPlan();
  const [isEditing, setIsEditing] = useState(false);
  // Remembers which plan a choice was made for, so that a new plan starts from its own default.
  const [choice, setChoice] = useState<{ plan: TripPlan; routeId: string } | null>(null);
  const [focusedCheckpoint, setFocusedCheckpoint] = useState<CheckpointFocus | null>(null);

  const plan = state.status === "success" ? state.plan : null;
  const selectedRouteId = plan ? (choice?.plan === plan ? choice.routeId : defaultRouteId(plan)) : null;
  const showResults = state.status === "success" && !isEditing;
  const { state: heatmapState, retry: retryHeatmap } = useHeatmap(
    plan,
    state.status === "success" ? state.trip.load_lb : null,
  );
  const mapHandle = useRef<MapHandle>(null);

  const selectRoute = useCallback(
    (routeId: string) => {
      if (plan) {
        setChoice({ plan, routeId });
      }
    },
    [plan],
  );

  // On a phone the map gets more room once there are routes and a forecast slider to show.
  const phoneRows = plan
    ? "grid-rows-[minmax(24rem,66dvh)_minmax(0,1fr)]"
    : "grid-rows-[minmax(16rem,38dvh)_minmax(0,1fr)]";

  return (
    <div className="grid h-full grid-rows-[auto_minmax(0,1fr)]">
      <TopBar status={service} />
      <main
        className={`grid min-h-0 ${phoneRows} lg:grid-cols-[minmax(24rem,30rem)_minmax(0,1fr)] lg:grid-rows-1`}
      >
        <section
          aria-label="Trip planner"
          className="order-2 flex min-h-0 flex-col gap-6 overflow-y-auto border-hairline p-6 lg:order-1 lg:border-r lg:p-8"
        >
          {/* Stays mounted while hidden, so that editing a trip keeps what was entered. */}
          <div className={showResults ? "hidden" : "flex min-h-full flex-col gap-6"}>
            <div>
              <h1 className="text-[2.5rem] leading-[1.02] tracking-[-0.025em] text-balance lg:text-[3.25rem]">
                Find the safest route for this load.
              </h1>
              <p className="mt-4 text-body text-ink-muted">
                Clearhaul reads the forecast for the hour your truck reaches each point on the way.
              </p>
            </div>
            <TripForm
              onSubmit={(trip, places) => {
                setIsEditing(false);
                submit(trip, places);
              }}
              isSubmitting={state.status === "loading"}
              serverError={state.status === "error" ? state.error : null}
            />
            <PlanStatus state={state} service={service} />
            <div aria-hidden="true" className="dot-matrix hidden min-h-0 flex-1 lg:block" />
          </div>

          {showResults && (
            <div key={state.planNumber} className="reveal">
              <TripResults
                plan={state.plan}
                places={state.places}
                loadLb={state.trip.load_lb}
                selectedRouteId={selectedRouteId!}
                onSelectRoute={selectRoute}
                onSelectCheckpoint={(index) => setFocusedCheckpoint({ routeId: selectedRouteId!, index })}
                onEditTrip={() => setIsEditing(true)}
              />
            </div>
          )}
        </section>

        <MapPlate
          className="order-1 lg:order-2"
          seal={plan?.recommended_route_id && <RecommendationSeal routeId={plan.recommended_route_id} />}
          footer={
            state.status === "success" && (
              <ForecastBar
                key={state.planNumber}
                plan={state.plan}
                state={heatmapState}
                onHourChange={(hour) => mapHandle.current?.showForecastHour(hour)}
                onRetry={retryHeatmap}
              />
            )
          }
        >
          <Suspense fallback={<MapPlaceholder />}>
            <MapView
              ref={mapHandle}
              plan={plan}
              heatmap={heatmapState.status === "ready" ? heatmapState.heatmap : null}
              selectedRouteId={selectedRouteId}
              focusedCheckpoint={focusedCheckpoint}
              onSelectRoute={selectRoute}
            />
          </Suspense>
          {state.status === "loading" && <PlanningOverlay />}
        </MapPlate>
      </main>
    </div>
  );
}
