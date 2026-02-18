import { useEffect, useRef, useCallback, useState } from "react";
import { t } from "./lib/i18n";
import { WikiCard } from "./components/WikiCard";
import { PaperDetailModal } from "./components/PaperDetailModal";
import { AdminPage } from "./components/AdminPage";
import { Loader2, Search, X, Download } from "lucide-react";
// (Removed @vercel/analytics for local PaperTok deployment)
// LanguageSelector removed in PaperTok build
import { useLikedArticles } from "./contexts/LikedArticlesContext";
import { useWikiArticles } from "./hooks/useWikiArticles";

function MainPage() {
  const [showAbout, setShowAbout] = useState(false);
  const [showLikes, setShowLikes] = useState(false);

  const [contentLang, setContentLang] = useState<'zh' | 'en'>(() => {
    const saved = (localStorage.getItem('papertok:contentLang') || 'zh').toLowerCase();
    return saved === 'en' ? 'en' : 'zh';
  });

  useEffect(() => {
    localStorage.setItem('papertok:contentLang', contentLang);
  }, [contentLang]);

  const { articles, loading, offlineMode, fetchArticles, setArticles } = useWikiArticles({ lang: contentLang });
  const { likedArticles, toggleLike } = useLikedArticles();

  // Lightweight in-app navigation: /?paper=<id>&lang=<zh|en>
  const [routePaperId, setRoutePaperId] = useState<number | null>(null);
  const [routePaperTitle, setRoutePaperTitle] = useState<string | undefined>(undefined);

  const _applyRouteFromUrl = useCallback(() => {
    const params = new URLSearchParams(window.location.search || '');
    const raw = (params.get('paper') || '').trim();
    const pid = raw ? Number.parseInt(raw, 10) : NaN;
    setRoutePaperId(Number.isFinite(pid) ? pid : null);
    setRoutePaperTitle(undefined);

    const qLang = (params.get('lang') || '').toLowerCase();
    if (qLang === 'zh' || qLang === 'en') {
      setContentLang(qLang as any);
    }
  }, []);

  useEffect(() => {
    _applyRouteFromUrl();
    window.addEventListener('popstate', _applyRouteFromUrl);
    return () => window.removeEventListener('popstate', _applyRouteFromUrl);
  }, [_applyRouteFromUrl]);

  const openPaperRoute = useCallback((paperId: number, title?: string) => {
    const params = new URLSearchParams(window.location.search || '');
    params.set('paper', String(paperId));
    params.set('lang', contentLang);
    const qs = params.toString();
    const url = qs ? `/?${qs}` : '/';
    window.history.pushState({}, '', url);
    setRoutePaperId(paperId);
    setRoutePaperTitle(title);
  }, [contentLang]);

  const closePaperRoute = useCallback(() => {
    const params = new URLSearchParams(window.location.search || '');
    params.delete('paper');
    params.delete('lang');
    const qs = params.toString();
    const url = qs ? `/?${qs}` : '/';
    window.history.pushState({}, '', url);
    setRoutePaperId(null);
    setRoutePaperTitle(undefined);
  }, []);

  // Keep URL lang in sync when the route modal is open.
  useEffect(() => {
    if (!routePaperId) return;
    const params = new URLSearchParams(window.location.search || '');
    params.set('paper', String(routePaperId));
    params.set('lang', contentLang);
    const qs = params.toString();
    window.history.replaceState({}, '', qs ? `/?${qs}` : '/');
  }, [routePaperId, contentLang]);
  const observerTarget = useRef(null);
  const [searchQuery, setSearchQuery] = useState("");

  const handleObserver = useCallback(
    (entries: IntersectionObserverEntry[]) => {
      const [target] = entries;
      if (target.isIntersecting && !loading) {
        fetchArticles();
      }
    },
    [loading, fetchArticles]
  );

  useEffect(() => {
    const observer = new IntersectionObserver(handleObserver, {
      threshold: 0.1,
      rootMargin: "100px",
    });

    if (observerTarget.current) {
      observer.observe(observerTarget.current);
    }

    return () => observer.disconnect();
  }, [handleObserver]);

  useEffect(() => {
    fetchArticles();
  }, [contentLang]);

  const filteredLikedArticles = likedArticles.filter(
    (article) =>
      article.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      article.extract.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleExport = () => {
    const simplifiedArticles = likedArticles.map((article) => ({
      title: article.title,
      url: article.url,
      extract: article.extract,
      thumbnail: article.thumbnail?.source || null,
    }));

    const dataStr = JSON.stringify(simplifiedArticles, null, 2);
    const dataUri =
      "data:application/json;charset=utf-8," + encodeURIComponent(dataStr);

    const exportFileDefaultName = `papertok-favorites-${new Date().toISOString().split("T")[0]
      }.json`;

    const linkElement = document.createElement("a");
    linkElement.setAttribute("href", dataUri);
    linkElement.setAttribute("download", exportFileDefaultName);
    linkElement.click();
  };

  return (
    <div className="h-screen w-full bg-black text-white overflow-y-scroll snap-y snap-mandatory hide-scroll">
      <div className="fixed z-50 safe-top-4 safe-left-4">
        <button
          onClick={() => window.location.reload()}
          className="text-2xl font-bold text-white drop-shadow-lg hover:opacity-80 transition-opacity"
        >
          PaperTok
        </button>
        {offlineMode && (
          <div className="mt-2 inline-flex items-center gap-2 rounded bg-yellow-500/15 border border-yellow-500/30 px-2 py-1 text-xs text-yellow-100">
            {t(contentLang, 'offlineModeTitle')}
          </div>
        )}
      </div>

      <div className="fixed z-50 flex flex-col items-end gap-2 safe-top-4 safe-right-4">
        <button
          onClick={() => setShowAbout(!showAbout)}
          className="text-sm text-white/70 hover:text-white transition-colors"
        >
          {t(contentLang, 'about')}
        </button>
        <button
          onClick={() => setShowLikes(!showLikes)}
          className="text-sm text-white/70 hover:text-white transition-colors"
        >
          {t(contentLang, 'likes')}
        </button>
        <button
          onClick={() => {
            // Clear current cards immediately so we don't show mixed languages.
            setArticles([]);
            setContentLang(contentLang === 'zh' ? 'en' : 'zh');
          }}
          className="text-sm text-white/70 hover:text-white transition-colors"
          title="Switch language"
        >
          {/* Show the target language to reduce confusion */}
          {contentLang === 'zh' ? 'EN' : '中文'}
        </button>
      </div>

      {showAbout && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 safe-p-4">
          <div className="bg-gray-900 z-[41] p-6 rounded-lg max-w-md relative">
            <button
              onClick={() => setShowAbout(false)}
              className="absolute top-2 right-2 text-white/70 hover:text-white"
            >
              ✕
            </button>
            <h2 className="text-xl font-bold mb-4">{t(contentLang, 'aboutTitle')}</h2>
            <p className="mb-4">{t(contentLang, 'aboutDesc')}</p>
            <p className="text-white/70">{t(contentLang, 'author')}</p>
            <p className="text-white/70">{t(contentLang, 'wechatOA')}</p>
            <p className="text-white/70">
              {t(contentLang, 'github')}
              <a
                className="underline hover:text-white"
                href="https://github.com/ViffyGwaanl/papertok"
                target="_blank"
                rel="noreferrer"
              >
                https://github.com/ViffyGwaanl/papertok
              </a>
            </p>
            <p className="text-white/70 mt-2">PaperTok — a local MVP for browsing trending AI/ML papers.</p>
          </div>
          <div
            className={`w-full h-full z-[40] top-1 left-1  bg-[rgb(28 25 23 / 43%)] fixed  ${showAbout ? "block" : "hidden"
              }`}
            onClick={() => setShowAbout(false)}
          ></div>
        </div>
      )}

      {showLikes && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 safe-p-4">
          <div className="bg-gray-900 z-[41] p-6 rounded-lg w-full max-w-2xl h-[80vh] flex flex-col relative">
            <button
              onClick={() => setShowLikes(false)}
              className="absolute top-2 right-2 text-white/70 hover:text-white"
            >
              ✕
            </button>

            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Liked Articles</h2>
              {likedArticles.length > 0 && (
                <button
                  onClick={handleExport}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors"
                  title="Export liked articles"
                >
                  <Download className="w-4 h-4" />
                  Export
                </button>
              )}
            </div>

            <div className="relative mb-4">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search liked articles..."
                className="w-full bg-gray-800 text-white px-4 py-2 pl-10 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <Search className="w-5 h-5 text-white/50 absolute left-3 top-1/2 transform -translate-y-1/2" />
            </div>

            <div className="flex-1 overflow-y-auto min-h-0">
              {filteredLikedArticles.length === 0 ? (
                <p className="text-white/70">
                  {searchQuery ? "No matches found." : "No liked articles yet."}
                </p>
              ) : (
                <div className="space-y-4">
                  {filteredLikedArticles.map((article) => (
                    <div
                      key={article.pageid}
                      className="flex gap-4 items-start group"
                    >
                      {article.thumbnail && (
                        <img
                          src={article.thumbnail.source}
                          alt={article.title}
                          className="w-20 h-20 object-cover rounded"
                        />
                      )}
                      <div className="flex-1">
                        <div className="flex justify-between items-start">
                          <button
                            type="button"
                            onClick={() => {
                              setShowLikes(false);
                              openPaperRoute(article.pageid, article.displaytitle || article.title);
                            }}
                            className="font-bold hover:text-gray-200 text-left"
                            title={t(contentLang, 'page')}
                          >
                            {article.title}
                          </button>
                          <button
                            onClick={() => toggleLike(article)}
                            className="text-white/50 hover:text-white/90 p-1 rounded-full md:opacity-0 md:group-hover:opacity-100 transition-opacity"
                            aria-label="Remove from likes"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                        <p className="text-sm text-white/70 line-clamp-2">
                          {article.extract}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div
            className={`w-full h-full z-[40] top-1 left-1  bg-[rgb(28 25 23 / 43%)] fixed  ${showLikes ? "block" : "hidden"
              }`}
            onClick={() => setShowLikes(false)}
          ></div>
        </div>
      )}

      <PaperDetailModal
        open={!!routePaperId}
        paperId={routePaperId || 0}
        lang={contentLang}
        fallbackTitle={routePaperTitle}
        onClose={closePaperRoute}
      />

      {articles.map((article) => (
        <WikiCard key={article.pageid} article={article} lang={contentLang} />
      ))}
      <div ref={observerTarget} className="h-10 -mt-1" />
      {loading && (
        <div className="h-screen w-full flex items-center justify-center gap-2">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span>Loading...</span>
        </div>
      )}
      {/* Analytics removed */}
    </div>
  );
}

function App() {
  const path = window.location.pathname || '/';
  if (path === '/admin' || path.startsWith('/admin/')) {
    return <AdminPage />;
  }
  return <MainPage />;
}

export default App;
