type FeatureFlags = Record<string, boolean>;

let cachedFlags: FeatureFlags | null = null;

function normalizeFlags(raw: unknown): FeatureFlags {
  if (!raw) return {};

  if (Array.isArray(raw)) {
    return raw.reduce<FeatureFlags>((acc, value) => {
      if (typeof value === "string" && value.trim()) {
        acc[value.trim()] = true;
      }
      return acc;
    }, {});
  }

  if (typeof raw === "object") {
    return Object.entries(raw as Record<string, unknown>).reduce<FeatureFlags>(
      (acc, [key, value]) => {
        if (!key) return acc;
        const normalized = String(key).trim();
        if (!normalized) return acc;
        if (typeof value === "boolean") {
          acc[normalized] = value;
        } else if (typeof value === "string") {
          acc[normalized] = value.toLowerCase() in { true: true, on: true, yes: true };
        } else if (typeof value === "number") {
          acc[normalized] = value !== 0;
        }
        return acc;
      },
      {}
    );
  }

  if (typeof raw === "string") {
    const parts = raw
      .split(/[,\s]+/)
      .map((part) => part.trim())
      .filter(Boolean);
    return parts.reduce<FeatureFlags>((acc, value) => {
      acc[value] = true;
      return acc;
    }, {});
  }

  return {};
}

function loadFeatureFlags(): FeatureFlags {
  if (cachedFlags) {
    return cachedFlags;
  }

  const raw = process.env.NEXT_PUBLIC_FEATURE_FLAGS;
  if (!raw) {
    cachedFlags = {};
    return cachedFlags;
  }

  try {
    const parsed = JSON.parse(raw);
    cachedFlags = normalizeFlags(parsed);
  } catch {
    cachedFlags = normalizeFlags(raw);
  }

  return cachedFlags;
}

export function getFeatureFlag(name: string): boolean {
  const flags = loadFeatureFlags();
  return Boolean(flags[name]);
}

export function __resetFeatureFlagsForTests(): void {
  cachedFlags = null;
}
