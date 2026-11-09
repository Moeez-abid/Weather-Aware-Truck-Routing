/** Shared parts of the trip form's fields, so every control has the same look and states. */

export const labelClass = "mb-1.5 block font-mono text-label text-ink-muted uppercase";

export const inputClass =
  "h-12 w-full rounded-none border border-hairline bg-field px-3 text-base text-ink transition-colors placeholder:text-ink-muted hover:border-ink-muted focus-visible:border-ink focus-visible:outline-offset-0 disabled:cursor-not-allowed disabled:opacity-60 aria-invalid:border-alert";

export function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) {
    return null;
  }
  return (
    <p id={id} className="mt-1.5 text-sm text-alert">
      {message}
    </p>
  );
}
