import type { RiskLevel } from "../api/types";
import { NO_TRAVEL_BAR, RISK_COLOR, RISK_SHAPE } from "./levels";

export function RiskGlyph({ level, className = "size-3.5" }: { level: RiskLevel; className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 16 16" className={`shrink-0 ${className}`}>
      <path d={RISK_SHAPE[level]} fill={RISK_COLOR[level]} />
      {level === "no_travel" && <path d={NO_TRAVEL_BAR} fill="#fff" />}
    </svg>
  );
}
