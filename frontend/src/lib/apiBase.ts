const PLACEHOLDER = /\[SENSITIVE\]|(^|[/.:-])(placeholder|change[-_ ]?me|your[-_ ]?api)([/.:-]|$)/i;

/**
 * Resolve the API base URL used by every axios client.
 *
 * The value comes from `VITE_API_URL` at build time. That value can be wrong
 * (an unresolved placeholder, a localhost URL baked into a production build,
 * or a relative path without `/api`), so invalid values fall back to `/api`.
 * `/api` is served by Caddy locally and rewritten to Render by Vercel.
 */
function configuredApiUrl(): string | undefined {
  const env = import.meta.env as Record<string, string | undefined> | undefined;
  return env?.VITE_API_URL;
}

export function resolveApiBase(
  raw: string | undefined = configuredApiUrl(),
  hostname: string | undefined = typeof window === "undefined" ? undefined : window.location.hostname
): string {
  const fallback = "/api";
  const value = typeof raw === "string" ? raw.trim() : "";

  if (!value || PLACEHOLDER.test(value)) {
    return fallback;
  }

  if (value.startsWith("/")) {
    const path = value.replace(/\/+$/, "");
    return path || fallback;
  }

  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return fallback;
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return fallback;
  }

  const localHosts = new Set(["localhost", "127.0.0.1", "0.0.0.0", "::1"]);
  const browserHost = (hostname ?? "").toLowerCase();
  const browserIsLocal =
    !browserHost || localHosts.has(browserHost) || browserHost.endsWith(".localhost");

  // A localhost API URL is only valid when the app itself runs on localhost.
  if (localHosts.has(url.hostname.toLowerCase()) && !browserIsLocal) {
    return fallback;
  }

  return url.toString().replace(/\/+$/, "");
}
