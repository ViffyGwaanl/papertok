import { useState, useCallback } from "react";
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

export function useWikiArticles() {
  const [articles, setArticles] = useState<WikiArticle[]>([]);
  const [loading, setLoading] = useState(false);
  const [buffer, setBuffer] = useState<WikiArticle[]>([]);
  const [offlineMode, setOfflineMode] = useState(false);

  const fetchArticles = async (forBuffer = false) => {
    if (loading) return;
    setLoading(true);

    // Ensure we have a bundled offline fallback even on first launch.
    // This should be fast (local file) and safe to call repeatedly.
    try {
      await primeOfflineCacheFromSeedPack();
    } catch {
      // ignore
    }

    const qs = new URLSearchParams({ limit: "20" });
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
      console.error("Error fetching articles:", error);
      // keep offlineMode as-is
    } finally {
      setLoading(false);
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

  return { articles, loading, offlineMode, fetchArticles: getMoreArticles };
}
