import { useState, useCallback, useEffect, useRef } from "react";
import type { WikiArticle } from "../components/WikiCard";

import { API_BASE, apiUrl } from "../lib/apiBase";
import { fetchJsonWithOfflineCache } from "../lib/offlineCache";
import { primeOfflineCacheFromSeedPack } from "../lib/seedPack";

const preloadImage = (src: string): Promise<void> => {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.src = src;
    img.onload = () => resolve();
    img.onerror = reject;
  });
};

export function useWikiArticles(opts?: { lang?: string }) {
  const lang0 = (opts?.lang || "zh").toLowerCase() === "en" ? "en" : "zh";

  const [articles, setArticles] = useState<WikiArticle[]>([]);
  const [loading, setLoading] = useState(false);
  const [buffer, setBuffer] = useState<WikiArticle[]>([]);
  const [offlineMode, setOfflineMode] = useState(false);

  // Generation id to ignore stale in-flight fetches after language switch.
  const genRef = useRef(0);

  // When language changes, reset feed so we don't mix languages.
  useEffect(() => {
    genRef.current += 1;
    setArticles([]);
    setBuffer([]);
    setOfflineMode(false);
    // If a previous fetch was in-flight, don't let it block the next language fetch.
    setLoading(false);
  }, [lang0]);

  const fetchArticles = async (forBuffer = false) => {
    // capture the current generation (language version)
    const myGen = genRef.current;

    if (loading) return;
    setLoading(true);

    // Ensure we have a bundled offline fallback even on first launch.
    // This should be fast (local file) and safe to call repeatedly.
    try {
      await primeOfflineCacheFromSeedPack();
    } catch {
      // ignore
    }

    const qs = new URLSearchParams({ limit: "20", lang: lang0 });
    const urlPath = `/api/papers/random?${qs.toString()}`;
    const fullUrl = apiUrl(urlPath);
    const cacheKey = `papertok:feed:last:${qs.toString()}`;

    try {
      const { data: newArticles, fromCache } = await fetchJsonWithOfflineCache<WikiArticle[]>(
        fullUrl,
        cacheKey,
        {
          // If tunnel/network is down, allow showing cached feed from the last 24h.
          maxAgeMs: 1000 * 60 * 60 * 24,
          fetchTimeoutMs: 12000,
        }
      );

      // If language changed while this request was in-flight, ignore the result.
      if (genRef.current !== myGen) return;

      setOfflineMode(fromCache);

      // MVP: allow missing thumbnails (UI will fall back to gray background)
      const filtered = (newArticles || []).filter(
        (a) => a && a.pageid && a.url && a.extract
      );

      // Don't block UI on image preloading; on some mobile networks, a single stalled image
      // can keep the Promise pending and make the app look "stuck" on Loading...
      void Promise.allSettled(
        filtered
          .filter((article) => article.thumbnail?.source)
          .slice(0, 20)
          .map((article) => {
            const src = article.thumbnail!.source;
            const finalSrc = src.startsWith("http") ? src : `${API_BASE}${src}`;
            return preloadImage(finalSrc);
          })
      );

      if (forBuffer) {
        setBuffer(filtered);
      } else {
        setArticles((prev) => [...prev, ...filtered]);
        fetchArticles(true);
      }
    } catch (error) {
      // If language switched, ignore errors from stale requests.
      if (genRef.current !== myGen) return;
      console.error("Error fetching articles:", error);
      // keep offlineMode as-is
    } finally {
      // Only clear loading if we're still on the same language generation.
      if (genRef.current === myGen) setLoading(false);
    }
  };

  const getMoreArticles = useCallback(() => {
    if (buffer.length > 0) {
      setArticles((prev) => [...prev, ...buffer]);
      setBuffer([]);
      fetchArticles(true);
    } else {
      fetchArticles(false);
    }
  }, [buffer]);

  return { articles, loading, offlineMode, fetchArticles: getMoreArticles, lang: lang0, setArticles };
}
