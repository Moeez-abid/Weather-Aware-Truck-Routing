/** The trip form's rules, kept free of React so they can be tested directly. */

import type { CheckpointInterval, Place, TripRequest } from "../api/types";

export interface TripFormValues {
  origin: Place | null;
  destination: Place | null;
  /** Local time at the origin, as a date-time input reports it: 2026-11-10T09:30. */
  departure: string;
  load: string;
  interval: CheckpointInterval;
}

export type TripFormField = keyof TripFormValues;
export type TripFormErrors = Partial<Record<TripFormField, string>>;

export const MAX_LOAD_LB = 200_000;

const QUARTER_HOUR_MS = 15 * 60 * 1000;
// Matches the backend, which allows for the moments between filling in the form and sending it.
const DEPARTURE_GRACE_MS = 15 * 60 * 1000;
const DEPARTURE_FORMAT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;

export function browserTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

/** The wall-clock time in a timezone, in the format a date-time input uses. */
export function wallClock(moment: Date, timeZone: string): string {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone,
      hourCycle: "h23",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    })
      .formatToParts(moment)
      .map((part) => [part.type, part.value]),
  );
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

/** The next quarter hour, as local time in the given timezone. */
export function defaultDeparture(timeZone: string, now: Date): string {
  const next = Math.ceil(now.getTime() / QUARTER_HOUR_MS) * QUARTER_HOUR_MS;
  return wallClock(new Date(next), timeZone);
}

/** A timezone's full name at a given moment, such as "Central Standard Time". */
export function timeZoneName(timeZone: string, moment: Date): string {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone, timeZoneName: "long" }).formatToParts(moment);
  return parts.find((part) => part.type === "timeZoneName")?.value ?? timeZone;
}

/** Reads a load such as "40,000". Returns null if it isn't a number. */
export function parseLoad(load: string): number | null {
  const cleaned = load.replace(/[,\s]/g, "");
  if (!/^\d+(\.\d+)?$/.test(cleaned)) {
    return null;
  }
  return Number(cleaned);
}

function departureError(departure: string, timeZone: string | null, now: Date): string | undefined {
  if (!DEPARTURE_FORMAT.test(departure)) {
    return "Choose a departure date and time.";
  }
  // Without the origin's timezone the backend makes this check instead.
  if (timeZone && departure < wallClock(new Date(now.getTime() - DEPARTURE_GRACE_MS), timeZone)) {
    return "Departure time is in the past.";
  }
  return undefined;
}

function loadError(load: string): string | undefined {
  if (load.trim() === "") {
    return "Enter the load weight in pounds.";
  }
  const pounds = parseLoad(load);
  if (pounds === null) {
    return "Enter the load as a number of pounds.";
  }
  if (pounds > MAX_LOAD_LB) {
    return `Load can't be more than ${MAX_LOAD_LB.toLocaleString("en-US")} lb.`;
  }
  return undefined;
}

/** Checks the form, using the origin's timezone once it is known. */
export function validateTripForm(
  values: TripFormValues,
  timeZone: string | null,
  now: Date,
): TripFormErrors {
  const errors: TripFormErrors = {
    origin: values.origin ? undefined : "Choose a starting place from the list.",
    destination: values.destination ? undefined : "Choose a destination from the list.",
    departure: departureError(values.departure, timeZone, now),
    load: loadError(values.load),
  };
  return Object.fromEntries(Object.entries(errors).filter(([, message]) => message));
}

/** Builds the API request. Only call this after validation has passed. */
export function toTripRequest(values: TripFormValues): TripRequest {
  const { origin, destination } = values;
  if (!origin || !destination) {
    throw new Error("The trip needs an origin and a destination.");
  }
  return {
    origin: { lat: origin.lat, lon: origin.lon },
    destination: { lat: destination.lat, lon: destination.lon },
    departure: values.departure,
    load_lb: parseLoad(values.load) ?? 0,
    interval_miles: values.interval,
  };
}

const SERVER_FIELDS: Record<string, TripFormField> = {
  origin: "origin",
  destination: "destination",
  departure: "departure",
  load_lb: "load",
  interval_miles: "interval",
};

/** Finds the first message in a backend error, which may be nested under a field such as origin.lat. */
function firstMessage(value: unknown): string | undefined {
  if (typeof value === "string") {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map(firstMessage).find(Boolean);
  }
  if (typeof value === "object" && value !== null) {
    return Object.values(value).map(firstMessage).find(Boolean);
  }
  return undefined;
}

/** Turns the backend's validation errors into messages for the form's fields. */
export function serverFieldErrors(fields: Record<string, unknown>): TripFormErrors {
  const errors: TripFormErrors = {};
  for (const [name, value] of Object.entries(fields)) {
    const field = SERVER_FIELDS[name];
    const message = firstMessage(value);
    if (field && message) {
      errors[field] = message;
    }
  }
  return errors;
}
