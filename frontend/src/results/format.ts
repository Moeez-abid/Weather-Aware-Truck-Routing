/** Formats a length of time, such as "15 h 39 min" or "45 min". */
export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) {
    return `${minutes} min`;
  }
  return minutes === 0 ? `${hours} h` : `${hours} h ${minutes} min`;
}

/** Formats a distance. Short distances keep a decimal so that 0.4 miles doesn't read as none. */
export function formatMiles(miles: number): string {
  const digits = miles > 0 && miles < 10 ? 1 : 0;
  const number = miles.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  return `${number} mi`;
}

export function formatPounds(pounds: number): string {
  return `${pounds.toLocaleString("en-US")} lb`;
}

/** Formats a moment in a place's own timezone, such as "Mon 3:12 PM CST". */
export function formatLocalTime(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone,
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  })
    .format(new Date(iso))
    .replace(",", "");
}
