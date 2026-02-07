import { useState, useCallback } from "react";
import type { WikiArticle } from "../components/WikiCard";

const preloadImage = (src: string): Promise<void> => {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.src = src;
    img.onload = () => resolve();
    img.onerror = reject;
  });
};

import { API_BASE, apiUrl } from "../lib/apiBase";

export function useWikiArticles() {
  const [articles, setArticles] = useState<WikiArticle[]>([]);
  const [loading, setLoading] = useState(false);
  const [buffer, setBuffer] = useState<WikiArticle[]>([]);

  const fetchArticles = async (forBuffer = false) => {
    if (loading) return;
    setLoading(true);
    try {
      const response = await fetch(
        apiUrl(
          `/api/papers/random?` +
            new URLSearchParams({
              limit: "20",
            })
        )
      );

      const newArticles = (await response.json()) as WikiArticle[];

      // MVP: allow missing thumbnails (UI will fall back to gray background)
      const filtered = (newArticles || []).filter(
        (a) => a && a.pageid && a.url && a.extract
      );

      // Don't block UI on image preloading; on some mobile networks, a single stalled image
      // can keep the Promise pending and make the app look "stuck" on Loading...
      void Promise.allSettled(
        filtered
          .filter((article) => article.thumbnail?.source)
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
    }
    setLoading(false);
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

  return { articles, loading, fetchArticles: getMoreArticles };
}
