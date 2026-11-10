import { useCallback, useEffect, useState } from "react";

import { ApiError, fetchHeatmap } from "../api/client";
import type { Heatmap, TripPlan } from "../api/types";

export type HeatmapState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; heatmap: Heatmap }
  | { status: "failed"; message: string };

/** Loads the heatmap separately from the plan, so that routes appear without waiting for it. */
export function useHeatmap(plan: TripPlan | null, loadLb: number | null) {
  const [state, setState] = useState<HeatmapState>({ status: "idle" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!plan || loadLb === null) {
      setState({ status: "idle" });
      return;
    }

    setState({ status: "loading" });
    const controller = new AbortController();
    fetchHeatmap(
      {
        routes: plan.routes.map((route) => route.corridor),
        departure: plan.departure,
        load_lb: loadLb,
      },
      controller.signal,
    ).then(
      (heatmap) => setState({ status: "ready", heatmap }),
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setState({
            status: "failed",
            message: error instanceof ApiError ? error.message : "The weather heatmap couldn't load.",
          });
        }
      },
    );
    return () => controller.abort();
  }, [plan, loadLb, attempt]);

  const retry = useCallback(() => setAttempt((current) => current + 1), []);

  return { state, retry };
}
