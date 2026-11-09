import { lazy, Suspense, useCallback, useState } from "react";

import type { TripPlan } from "./api/types";
import { MapPlaceholder, MapPlate } from "./components/MapPlate";
import { TopBar } from "./components/TopBar";
import type { CheckpointFocus } from "./map/MapView";
import { defaultRouteId } from "./results/recommendation";
import { TripResults } from "./results/TripResults";
import { serverFieldErrors } from "./trip/formValues";
import { TripForm } from "./trip/TripForm";
import { useTripPlan, type TripPlanState } from "./trip/useTripPlan";

// Loaded separately because the map library is most of the app's size. The page can paint first.
const MapView = lazy(() => import("./map/MapView"));

function PlanStatus({ state }: { state: TripPlanState }) {
  if (state.status === "loading") {
    return (
      <p role="status" className="text-sm text-ink-muted">
        Finding truck routes and reading the forecast along each one. This can take up to 15 seconds.
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

export function App() {
  const { state, submit } = useTripPlan();
  const [isEditing, setIsEditing] = useState(false);
  // Remembers which plan a choice was made for, so that a new plan starts from its own default.
  const [choice, setChoice] = useState<{ plan: TripPlan; routeId: string } | null>(null);
  const [focusedCheckpoint, setFocusedCheckpoint] = useState<CheckpointFocus | null>(null);

  const plan = state.status === "success" ? state.plan : null;
  const selectedRouteId = plan ? (choice?.plan === plan ? choice.routeId : defaultRouteId(plan)) : null;
  const showResults = state.status === "success" && !isEditing;

  const selectRoute = useCallback(
    (routeId: string) => {
      if (plan) {
        setChoice({ plan, routeId });
      }
    },
    [plan],
  );

  return (
    <div className="grid h-full grid-rows-[auto_minmax(0,1fr)]">
      <TopBar />
      <main className="grid min-h-0 grid-rows-[minmax(16rem,38dvh)_minmax(0,1fr)] lg:grid-cols-[minmax(24rem,30rem)_minmax(0,1fr)] lg:grid-rows-1">
        <section
          aria-label="Trip planner"
          className="order-2 flex min-h-0 flex-col gap-6 overflow-y-auto border-hairline p-6 lg:order-1 lg:border-r lg:p-8"
        >
          {/* Stays mounted while hidden, so that editing a trip keeps what was entered. */}
          <div className={showResults ? "hidden" : "flex min-h-full flex-col gap-6"}>
            <div>
              <h1 className="text-[2.5rem] leading-[1.05] tracking-[-0.02em] text-balance">
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
            <PlanStatus state={state} />
            <div aria-hidden="true" className="dot-matrix hidden min-h-0 flex-1 lg:block" />
          </div>

          {showResults && (
            <TripResults
              plan={state.plan}
              places={state.places}
              loadLb={state.trip.load_lb}
              selectedRouteId={selectedRouteId!}
              onSelectRoute={selectRoute}
              onSelectCheckpoint={(index) => setFocusedCheckpoint({ routeId: selectedRouteId!, index })}
              onEditTrip={() => setIsEditing(true)}
            />
          )}
        </section>

        <MapPlate className="order-1 lg:order-2">
          <Suspense fallback={<MapPlaceholder />}>
            <MapView
              plan={plan}
              selectedRouteId={selectedRouteId}
              focusedCheckpoint={focusedCheckpoint}
              onSelectRoute={selectRoute}
            />
          </Suspense>
        </MapPlate>
      </main>
    </div>
  );
}
