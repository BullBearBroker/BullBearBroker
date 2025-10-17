export type AnalyticsEventPayload = Record<string, unknown> | undefined;

type AnalyticsClient = {
  track?: (event: string, payload?: AnalyticsEventPayload) => void;
};

function getClient(): AnalyticsClient | undefined {
  if (typeof window === "undefined") {
    return undefined;
  }
  const candidate = (window as typeof window & { analytics?: AnalyticsClient }).analytics;
  return candidate || undefined;
}

export function trackEvent(event: string, payload?: AnalyticsEventPayload) {
  const client = getClient();
  if (client?.track) {
    try {
      client.track(event, payload);
    } catch (error) {
      if (process.env.NODE_ENV !== "production") {
        console.error("analytics track failed", error);
      }
    }
    return;
  }

  if (process.env.NODE_ENV !== "production") {
    console.info("analytics event", event, payload);
  }
}
