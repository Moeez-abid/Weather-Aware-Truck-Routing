import { useCombobox } from "downshift";
import { useEffect, useState } from "react";

import { searchPlaces } from "../api/client";
import type { Place } from "../api/types";
import { FieldError, inputClass, labelClass } from "./fields";

const SEARCH_DELAY_MS = 250;
const MIN_QUERY_LENGTH = 2;

type SearchStatus = "idle" | "searching" | "done" | "failed";

function usePlaceSearch(query: string) {
  const [places, setPlaces] = useState<Place[]>([]);
  const [status, setStatus] = useState<SearchStatus>("idle");

  useEffect(() => {
    const text = query.trim();
    if (text.length < MIN_QUERY_LENGTH) {
      setPlaces([]);
      setStatus("idle");
      return;
    }

    setStatus("searching");
    const controller = new AbortController();
    const timer = setTimeout(() => {
      searchPlaces(text, controller.signal).then(
        (results) => {
          setPlaces(results);
          setStatus("done");
        },
        () => {
          if (!controller.signal.aborted) {
            setPlaces([]);
            setStatus("failed");
          }
        },
      );
    }, SEARCH_DELAY_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  return { places, status };
}

function searchMessage(status: SearchStatus, hasPlaces: boolean): string | null {
  if (hasPlaces) {
    return null;
  }
  switch (status) {
    case "searching":
      return "Searching…";
    case "done":
      return "No matches. Check the spelling or try a nearby city.";
    case "failed":
      return "Address search isn't available right now. Please try again.";
    case "idle":
      return null;
  }
}

interface PlaceFieldProps {
  id: string;
  label: string;
  error?: string;
  onChange: (place: Place | null) => void;
}

export function PlaceField({ id, label, error, onChange }: PlaceFieldProps) {
  const [query, setQuery] = useState("");
  const { places, status } = usePlaceSearch(query);
  const errorId = `${id}-error`;

  const combobox = useCombobox<Place>({
    items: places,
    inputId: id,
    labelId: `${id}-label`,
    menuId: `${id}-menu`,
    itemToString: (place) => place?.label ?? "",
    itemToKey: (place) => place?.label,
    // Editing the text means the earlier choice no longer matches what is shown.
    stateReducer: (_state, { type, changes }) =>
      type === useCombobox.stateChangeTypes.InputChange ? { ...changes, selectedItem: null } : changes,
    onSelectedItemChange: ({ selectedItem }) => onChange(selectedItem ?? null),
    onInputValueChange: ({ inputValue, type }) =>
      setQuery(type === useCombobox.stateChangeTypes.InputChange ? (inputValue ?? "") : ""),
  });

  const message = searchMessage(status, places.length > 0);
  const showPanel = combobox.isOpen && (places.length > 0 || message !== null);

  return (
    <div className="relative">
      <label {...combobox.getLabelProps()} className={labelClass}>
        {label}
      </label>
      <input
        {...combobox.getInputProps({
          "aria-invalid": error ? true : undefined,
          "aria-describedby": error ? errorId : undefined,
        })}
        className={inputClass}
        placeholder="City or address"
        autoComplete="off"
        spellCheck={false}
      />
      <FieldError id={errorId} message={error} />
      <div className={showPanel ? "absolute inset-x-0 z-20 border border-t-0 border-ink bg-ground" : "hidden"}>
        {message && (
          <p role="status" className="px-3 py-3 text-sm text-ink-muted">
            {message}
          </p>
        )}
        <ul {...combobox.getMenuProps()} className="max-h-64 overflow-y-auto">
          {combobox.isOpen &&
            places.map((place, index) => (
              <li
                key={place.label}
                {...combobox.getItemProps({ item: place, index })}
                className={`cursor-pointer border-t border-hairline px-3 py-2.5 text-base first:border-t-0 ${
                  combobox.highlightedIndex === index ? "bg-seal" : ""
                }`}
              >
                {place.label}
              </li>
            ))}
        </ul>
      </div>
    </div>
  );
}
