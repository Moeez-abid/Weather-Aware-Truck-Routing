import type { ReactNode } from "react";

const CORNERS = [
  "-top-2 -left-2",
  "-top-2 -right-2",
  "-bottom-2 -left-2",
  "-bottom-2 -right-2",
];

/** Holds the map's place while it loads. */
export function MapPlaceholder() {
  return <div aria-hidden="true" className="dot-matrix absolute inset-0 bg-ground" />;
}

/** Frames the map like a printed plate, with registration marks at its corners. */
export function MapPlate({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`min-h-0 p-4 lg:p-8 ${className}`}>
      <div className="relative size-full">
        <div className="absolute inset-0 overflow-hidden border border-hairline">{children}</div>
        {CORNERS.map((position) => (
          <svg
            key={position}
            aria-hidden="true"
            viewBox="0 0 16 16"
            className={`pointer-events-none absolute size-4 stroke-ink ${position}`}
          >
            <path d="M8 0v16M0 8h16" strokeWidth="1" />
          </svg>
        ))}
      </div>
    </div>
  );
}
