import { useEffect, useState } from "react";

import { checkHealth } from "../api/client";

/** "connecting" lasts until the backend answers. A hosted backend that was idle can take a minute to wake. */
export type ServiceStatus = "connecting" | "online" | "offline";

export function useServiceStatus(): ServiceStatus {
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

  return status;
}
