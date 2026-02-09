import { offlineCacheGet, offlineCacheSet } from "./offlineCache";

export type SeedPack = {
  generated_at?: string;
  source?: { kind?: string; earliest_day?: string; count?: number };
  cards?: any[];
  details?: Record<string, any>;
};

let _primed = false;

async function loadSeedPack(): Promise<SeedPack | null> {
  try {
    const r = await fetch("/seed/seed-pack.json", { cache: "no-store" });
    if (!r.ok) return null;
    return (await r.json()) as SeedPack;
  } catch {
    return null;
  }
}

/**
 * Prime offline cache using the bundled seed pack.
 *
 * This makes the app usable on first launch even if the tunnel/network is down.
 */
export async function primeOfflineCacheFromSeedPack(): Promise<void> {
  if (_primed) return;
  _primed = true;

  // If we already have a cached feed, don't override it.
  const existing = offlineCacheGet<any>("papertok:feed:last:limit=20", 1000 * 60 * 60 * 24 * 365);
  if (existing) return;

  const seed = await loadSeedPack();
  if (!seed?.cards || !Array.isArray(seed.cards) || seed.cards.length === 0) return;

  try {
    // Feed cache key used by useWikiArticles.ts
    offlineCacheSet("papertok:feed:last:limit=20", seed.cards);

    const details = seed.details || {};
    for (const k of Object.keys(details)) {
      const d = details[k];
      if (!d || !d.id) continue;
      offlineCacheSet(`papertok:paper_detail:${d.id}`, d);
    }
  } catch {
    // ignore
  }
}
