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

  // If we already have a cached feed (old key or lang-scoped key), don't override it.
  const existingOld = offlineCacheGet<any>("papertok:feed:last:limit=20", 1000 * 60 * 60 * 24 * 365);
  const existingZh = offlineCacheGet<any>(
    "papertok:feed:last:limit=20&lang=zh",
    1000 * 60 * 60 * 24 * 365
  );
  if (existingOld || existingZh) return;

  const seed = await loadSeedPack();
  if (!seed?.cards || !Array.isArray(seed.cards) || seed.cards.length === 0) return;

  try {
    // Feed cache key used by useWikiArticles.ts (lang-scoped).
    // Seed pack is currently ZH-first; EN offline seeding can be added later.
    offlineCacheSet("papertok:feed:last:limit=20&lang=zh", seed.cards);

    const details = seed.details || {};
    for (const k of Object.keys(details)) {
      const d = details[k];
      if (!d || !d.id) continue;
      // Match the keys used by WikiCard.tsx / detail fetch.
      offlineCacheSet(`papertok:paper_detail:${d.id}:lang=zh`, d);
    }
  } catch {
    // ignore
  }
}
