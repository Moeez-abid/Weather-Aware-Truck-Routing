import type { Checkpoint } from "../api/types";
import { RiskGlyph } from "../risk/RiskGlyph";
import { RISK_LABEL } from "../risk/levels";
import { formatLocalTime, formatMiles } from "./format";
import { riskDrivers, type WeatherFactor } from "./recommendation";

export function WeatherSummary({ checkpoint }: { checkpoint: Checkpoint }) {
  const { wind_mph, rain_in_hr, snow_in_hr } = checkpoint.weather;
  const drivers = riskDrivers(checkpoint);
  const readings: [WeatherFactor, string][] = [
    ["wind", `Wind ${Math.round(wind_mph)} mph`],
    ["rain", `Rain ${rain_in_hr.toFixed(2)} in/hr`],
    ["snow", `Snow ${snow_in_hr.toFixed(2)} in/hr`],
  ];

  return (
    <p className="flex flex-wrap gap-x-3 text-sm text-ink-muted">
      {readings.map(([factor, text]) => (
        <span key={factor} className={drivers.includes(factor) ? "font-semibold text-ink" : undefined}>
          {text}
        </span>
      ))}
    </p>
  );
}

/** A checkpoint's full details, shown when it is chosen on the map. */
export function CheckpointDetail({ checkpoint, onClose }: { checkpoint: Checkpoint; onClose: () => void }) {
  return (
    <div className="font-sans text-ink">
      <button
        type="button"
        onClick={onClose}
        aria-label="Close checkpoint details"
        className="absolute top-1.5 right-1.5 grid size-7 cursor-pointer place-items-center text-ink-muted transition-colors hover:text-ink"
      >
        <svg aria-hidden="true" viewBox="0 0 16 16" className="size-3.5 stroke-current" strokeWidth="1.5">
          <path d="M3 3l10 10M13 3 3 13" />
        </svg>
      </button>
      <p className="flex items-center gap-1.5 text-base font-medium">
        <RiskGlyph level={checkpoint.risk} />
        {RISK_LABEL[checkpoint.risk]}
      </p>
      <p className="mt-1 text-sm">
        Mile {formatMiles(checkpoint.mile).replace(" mi", "")}, arrives {formatLocalTime(checkpoint.eta, checkpoint.timezone)}
      </p>
      <div className="mt-1">
        <WeatherSummary checkpoint={checkpoint} />
      </div>
    </div>
  );
}
