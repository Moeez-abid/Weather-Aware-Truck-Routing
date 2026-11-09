import type { RiskLevel } from "../api/types";

/** Lowest to highest. A level's position matches the digit the heatmap frames use for it. */
export const RISK_LEVELS: RiskLevel[] = ["low", "moderate", "high", "severe", "no_travel"];

export const RISK_LABEL: Record<RiskLevel, string> = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  severe: "Severe",
  no_travel: "No Travel",
};

export const RISK_COLOR: Record<RiskLevel, string> = {
  low: "#2f8f66",
  moderate: "#e0ab00",
  high: "#e36f12",
  severe: "#c4232b",
  no_travel: "#3b1150",
};

/**
 * A shape for each level in a 16-unit box, so that risk never depends on color alone.
 * The upper levels borrow road signs: yield triangle, warning diamond and stop octagon.
 */
export const RISK_SHAPE: Record<RiskLevel, string> = {
  low: "M8 3a5 5 0 1 0 0 10A5 5 0 0 0 8 3Z",
  moderate: "M8 2 15 14H1Z",
  high: "M2.5 2.5h11v11h-11Z",
  severe: "M8 .5 15.5 8 8 15.5.5 8Z",
  no_travel: "M5 .5h6L15.5 5v6L11 15.5H5L.5 11V5Z",
};

/** The bar across the stop-sign shape, drawn in white. */
export const NO_TRAVEL_BAR = "M4 7h8v2H4Z";
