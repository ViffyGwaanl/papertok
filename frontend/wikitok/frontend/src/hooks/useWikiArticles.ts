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
  (() => {
    // Prod / tunnel: backend serves frontend and API on the same origin (no :8000)
    // Local dev: if the frontend is not served from :8000, default API to :8000.
    const { protocol, hostname, port } = window.location;
    const isLocalhost = hostname === "localhost" || hostname === "127.0.0.1";
    if (isLocalhost && port && port !== "8000") {
      return `${protocol}//${hostname}:8000`;
    }
    return window.location.origin;
  })();

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
