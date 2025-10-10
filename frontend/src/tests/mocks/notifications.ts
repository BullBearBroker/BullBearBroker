export interface MockNotificationEvent {
  id: string;
  title: string;
  body: string;
  timestamp: string | number;
  type?: string;
  receivedAt?: string;
  payload?: Record<string, unknown>;
  meta?: Record<string, unknown>;
}

export function createMockNotificationEvent(
  overrides: Partial<MockNotificationEvent> = {},
): MockNotificationEvent {
  const baseTimestamp = overrides.timestamp ?? overrides.receivedAt ?? Date.now();

  return {
    id: overrides.id ?? "mock-event",
    title: overrides.title ?? "Notificación de prueba",
    body: overrides.body ?? "Contenido de prueba",
    timestamp:
      typeof baseTimestamp === "number" ? baseTimestamp : new Date(baseTimestamp).toISOString(),
    receivedAt:
      overrides.receivedAt ??
      (typeof baseTimestamp === "number" ? new Date(baseTimestamp).toISOString() : baseTimestamp),
    ...overrides,
  };
}
