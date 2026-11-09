import { useEffect, useState } from "react";

import { checkHealth } from "../api/client";

type ServiceStatus = "connecting" | "online" | "offline";

const STATUS_LABEL: Record<ServiceStatus, string> = {
  // The hosted backend sleeps when idle and can take close to a minute to wake.
  connecting: "Connecting",
  online: "Service online",
  offline: "Service offline",
};

const STATUS_MARK: Record<ServiceStatus, string> = {
  connecting: "border border-ink-muted",
  online: "bg-ink",
  offline: "border border-ink bg-[linear-gradient(135deg,transparent_45%,var(--color-ink)_45%,var(--color-ink)_55%,transparent_55%)]",
};

export function TopBar() {
  const [status, setStatus] = useState<ServiceStatus>("connecting");

  useEffect(() => {
    const controller = new AbortController();
    checkHealth(controller.signal).then(
      () => setStatus("online"),
      () => {
        if (!controller.signal.aborted) {
          setStatus("offline");
        }
      },
    );
    return () => controller.abort();
  }, []);

  return (
    <header className="flex h-14 items-center justify-between gap-4 border-b border-hairline px-4 lg:px-8">
      <div className="flex min-w-0 items-baseline gap-5">
        <span className="text-xl font-medium tracking-[-0.01em]">Clearhaul</span>
        <span className="hidden truncate text-sm text-ink-muted sm:inline">Weather-aware truck routing</span>
      </div>
      <p role="status" className="flex shrink-0 items-center gap-2 font-mono text-label text-ink-muted uppercase">
        <span aria-hidden="true" className={`size-2 ${STATUS_MARK[status]}`} />
        {STATUS_LABEL[status]}
      </p>
    </header>
  );
}
