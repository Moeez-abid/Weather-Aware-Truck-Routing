import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, planTrip } from "../api/client";
import type { TripPlan, TripRequest } from "../api/types";

export interface PlaceNames {
  origin: string;
  destination: string;
}

export type TripPlanState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; plan: TripPlan; trip: TripRequest; places: PlaceNames }
  | { status: "error"; error: ApiError };

export function useTripPlan() {
  const [state, setState] = useState<TripPlanState>({ status: "idle" });
  const controller = useRef<AbortController | null>(null);

  const submit = useCallback((trip: TripRequest, places: PlaceNames) => {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;

    setState({ status: "loading" });
    planTrip(trip, current.signal).then(
      (plan) => setState({ status: "success", plan, trip, places }),
      (error: unknown) => {
        if (!current.signal.aborted) {
          setState({
            status: "error",
            error: error instanceof ApiError ? error : new ApiError("Something went wrong. Please try again.", 0),
          });
        }
      },
    );
  }, []);

  useEffect(() => () => controller.current?.abort(), []);

  return { state, submit };
}
