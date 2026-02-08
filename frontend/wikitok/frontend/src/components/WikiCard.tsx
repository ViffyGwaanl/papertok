import { Share2, Heart, Image as ImageIcon, ExternalLink, ChevronLeft, ChevronRight } from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { useLikedArticles } from '../contexts/LikedArticlesContext';

import { API_BASE, apiUrl } from '../lib/apiBase';

export interface WikiArticle {
    title: string;
    displaytitle: string;
    extract: string;
    pageid: number;
    url: string;
    day?: string | null;
    thumbnail?: {
        source: string;
        width: number;
        height: number;
    } | null;
    // Extension: multiple background images for horizontal carousel
    thumbnails?: string[] | null;
}

type PaperDetail = {
    id: number;
    external_id: string;
    day?: string | null;
    title: string;
    display_title: string;
    url?: string | null;
    thumbnail_url?: string | null;
    one_liner?: string | null;
    content_explain_cn?: string | null;
    pdf_url?: string | null;
    pdf_local_url?: string | null;
    raw_markdown_url?: string | null;
    images?: string[];
    image_captions?: Record<string, string>;
};

interface WikiCardProps {
    article: WikiArticle;
}

export function WikiCard({ article }: WikiCardProps) {
    const [imageLoaded, setImageLoaded] = useState(false);
    const [carouselIndex, setCarouselIndex] = useState(0);
    const carouselRef = useRef<HTMLDivElement | null>(null);
    const dragRef = useRef<{ active: boolean; pointerId: number | null; startX: number; startY: number; startScrollLeft: number; dragging: boolean }>({
        active: false,
        pointerId: null,
        startX: 0,
        startY: 0,
        startScrollLeft: 0,
        dragging: false,
    });
    const { toggleLike, isLiked } = useLikedArticles();

    const [showDetail, setShowDetail] = useState(false);
    const [detailLoading, setDetailLoading] = useState(false);
    const [detailError, setDetailError] = useState<string | null>(null);
    const [detail, setDetail] = useState<PaperDetail | null>(null);

    const [tab, setTab] = useState<'explain' | 'markdown' | 'images'>('explain');
    const [markdownLoading, setMarkdownLoading] = useState(false);
    const [markdownText, setMarkdownText] = useState<string | null>(null);

    const [captionModal, setCaptionModal] = useState<null | { src: string; caption: string }>(null);

    const detailMarkdownUrl = useMemo(() => {
        if (!detail?.raw_markdown_url) return null;
        return `${API_BASE}${detail.raw_markdown_url}`;
    }, [detail]);

    // Local PDF link is intentionally hidden (online arXiv PDF is enough).

    const openDetail = async () => {
        setShowDetail(true);
        setDetailError(null);
        setTab('explain');

        // Always refetch so long-running background jobs (e.g. image captions) can show up.
        setDetailLoading(true);
        try {
            const r = await fetch(apiUrl(`/api/papers/${article.pageid}`));
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const j = (await r.json()) as PaperDetail;
            setDetail(j);
        } catch (e: any) {
            setDetailError(e?.message || 'Failed to load detail');
        } finally {
            setDetailLoading(false);
        }
    };

    const loadMarkdownIfNeeded = async () => {
        if (markdownText || markdownLoading) return;
        if (!detailMarkdownUrl) return;
        setMarkdownLoading(true);
        try {
            const r = await fetch(detailMarkdownUrl);
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const t = await r.text();
            setMarkdownText(t);
        } catch (e: any) {
            setMarkdownText(`(加载失败) ${e?.message || ''}`);
        } finally {
            setMarkdownLoading(false);
        }
    };

    const handleShare = async () => {
        if (navigator.share) {
            try {
                await navigator.share({
                    title: article.displaytitle,
                    text: article.extract || '',
                    url: article.url
                });
            } catch (error) {
                console.error('Error sharing:', error);
            }
        } else {
            // Fallback: Copy to clipboard
            await navigator.clipboard.writeText(article.url);
            alert('Link copied to clipboard!');
        }
    };

    return (
        <div className="h-screen w-full flex items-center justify-center snap-start relative" onDoubleClick={() => toggleLike(article)}>
            <div className="h-full w-full relative">
                {article.thumbnail ? (
                    <div className="absolute inset-0">
                        {Array.isArray(article.thumbnails) && article.thumbnails.length > 0 ? (
                            <>
                                <div
                                    ref={carouselRef}
                                    className="absolute inset-0 flex overflow-x-auto overflow-y-hidden snap-x snap-mandatory"
                                    style={{ scrollSnapType: 'x mandatory', WebkitOverflowScrolling: 'touch' as any }}
                                    onScroll={(e) => {
                                        const el = e.currentTarget as HTMLDivElement;
                                        const w = el.clientWidth || 1;
                                        const idx = Math.round(el.scrollLeft / w);
                                        if (!Number.isNaN(idx)) setCarouselIndex(idx);
                                    }}
                                >
                                    {article.thumbnails.map((src, idx) => {
                                        const finalSrc = src.startsWith('http') ? src : `${API_BASE}${src}`;
                                        return (
                                            <div
                                                key={idx}
                                                className="w-full h-full flex-shrink-0 snap-start"
                                                style={{ minWidth: '100%' }}
                                            >
                                                <img
                                                    loading={idx === 0 ? 'eager' : 'lazy'}
                                                    src={finalSrc}
                                                    alt={article.displaytitle}
                                                    className="w-full h-full object-cover bg-white"
                                                    onLoad={() => idx === 0 && setImageLoaded(true)}
                                                    onError={(e) => {
                                                        console.error('Image failed to load:', e);
                                                        if (idx === 0) setImageLoaded(true);
                                                    }}
                                                />
                                            </div>
                                        );
                                    })}
                                </div>

                                {/* arrows (more reliable than swipe on some devices) */}
                                {((article.thumbnails || []).length > 1) && (
                                    <>
                                        <button
                                            className="absolute left-2 top-1/2 -translate-y-1/2 z-20 p-2 rounded-full bg-black/30 hover:bg-black/50"
                                            onClick={() => {
                                                const el = carouselRef.current;
                                                if (!el) return;
                                                const w = el.clientWidth || 1;
                                                const next = Math.max(0, carouselIndex - 1);
                                                el.scrollTo({ left: next * w, behavior: 'smooth' });
                                                setCarouselIndex(next);
                                            }}
                                            aria-label="Previous image"
                                        >
                                            <ChevronLeft className="w-5 h-5" />
                                        </button>
                                        <button
                                            className="absolute right-2 top-1/2 -translate-y-1/2 z-20 p-2 rounded-full bg-black/30 hover:bg-black/50"
                                            onClick={() => {
                                                const el = carouselRef.current;
                                                if (!el) return;
                                                const w = el.clientWidth || 1;
                                                const thumbs = article.thumbnails || [];
                                                const max = thumbs.length - 1;
                                                const next = Math.min(max, carouselIndex + 1);
                                                el.scrollTo({ left: next * w, behavior: 'smooth' });
                                                setCarouselIndex(next);
                                            }}
                                            aria-label="Next image"
                                        >
                                            <ChevronRight className="w-5 h-5" />
                                        </button>
                                    </>
                                )}

                                {/* dots */}
                                <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-1 z-20 pointer-events-none">
                                    {article.thumbnails.slice(0, 8).map((_, i) => (
                                        <div
                                            key={i}
                                            className={`h-1.5 w-1.5 rounded-full ${i === carouselIndex ? 'bg-white' : 'bg-white/40'}`}
                                        />
                                    ))}
                                </div>

                                {!imageLoaded && (
                                    <div className="absolute inset-0 bg-gray-900 animate-pulse" />
                                )}
                            </>
                        ) : (
                            <img
                                loading="lazy"
                                src={article.thumbnail.source.startsWith('http') ? article.thumbnail.source : `${API_BASE}${article.thumbnail.source}`}
                                alt={article.displaytitle}
                                className={`w-full h-full object-cover transition-opacity duration-300 bg-white ${imageLoaded ? 'opacity-100' : 'opacity-0'
                                    }`}
                                onLoad={() => setImageLoaded(true)}
                                onError={(e) => {
                                    console.error('Image failed to load:', e);
                                    setImageLoaded(true); // Show content even if image fails
                                }}
                            />
                        )}
                        <div className="absolute inset-0 bg-gradient-to-b from-black/20 to-black/60 pointer-events-none" />
                    </div>
                ) : (
                    <div className="absolute inset-0 bg-gray-900" />
                )}

                {/* Caption modal (for markdown/images) */}
                {captionModal && (
                    <div className="fixed inset-0 z-[70] bg-black/80 backdrop-blur-sm p-4 safe-p-4 flex items-center justify-center">
                        <div className="w-full max-w-2xl bg-gray-950 border border-white/10 rounded-lg overflow-hidden">
                            <div className="p-3 border-b border-white/10 flex items-center justify-between">
                                <div className="text-sm text-white/80 truncate">图注</div>
                                <button
                                    onClick={() => setCaptionModal(null)}
                                    className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20"
                                >
                                    关闭
                                </button>
                            </div>
                            <div className="p-4 space-y-3">
                                <img
                                    src={captionModal.src}
                                    alt="captioned"
                                    className="w-full max-h-[50vh] object-contain rounded border border-white/10 bg-black"
                                />
                                <div className="text-sm text-white/85 leading-relaxed whitespace-pre-wrap">
                                    {captionModal.caption}
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Detail modal */}
                {showDetail && (
                    <div className="fixed inset-0 z-[60] bg-black/80 backdrop-blur-sm p-4 safe-p-4 flex items-center justify-center">
                        <div className="w-full max-w-3xl h-[85vh] bg-gray-950 border border-white/10 rounded-lg overflow-hidden flex flex-col">
                            <div className="p-4 border-b border-white/10 flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                    <div className="text-lg font-bold truncate">{article.displaytitle}</div>
                                    <div className="flex items-center gap-2 flex-wrap">
                                        {detail?.external_id && (
                                            <div className="text-xs text-white/60">arXiv: {detail.external_id}</div>
                                        )}
                                        {(detail?.day || article.day) && (
                                            <div className="text-xs text-white/60">Top10: {detail?.day || article.day}</div>
                                        )}
                                    </div>
                                </div>
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => setShowDetail(false)}
                                        className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20 whitespace-nowrap shrink-0 min-w-[3.5rem]"
                                    >
                                        关闭
                                    </button>
                                </div>
                            </div>

                            <div className="p-3 border-b border-white/10 flex gap-2 overflow-x-auto">
                                <button
                                    onClick={() => setTab('explain')}
                                    className={`px-3 py-1.5 text-sm rounded ${tab === 'explain' ? 'bg-white/20' : 'bg-white/10 hover:bg-white/20'}`}
                                >
                                    讲解
                                </button>
                                <button
                                    onClick={async () => {
                                        setTab('markdown');
                                        await loadMarkdownIfNeeded();
                                    }}
                                    className={`px-3 py-1.5 text-sm rounded ${tab === 'markdown' ? 'bg-white/20' : 'bg-white/10 hover:bg-white/20'}`}
                                    title="MinerU markdown"
                                >
                                    原文
                                </button>
                                <button
                                    onClick={() => setTab('images')}
                                    className={`px-3 py-1.5 text-sm rounded ${tab === 'images' ? 'bg-white/20' : 'bg-white/10 hover:bg-white/20'}`}
                                    title="MinerU extracted images"
                                >
                                    图片
                                </button>

                                <div className="ml-auto flex gap-2">
                                    {/* PDF(本地) 暂时隐藏：已有在线 PDF(arXiv) */}
                                    {detail?.pdf_url && (
                                        <a
                                            className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20 inline-flex items-center gap-2"
                                            href={detail.pdf_url}
                                            target="_blank"
                                            rel="noreferrer"
                                        >
                                            <ExternalLink className="w-4 h-4" /> PDF
                                        </a>
                                    )}
                                    {detail?.url && (
                                        <a
                                            className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20 inline-flex items-center gap-2"
                                            href={detail.url}
                                            target="_blank"
                                            rel="noreferrer"
                                        >
                                            <ExternalLink className="w-4 h-4" /> 页面
                                        </a>
                                    )}
                                </div>
                            </div>

                            <div className="flex-1 overflow-y-auto p-4">
                                {detailLoading && (
                                    <div className="text-white/70">加载中…</div>
                                )}
                                {detailError && (
                                    <div className="text-red-300">加载失败：{detailError}</div>
                                )}

                                {!detailLoading && !detailError && detail && tab === 'explain' && (
                                    <div className="space-y-3">
                                        <div className="text-sm text-white/85 leading-relaxed">
                                            <ReactMarkdown
                                                remarkPlugins={[remarkGfm, remarkBreaks]}
                                                components={{
                                                    a: ({ href, children }) => (
                                                        <a
                                                            href={href || '#'}
                                                            target="_blank"
                                                            rel="noreferrer"
                                                            className="text-blue-300 hover:text-blue-200 underline"
                                                        >
                                                            {children}
                                                        </a>
                                                    ),
                                                    h1: ({ children }) => <h1 className="text-lg font-bold mt-2 mb-2">{children}</h1>,
                                                    h2: ({ children }) => <h2 className="text-base font-bold mt-2 mb-2">{children}</h2>,
                                                    h3: ({ children }) => <h3 className="text-sm font-semibold mt-2 mb-1">{children}</h3>,
                                                    p: ({ children }) => <p className="text-sm leading-relaxed mb-2">{children}</p>,
                                                    ul: ({ children }) => <ul className="list-disc pl-5 space-y-1 mb-2">{children}</ul>,
                                                    ol: ({ children }) => <ol className="list-decimal pl-5 space-y-1 mb-2">{children}</ol>,
                                                    li: ({ children }) => <li className="text-sm leading-relaxed">{children}</li>,
                                                    code: ({ children }) => (
                                                        <code className="text-xs bg-white/10 px-1 py-0.5 rounded">{children}</code>
                                                    ),
                                                    pre: ({ children }) => (
                                                        <pre className="text-xs bg-white/5 border border-white/10 rounded p-2 overflow-x-auto">{children}</pre>
                                                    ),
                                                }}
                                            >
                                                {detail.content_explain_cn || '（暂无讲解）'}
                                            </ReactMarkdown>
                                        </div>
                                    </div>
                                )}

                                {!detailLoading && !detailError && detail && tab === 'markdown' && (
                                    <div className="space-y-3">
                                        {!detailMarkdownUrl && (
                                            <div className="text-white/70">（没有 MinerU markdown）</div>
                                        )}
                                        {detailMarkdownUrl && markdownLoading && (
                                            <div className="text-white/70">加载 markdown…</div>
                                        )}
                                        {detailMarkdownUrl && markdownText && (
                                            <div className="text-sm text-white/85 leading-relaxed">
                                                <ReactMarkdown
                                                    remarkPlugins={[remarkGfm, remarkBreaks]}
                                                    components={{
                                                        a: ({ href, children }) => (
                                                            <a
                                                                href={href || '#'}
                                                                target="_blank"
                                                                rel="noreferrer"
                                                                className="text-blue-300 hover:text-blue-200 underline"
                                                            >
                                                                {children}
                                                            </a>
                                                        ),
                                                        img: ({ src, alt }) => {
                                                            const s = (src || '').toString();
                                                            if (!s) return null;

                                                            let finalSrc = s;
                                                            if (s.startsWith('http')) {
                                                                finalSrc = s;
                                                            } else if (s.startsWith('/')) {
                                                                // absolute URL path served by backend
                                                                finalSrc = `${API_BASE}${s}`;
                                                            } else {
                                                                // MinerU markdown uses relative paths like: images/<hash>.jpg
                                                                const file = s.split('/').pop();
                                                                const mdBase = (detail.raw_markdown_url || '').toString().replace(/\/[^/]+$/, '');
                                                                if (file && mdBase) {
                                                                    finalSrc = `${API_BASE}${mdBase}/images/${file}`;
                                                                } else if (file && detail.external_id) {
                                                                    // fallback (older layout)
                                                                    finalSrc = `${API_BASE}/static/mineru/${detail.external_id}/txt/images/${file}`;
                                                                }
                                                            }

                                                            // Prefer showing caption on click (instead of opening raw image)
                                                            const key = finalSrc.startsWith(API_BASE) ? finalSrc.slice(API_BASE.length) : finalSrc;
                                                            const cap = (detail.image_captions && (detail.image_captions as any)[key]) || '';

                                                            return (
                                                                <button
                                                                    type="button"
                                                                    className="block my-2 text-left"
                                                                    onClick={() => {
                                                                        setCaptionModal({
                                                                            src: finalSrc,
                                                                            caption: cap || '（暂无图注）',
                                                                        });
                                                                    }}
                                                                >
                                                                    <img
                                                                        src={finalSrc}
                                                                        alt={alt || ''}
                                                                        className="max-w-full rounded border border-white/10"
                                                                    />
                                                                </button>
                                                            );
                                                        },
                                                        h1: ({ children }) => <h1 className="text-lg font-bold mt-3 mb-2">{children}</h1>,
                                                        h2: ({ children }) => <h2 className="text-base font-bold mt-3 mb-2">{children}</h2>,
                                                        h3: ({ children }) => <h3 className="text-sm font-semibold mt-3 mb-1">{children}</h3>,
                                                        p: ({ children }) => <p className="text-sm leading-relaxed mb-2">{children}</p>,
                                                        ul: ({ children }) => <ul className="list-disc pl-5 space-y-1 mb-2">{children}</ul>,
                                                        ol: ({ children }) => <ol className="list-decimal pl-5 space-y-1 mb-2">{children}</ol>,
                                                        li: ({ children }) => <li className="text-sm leading-relaxed">{children}</li>,
                                                        code: ({ children }) => (
                                                            <code className="text-xs bg-white/10 px-1 py-0.5 rounded">{children}</code>
                                                        ),
                                                        pre: ({ children }) => (
                                                            <pre className="text-xs bg-white/5 border border-white/10 rounded p-2 overflow-x-auto">{children}</pre>
                                                        ),
                                                    }}
                                                >
                                                    {markdownText}
                                                </ReactMarkdown>
                                            </div>
                                        )}
                                    </div>
                                )}

                                {!detailLoading && !detailError && detail && tab === 'images' && (
                                    <div className="space-y-3">
                                        {(detail.images || []).length === 0 ? (
                                            <div className="text-white/70">（没有提取到图片）</div>
                                        ) : (
                                            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                                                {(detail.images || []).slice(0, 60).map((imgUrl, idx) => (
                                                    <div
                                                        key={idx}
                                                        className="border border-white/10 rounded overflow-hidden hover:opacity-95"
                                                    >
                                                        <button
                                                            type="button"
                                                            className="block w-full"
                                                            title="Show caption"
                                                            onClick={() => {
                                                                const src = `${API_BASE}${imgUrl}`;
                                                                const cap = detail.image_captions?.[imgUrl] || '（暂无图注）';
                                                                setCaptionModal({ src, caption: cap });
                                                            }}
                                                        >
                                                            <img
                                                                src={`${API_BASE}${imgUrl}`}
                                                                alt={`paper image ${idx + 1}`}
                                                                loading="lazy"
                                                                className="w-full h-32 object-cover bg-gray-900"
                                                            />
                                                        </button>
                                                        {detail.image_captions?.[imgUrl] && (
                                                            <div className="p-2 text-[11px] leading-snug text-white/75">
                                                                {detail.image_captions[imgUrl]}
                                                            </div>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                        {(detail.images || []).length > 60 && (
                                            <div className="text-white/60 text-xs">只显示前 60 张（防止卡顿）</div>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {/* Content container with z-index to ensure it's above the image */}
                <div
                    className="absolute backdrop-blur-xs bg-black/30 bottom-[10vh] left-0 right-0 p-6 text-white z-10"
                    style={{ touchAction: 'pan-y' }}
                    onPointerDown={(e) => {
                        // If user starts on an interactive element, don't hijack.
                        const t = e.target as HTMLElement;
                        if (t?.closest('button,a')) return;

                        const el = carouselRef.current;
                        if (!el) return;
                        dragRef.current.active = true;
                        dragRef.current.pointerId = e.pointerId;
                        dragRef.current.startX = e.clientX;
                        dragRef.current.startY = e.clientY;
                        dragRef.current.startScrollLeft = el.scrollLeft;
                        dragRef.current.dragging = false;
                        try {
                            (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
                        } catch { }
                    }}
                    onPointerMove={(e) => {
                        if (!dragRef.current.active) return;
                        const el = carouselRef.current;
                        if (!el) return;

                        const dx = e.clientX - dragRef.current.startX;
                        const dy = e.clientY - dragRef.current.startY;

                        // Determine if this is a horizontal gesture.
                        if (!dragRef.current.dragging) {
                            if (Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy) * 1.2) {
                                dragRef.current.dragging = true;
                            } else {
                                return;
                            }
                        }

                        // Horizontal drag: scroll the background carousel.
                        e.preventDefault();
                        el.scrollLeft = dragRef.current.startScrollLeft - dx;
                    }}
                    onPointerUp={(e) => {
                        if (!dragRef.current.active) return;
                        const el = carouselRef.current;
                        dragRef.current.active = false;

                        if (!el || !dragRef.current.dragging) return;

                        const w = el.clientWidth || 1;
                        const max = (article.thumbnails || []).length - 1;
                        const idx = Math.max(0, Math.min(max, Math.round(el.scrollLeft / w)));
                        el.scrollTo({ left: idx * w, behavior: 'smooth' });
                        setCarouselIndex(idx);

                        try {
                            (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
                        } catch { }
                    }}
                    onPointerCancel={() => {
                        dragRef.current.active = false;
                    }}
                >
                    <div className="flex justify-between items-start mb-3">
                        <a
                            href={article.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-gray-200 transition-colors"
                        >
                            <h2 className="text-2xl font-bold drop-shadow-lg">{article.displaytitle}</h2>
                        </a>
                        <div className="flex gap-2">
                            <button
                                onClick={() => toggleLike(article)}
                                className={`p-2 rounded-full backdrop-blur-sm transition-colors ${isLiked(article.pageid)
                                    ? 'bg-red-500 hover:bg-red-600'
                                    : 'bg-white/10 hover:bg-white/20'
                                    }`}
                                aria-label="Like article"
                            >
                                <Heart
                                    className={`w-5 h-5 ${isLiked(article.pageid) ? 'fill-white' : ''}`}
                                />
                            </button>
                            <button
                                onClick={handleShare}
                                className="p-2 rounded-full bg-white/10 backdrop-blur-sm hover:bg-white/20 transition-colors"
                                aria-label="Share article"
                            >
                                <Share2 className="w-5 h-5" />
                            </button>
                        </div>
                    </div>
                    <p className="text-gray-100 mb-4 drop-shadow-lg line-clamp-6">{article.extract}</p>

                    <div className="flex items-center gap-4">
                        <button
                            onClick={openDetail}
                            className="inline-flex items-center gap-2 text-white hover:text-gray-200 drop-shadow-lg"
                        >
                            <ImageIcon className="w-4 h-4" /> 讲解 / 原文 / 图片 →
                        </button>
                        <a
                            href={article.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-block text-white/80 hover:text-white drop-shadow-lg"
                        >
                            Read more →
                        </a>
                    </div>
                </div>
            </div>
        </div>
    );
}
