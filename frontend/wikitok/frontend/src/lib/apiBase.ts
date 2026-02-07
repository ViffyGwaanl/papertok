// Single source of truth for API/asset base URL.
//
// Priority:
// 1) VITE_API_BASE (recommended for Capacitor/WebView builds)
// 2) window.location.origin (recommended for same-origin web deploy)
// 3) localhost dev fallback to :8000

const envBase = (import.meta as unknown as { env?: { VITE_API_BASE?: string } }).env?.VITE_API_BASE;

function computeBase(): string {
  if (envBase && envBase.trim()) return envBase.trim().replace(/\/$/, "");

  const { protocol, hostname, port, origin } = window.location;
  const isLocalhost = hostname === "localhost" || hostname === "127.0.0.1";

  // Local dev: if frontend is served from a non-8000 port, assume backend is :8000.
  if (isLocalhost && port && port !== "8000") {
    return `${protocol}//${hostname}:8000`;
  }

  // Default: same-origin.
  return origin;
}

export const API_BASE = computeBase();

export function apiUrl(path: string): string {
  if (!path) return API_BASE;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  if (!path.startsWith("/")) path = `/${path}`;
  return `${API_BASE}${path}`;
}

export function assetUrl(path: string): string {
  // Currently the same logic as apiUrl; kept separate for clarity.
  return apiUrl(path);
}
