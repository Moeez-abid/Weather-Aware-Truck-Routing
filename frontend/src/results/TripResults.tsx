import { useEffect, useRef } from "react";

import type { PlannedRoute, TripPlan } from "../api/types";
import { RiskGlyph } from "../risk/RiskGlyph";
import { RISK_COLOR, RISK_LABEL } from "../risk/levels";
import { WeatherSummary } from "./CheckpointDetail";
import { formatDuration, formatLocalTime, formatMiles, formatPounds } from "./format";
import { rankedRoutes, recommendationReason, riskSegments, routeById } from "./recommendation";

function RouteRow({
  route,
  timeZoneOfArrival,
  isRecommended,
  isSelected,
  onSelect,
}: {
  route: PlannedRoute;
  timeZoneOfArrival: string;
  isRecommended: boolean;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const segments = riskSegments(route);

  return (
    <li className="border-t border-hairline first:border-t-0">
      <button
        type="button"
        aria-pressed={isSelected}
        onClick={onSelect}
        className={`block w-full cursor-pointer p-4 text-left transition-colors focus-visible:-outline-offset-2 ${
          isSelected ? "bg-seal" : "hover:bg-seal/40"
        }`}
      >
        <span className="flex items-baseline justify-between gap-3">
          <span className="flex items-center gap-2.5">
            <span className="text-xl font-medium">Route {route.id}</span>
            {isRecommended && (
              <span className="bg-ink px-1.5 py-0.5 font-mono text-[0.6875rem] leading-4 tracking-[0.08em] text-ground uppercase">
                Recommended
              </span>
            )}
          </span>
          <span className="text-base whitespace-nowrap">{formatDuration(route.duration_seconds)}</span>
        </span>
        <span className="mt-0.5 block text-sm text-ink-muted">
          {formatMiles(route.distance_miles)}, arrives {formatLocalTime(route.arrival, timeZoneOfArrival)}
        </span>

        <span aria-hidden="true" className="mt-3 flex h-2 gap-px">
          {segments.map((segment) => (
            <span
              key={segment.level}
              style={{ width: `${segment.percent}%`, backgroundColor: RISK_COLOR[segment.level] }}
            />
          ))}
        </span>
        <span className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {segments.map((segment) => (
            <span key={segment.level} className="flex items-center gap-1.5 whitespace-nowrap">
              <RiskGlyph level={segment.level} className="size-3" />
              {RISK_LABEL[segment.level]} {formatMiles(segment.miles)}
            </span>
          ))}
        </span>
        <span className="mt-1 block text-sm text-ink-muted">Average risk {route.average_risk.toFixed(2)} of 4</span>
      </button>
    </li>
  );
}

interface TripResultsProps {
  plan: TripPlan;
  places: { origin: string; destination: string };
  loadLb: number;
  selectedRouteId: string;
  onSelectRoute: (routeId: string) => void;
  onSelectCheckpoint: (index: number) => void;
  onEditTrip: () => void;
}

export function TripResults({
  plan,
  places,
  loadLb,
  selectedRouteId,
  onSelectRoute,
  onSelectCheckpoint,
  onEditTrip,
}: TripResultsProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const recommended = plan.recommended_route_id;
  const selected = routeById(plan, selectedRouteId);

  useEffect(() => {
    // Moves keyboard and screen reader users to the answer, and scrolls it into view on a phone.
    headingRef.current?.focus();
  }, [plan]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 text-sm text-ink-muted">
          <p className="text-base text-ink">
            {places.origin} to {places.destination}
          </p>
          <p className="mt-0.5">
            Departs {formatLocalTime(plan.departure, plan.timezone)}, {formatPounds(loadLb)}
          </p>
        </div>
        <button
          type="button"
          onClick={onEditTrip}
          className="h-9 shrink-0 cursor-pointer border border-hairline px-3 text-sm transition-colors hover:border-ink"
        >
          Edit trip
        </button>
      </div>

      <div>
        <h1
          ref={headingRef}
          tabIndex={-1}
          className="text-[2.5rem] leading-[1.05] tracking-[-0.02em] text-balance outline-none"
        >
          {recommended ? `Take Route ${recommended}` : "No safe route at this departure"}
        </h1>
        <p className="mt-3 text-body text-ink-muted">
          {recommended
            ? recommendationReason(plan)
            : "Every route has miles in No Travel conditions. Try a different departure time."}
        </p>
      </div>

      <div>
        <h2 className="mb-2 font-mono text-label text-ink-muted uppercase">Routes compared</h2>
        <ul className="border border-hairline">
          {rankedRoutes(plan).map((route) => (
            <RouteRow
              key={route.id}
              route={route}
              timeZoneOfArrival={route.checkpoints.at(-1)!.timezone}
              isRecommended={route.id === recommended}
              isSelected={route.id === selectedRouteId}
              onSelect={() => onSelectRoute(route.id)}
            />
          ))}
        </ul>
        {plan.routes.length < 3 && (
          <p className="mt-2 text-sm text-ink-muted">
            Only {plan.routes.length} distinct {plan.routes.length === 1 ? "route exists" : "routes exist"} for this trip.
          </p>
        )}
      </div>

      <div>
        <h2 className="mb-2 font-mono text-label text-ink-muted uppercase">Route {selected.id} checkpoints</h2>
        <ol className="border-t border-hairline">
          {selected.checkpoints.map((checkpoint, index) => (
            <li key={index} className="border-b border-hairline">
              <button
                type="button"
                onClick={() => onSelectCheckpoint(index)}
                className="block w-full cursor-pointer px-1 py-2.5 text-left transition-colors hover:bg-seal/40 focus-visible:-outline-offset-2"
              >
                <span className="flex items-baseline justify-between gap-3">
                  <span className="text-base">
                    Mile {Math.round(checkpoint.mile).toLocaleString("en-US")}
                    <span className="ml-2 text-sm text-ink-muted">{formatLocalTime(checkpoint.eta, checkpoint.timezone)}</span>
                  </span>
                  <span className="flex shrink-0 items-center gap-1.5 text-sm font-medium">
                    <RiskGlyph level={checkpoint.risk} />
                    {RISK_LABEL[checkpoint.risk]}
                  </span>
                </span>
                <span className="mt-0.5 block">
                  <WeatherSummary checkpoint={checkpoint} />
                </span>
              </button>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
