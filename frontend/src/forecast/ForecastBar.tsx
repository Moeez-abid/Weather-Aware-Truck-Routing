import { useMemo, useRef, type ChangeEvent } from "react";

import type { TripPlan } from "../api/types";
import { RISK_LABEL, RISK_LEVELS } from "../risk/levels";
import { RiskGlyph } from "../risk/RiskGlyph";
import { forecastHourLabels, hasMissingForecast } from "./frames";
import type { HeatmapState } from "./useHeatmap";

const FORECAST_HOURS = 49;
const LAST_HOUR = FORECAST_HOURS - 1;
const RULER_HOURS = [0, 6, 12, 18, 24, 30, 36, 42, 48];
// Half the slider thumb's width, because the thumb's center stops short of the track's ends.
const THUMB_INSET = "0.375rem";

function rulerPosition(hour: number): string {
  return `calc(${THUMB_INSET} + (100% - 2 * ${THUMB_INSET}) * ${hour / LAST_HOUR})`;
}

function Ruler() {
  return (
    <div aria-hidden="true" className="relative h-5">
      {RULER_HOURS.map((hour) => (
        <span key={hour} className="absolute top-0 -translate-x-1/2" style={{ left: rulerPosition(hour) }}>
          <span className={`mx-auto block w-px bg-hairline ${hour % 12 === 0 ? "h-1.5" : "h-1"}`} />
          {hour % 12 === 0 && <span className="block font-mono text-[0.6875rem] leading-3.5 text-ink-muted">{hour}h</span>}
        </span>
      ))}
    </div>
  );
}

function hourTitle(hour: number): string {
  return hour === 0 ? "At departure" : `${hour} ${hour === 1 ? "hour" : "hours"} after departure`;
}

interface ForecastBarProps {
  plan: TripPlan;
  state: HeatmapState;
  onHourChange: (hour: number) => void;
  onRetry: () => void;
}

/**
 * The slider stays uncontrolled and updates its text directly, so that dragging it doesn't
 * render React. Keying this component by plan resets it to hour 0 for each new trip.
 */
export function ForecastBar({ plan, state, onHourChange, onRetry }: ForecastBarProps) {
  const labels = useMemo(
    () => forecastHourLabels(plan.departure, plan.timezone, FORECAST_HOURS),
    [plan.departure, plan.timezone],
  );
  const titleRef = useRef<HTMLSpanElement>(null);
  const timeRef = useRef<HTMLSpanElement>(null);

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const hour = event.currentTarget.valueAsNumber;
    onHourChange(hour);
    titleRef.current!.textContent = hourTitle(hour);
    timeRef.current!.textContent = labels[hour]!;
    event.currentTarget.setAttribute("aria-valuetext", `${hourTitle(hour)}, ${labels[hour]}`);
  }

  const isReady = state.status === "ready";

  return (
    <div className="flex flex-col gap-3 pt-3">
      <div className="flex flex-col gap-x-6 gap-y-1 md:flex-row md:items-start">
        <p className="shrink-0 md:w-60">
          <span ref={titleRef} className="block font-mono text-label whitespace-nowrap text-ink-muted uppercase">
            {hourTitle(0)}
          </span>
          <span ref={timeRef} className="mt-0.5 block text-base">
            {labels[0]}
          </span>
        </p>
        <div className="min-w-0 flex-1">
          <input
            type="range"
            min={0}
            max={LAST_HOUR}
            step={1}
            defaultValue={0}
            disabled={!isReady}
            aria-label="Forecast hour"
            aria-valuetext={`${hourTitle(0)}, ${labels[0]}`}
            onChange={handleChange}
            className="forecast-slider"
          />
          <Ruler />
        </div>
      </div>

      <div className="flex min-h-5 flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        {state.status === "loading" && (
          <p role="status" className="text-ink-muted">
            Loading the weather heatmap for this trip…
          </p>
        )}
        {state.status === "failed" && (
          <p role="alert" className="flex flex-wrap items-center gap-x-3 text-alert">
            {state.message}
            <button type="button" onClick={onRetry} className="cursor-pointer text-ink underline underline-offset-2">
              Try again
            </button>
          </p>
        )}
        {isReady && (
          <>
            {[...RISK_LEVELS].reverse().map((level) => (
              <span key={level} className="flex items-center gap-1.5 whitespace-nowrap">
                <RiskGlyph level={level} className="size-3" />
                {RISK_LABEL[level]}
              </span>
            ))}
            {hasMissingForecast(state.heatmap) && <span className="text-ink-muted">Blank: no forecast yet</span>}
          </>
        )}
      </div>
    </div>
  );
}
