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

interface MapPlateProps {
  children: ReactNode;
  /** Controls that sit below the map, outside its frame. */
  footer?: ReactNode;
  /** Set half off the plate's top-left corner, like a stamp on a printed plate. */
  seal?: ReactNode;
  className?: string;
}

/** Frames the map like a printed plate, with registration marks at its corners. */
export function MapPlate({ children, footer, seal, className = "" }: MapPlateProps) {
  return (
    <div className={`flex min-h-0 flex-col p-4 lg:p-8 ${className}`}>
      <div className="relative min-h-0 flex-1">
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
        {seal}
      </div>
      {footer}
    </div>
  );
}
