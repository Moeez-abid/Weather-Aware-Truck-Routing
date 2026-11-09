import { useEffect, useRef, useState, type FormEvent } from "react";

import { getTimeZone, type ApiError } from "../api/client";
import type { CheckpointInterval, Place, TripRequest } from "../api/types";
import { FieldError, inputClass, labelClass } from "./fields";
import {
  browserTimeZone,
  defaultDeparture,
  serverFieldErrors,
  timeZoneName,
  toTripRequest,
  validateTripForm,
  wallClock,
  type TripFormErrors,
  type TripFormField,
  type TripFormValues,
} from "./formValues";
import { PlaceField } from "./PlaceField";

const INTERVALS: CheckpointInterval[] = [10, 25, 50];
const FIELD_ORDER: TripFormField[] = ["origin", "destination", "departure", "load", "interval"];

function fieldId(field: TripFormField): string {
  return `trip-${field}`;
}

function focusFirstError(errors: TripFormErrors) {
  const first = FIELD_ORDER.find((field) => errors[field]);
  if (first) {
    document.getElementById(fieldId(first))?.focus();
  }
}

function useOriginTimeZone(origin: Place | null): string | null {
  const [timeZone, setTimeZone] = useState<string | null>(null);

  useEffect(() => {
    setTimeZone(null);
    if (!origin) {
      return;
    }
    const controller = new AbortController();
    // If this fails the form still works, and the backend still checks the departure.
    getTimeZone(origin, controller.signal).then(setTimeZone, () => undefined);
    return () => controller.abort();
  }, [origin]);

  return timeZone;
}

interface TripFormProps {
  onSubmit: (trip: TripRequest) => void;
  isSubmitting: boolean;
  serverError: ApiError | null;
}

export function TripForm({ onSubmit, isSubmitting, serverError }: TripFormProps) {
  const [values, setValues] = useState<TripFormValues>(() => ({
    origin: null,
    destination: null,
    departure: defaultDeparture(browserTimeZone(), new Date()),
    load: "",
    interval: 25,
  }));
  const [errors, setErrors] = useState<TripFormErrors>({});
  const departureEdited = useRef(false);
  const timeZone = useOriginTimeZone(values.origin);

  useEffect(() => {
    if (timeZone && !departureEdited.current) {
      setValues((current) => ({ ...current, departure: defaultDeparture(timeZone, new Date()) }));
    }
  }, [timeZone]);

  useEffect(() => {
    if (serverError) {
      const fieldErrors = serverFieldErrors(serverError.fields);
      setErrors(fieldErrors);
      focusFirstError(fieldErrors);
    }
  }, [serverError]);

  function update<F extends TripFormField>(field: F, value: TripFormValues[F]) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validateTripForm(values, timeZone, new Date());
    setErrors(found);
    if (Object.keys(found).length > 0) {
      focusFirstError(found);
      return;
    }
    onSubmit(toTripRequest(values));
  }

  const now = new Date();
  const departureHint = timeZone ? `Local time at the origin: ${timeZoneName(timeZone, now)}` : "Local time at the origin";

  return (
    <form noValidate onSubmit={handleSubmit} aria-busy={isSubmitting} className="flex flex-col gap-5">
      <PlaceField
        id={fieldId("origin")}
        label="Origin"
        error={errors.origin}
        onChange={(place) => update("origin", place)}
      />
      <PlaceField
        id={fieldId("destination")}
        label="Destination"
        error={errors.destination}
        onChange={(place) => update("destination", place)}
      />

      <div>
        <label htmlFor={fieldId("departure")} className={labelClass}>
          Departure
        </label>
        <input
          id={fieldId("departure")}
          type="datetime-local"
          className={inputClass}
          value={values.departure}
          min={timeZone ? wallClock(now, timeZone) : undefined}
          aria-invalid={errors.departure ? true : undefined}
          aria-describedby={`${fieldId("departure")}-hint${errors.departure ? ` ${fieldId("departure")}-error` : ""}`}
          onChange={(event) => {
            departureEdited.current = true;
            update("departure", event.target.value);
          }}
        />
        <p id={`${fieldId("departure")}-hint`} className="mt-1.5 text-sm text-ink-muted">
          {departureHint}
        </p>
        <FieldError id={`${fieldId("departure")}-error`} message={errors.departure} />
      </div>

      <div className="grid grid-cols-1 gap-5 min-[26rem]:grid-cols-2 min-[26rem]:gap-4">
        <div>
          <label htmlFor={fieldId("load")} className={labelClass}>
            Load weight (lb)
          </label>
          <input
            id={fieldId("load")}
            type="text"
            inputMode="numeric"
            autoComplete="off"
            className={inputClass}
            value={values.load}
            aria-invalid={errors.load ? true : undefined}
            aria-describedby={errors.load ? `${fieldId("load")}-error` : undefined}
            onChange={(event) => update("load", event.target.value)}
          />
          <FieldError id={`${fieldId("load")}-error`} message={errors.load} />
        </div>

        <fieldset>
          <legend className={labelClass}>Weather check every</legend>
          <div className="grid h-12 grid-cols-3 border border-hairline">
            {INTERVALS.map((interval) => (
              <label
                key={interval}
                className="flex cursor-pointer items-center justify-center border-l border-hairline text-base whitespace-nowrap transition-colors first:border-l-0 hover:bg-seal has-checked:bg-ink has-checked:text-ground has-focus-visible:outline-2 has-focus-visible:outline-ink"
              >
                <input
                  id={interval === values.interval ? fieldId("interval") : undefined}
                  type="radio"
                  name="interval"
                  className="sr-only"
                  checked={interval === values.interval}
                  onChange={() => update("interval", interval)}
                />
                {interval} mi
              </label>
            ))}
          </div>
          <FieldError id={`${fieldId("interval")}-error`} message={errors.interval} />
        </fieldset>
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="mt-1 h-12 cursor-pointer bg-ink font-mono text-sm tracking-[0.1em] text-ground uppercase transition-colors hover:bg-ink-hover active:bg-ink disabled:cursor-progress disabled:opacity-70"
      >
        {isSubmitting ? "Comparing routes…" : "Compare routes"}
      </button>
    </form>
  );
}
