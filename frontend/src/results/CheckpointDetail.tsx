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
export function CheckpointDetail({ checkpoint }: { checkpoint: Checkpoint }) {
  return (
    <div className="font-sans text-ink">
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
