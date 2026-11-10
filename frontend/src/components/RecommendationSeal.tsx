// Circumference of the ring the text follows (radius 37), so the words spread evenly around it.
const RING_LENGTH = 2 * Math.PI * 37;

/**
 * The plate's stamp, stating the recommended route. It repeats what the results panel says, so it
 * is hidden from screen readers, and it sits only on wide screens where the plate has a margin.
 */
export function RecommendationSeal({ routeId }: { routeId: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 100 100"
      className="pointer-events-none absolute -top-8 -left-8 z-10 hidden size-24 lg:block"
    >
      <defs>
        <path id="seal-ring" d="M50 50m-37 0a37 37 0 1 1 74 0a37 37 0 1 1-74 0" />
      </defs>
      <circle cx="50" cy="50" r="49.5" fill="var(--color-seal)" />
      <circle cx="50" cy="50" r="28" fill="none" stroke="var(--color-ink)" strokeWidth="0.75" />
      <text className="fill-ink font-mono" fontSize="10.5" fontWeight="500">
        <textPath href="#seal-ring" textLength={RING_LENGTH - 6} lengthAdjust="spacing">
          RECOMMENDED · RECOMMENDED ·
        </textPath>
      </text>
      <text x="50" y="51" textAnchor="middle" dominantBaseline="central" className="fill-ink font-sans" fontSize="34">
        {routeId}
      </text>
    </svg>
  );
}
