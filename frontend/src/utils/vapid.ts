// QA: VAPID helper – utilidades compartidas para Web Push

const PLACEHOLDER_PATTERNS = ["placeholder", "change_me", "example"];

function decodeBase64(base64: string): string {
  if (typeof atob === "function") {
    return atob(base64);
  }
  if (typeof Buffer !== "undefined") {
    return Buffer.from(base64, "base64").toString("binary");
  }
  throw new Error("Base64 decoding is not supported in this environment");
}

export function urlBase64ToUint8Array(base64Url: string): Uint8Array {
  const sanitized = base64Url.trim();
  const padding = "=".repeat((4 - (sanitized.length % 4)) % 4);
  const base64 = (sanitized + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = decodeBase64(base64);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; ++i) {
    output[i] = raw.charCodeAt(i);
  }
  return output;
}

export function isLikelyVapidPlaceholder(key: string | null | undefined): boolean {
  if (!key) {
    return true;
  }
  const normalized = key.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return PLACEHOLDER_PATTERNS.some((pattern) => normalized.includes(pattern));
}

export function normalizeVapidKey(key: string | null | undefined): string {
  return typeof key === "string" ? key.trim() : "";
}
