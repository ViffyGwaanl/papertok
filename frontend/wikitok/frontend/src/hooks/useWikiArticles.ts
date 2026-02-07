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

const API_BASE =
  (import.meta as any).env?.VITE_API_BASE ||
  `${window.location.protocol}//${window.location.hostname}:8000`;

export function useWikiArticles() {
  const [articles, setArticles] = useState<WikiArticle[]>([]);
  const [loading, setLoading] = useState(false);
  const [buffer, setBuffer] = useState<WikiArticle[]>([]);

  const fetchArticles = async (forBuffer = false) => {
    if (loading) return;
    setLoading(true);
    try {
      const response = await fetch(
        `${API_BASE}/api/papers/random?` +
          new URLSearchParams({
            limit: "20",
          })
      );

      const newArticles = (await response.json()) as WikiArticle[];

      // MVP: allow missing thumbnails (UI will fall back to gray background)
      const filtered = (newArticles || []).filter(
        (a) => a && a.pageid && a.url && a.extract
      );

      await Promise.allSettled(
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
