// Lightweight offline cache for the PaperTok frontend.
//
// Goals:
// - Cache the latest successful API responses so the app can still render when network/tunnel is down.
// - Keep implementation simple: localStorage + small LRU index.
// - Avoid caching huge payloads (markdown can be large) by limiting entries.

export type OfflineCacheEntry<T> = {
  ts: number; // epoch ms
  value: T;
};

type IndexItem = { key: string; ts: number };

type CacheIndex = {
  items: IndexItem[];
};

const INDEX_KEY = "papertok:offline_cache:index:v1";
const MAX_INDEX_ITEMS = 60;

function nowMs(): number {
  return Date.now();
}

function safeParse<T>(raw: string | null): T | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function loadIndex(): CacheIndex {
  return safeParse<CacheIndex>(localStorage.getItem(INDEX_KEY)) || { items: [] };
}

function saveIndex(idx: CacheIndex) {
  try {
    localStorage.setItem(INDEX_KEY, JSON.stringify(idx));
  } catch {
    // ignore (storage full / private mode)
  }
}

function touchKey(key: string) {
  const idx = loadIndex();
  const ts = nowMs();
  const filtered = idx.items.filter((x) => x.key !== key);
  filtered.unshift({ key, ts });
  idx.items = filtered.slice(0, MAX_INDEX_ITEMS);
  saveIndex(idx);
}

function pruneOrphans() {
  // Best-effort: remove index keys that no longer exist.
  const idx = loadIndex();
  const kept: IndexItem[] = [];
  for (const it of idx.items) {
    if (localStorage.getItem(it.key) != null) kept.push(it);
  }
  idx.items = kept;
  saveIndex(idx);
}

export function offlineCacheGet<T>(key: string, maxAgeMs: number): T | null {
  const entry = safeParse<OfflineCacheEntry<T>>(localStorage.getItem(key));
  if (!entry) return null;
  if (!entry.ts || entry.value === undefined) return null;
  if (nowMs() - entry.ts > maxAgeMs) return null;
  touchKey(key);
  return entry.value;
}

export function offlineCacheSet<T>(key: string, value: T): void {
  const entry: OfflineCacheEntry<T> = { ts: nowMs(), value };
  try {
    localStorage.setItem(key, JSON.stringify(entry));
    touchKey(key);
  } catch {
    // If storage is full, prune and retry once.
    try {
      pruneOrphans();
      // Drop oldest half.
      const idx = loadIndex();
      const drop = idx.items.slice(Math.floor(idx.items.length / 2));
      for (const it of drop) localStorage.removeItem(it.key);
      idx.items = idx.items.slice(0, Math.floor(idx.items.length / 2));
      saveIndex(idx);

      localStorage.setItem(key, JSON.stringify(entry));
      touchKey(key);
    } catch {
      // give up
    }
  }
}

export async function fetchJsonWithOfflineCache<T>(
  url: string,
  cacheKey: string,
  opts?: { maxAgeMs?: number; fetchTimeoutMs?: number }
): Promise<{ data: T; fromCache: boolean }> {
  const maxAgeMs = opts?.maxAgeMs ?? 1000 * 60 * 60 * 24; // 24h
  const fetchTimeoutMs = opts?.fetchTimeoutMs ?? 12000;

  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), fetchTimeoutMs);
  try {
    const r = await fetch(url, { signal: ctrl.signal });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = (await r.json()) as T;
    offlineCacheSet(cacheKey, j);
    return { data: j, fromCache: false };
  } catch {
    const cached = offlineCacheGet<T>(cacheKey, maxAgeMs);
    if (cached != null) return { data: cached, fromCache: true };
    throw new Error("fetch failed");
  } finally {
    clearTimeout(t);
  }
}

export async function fetchTextWithOfflineCache(
  url: string,
  cacheKey: string,
  opts?: { maxAgeMs?: number; fetchTimeoutMs?: number }
): Promise<{ text: string; fromCache: boolean }> {
  const maxAgeMs = opts?.maxAgeMs ?? 1000 * 60 * 60 * 24; // 24h
  const fetchTimeoutMs = opts?.fetchTimeoutMs ?? 12000;

  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), fetchTimeoutMs);
  try {
    const r = await fetch(url, { signal: ctrl.signal });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const text = await r.text();
    // markdown can be large; still cache, but caller should choose distinct keys and keep entries limited.
    offlineCacheSet(cacheKey, text);
    return { text, fromCache: false };
  } catch {
    const cached = offlineCacheGet<string>(cacheKey, maxAgeMs);
    if (cached != null) return { text: cached, fromCache: true };
    throw new Error("fetch failed");
  } finally {
    clearTimeout(t);
  }
}
