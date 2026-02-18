import { ExternalLink } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';

import { API_BASE, apiUrl } from '../lib/apiBase';
import { fetchJsonWithOfflineCache, fetchTextWithOfflineCache } from '../lib/offlineCache';
import { t } from '../lib/i18n';

type PaperDetail = {
    id: number;
    external_id: string;
    day?: string | null;
    title: string;
    display_title: string;
    url?: string | null;
    thumbnail_url?: string | null;
    one_liner?: string | null;
    content_explain?: string | null;
    content_explain_cn?: string | null;
    content_explain_en?: string | null;
    pdf_url?: string | null;
    pdf_local_url?: string | null;
    raw_markdown_url?: string | null;

    // EPUB artifacts
    epub_url?: string | null;
    epub_url_en?: string | null;

    images?: string[];
    image_captions?: Record<string, string>;
};

export function PaperDetailModal({
    open,
    paperId,
    lang,
    fallbackTitle,
    onClose,
}: {
    open: boolean;
    paperId: number;
    lang: 'zh' | 'en';
    fallbackTitle?: string;
    onClose: () => void;
}) {
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

    const loadDetail = async () => {
        if (!open) return;

        setDetailError(null);
        setTab('explain');
        setMarkdownText(null);

        setDetailLoading(true);
        try {
            const url = apiUrl(`/api/papers/${paperId}?lang=${lang}`);
            const { data: j, fromCache } = await fetchJsonWithOfflineCache<PaperDetail>(
                url,
                `papertok:paper_detail_route:${paperId}:lang=${lang}`,
                { maxAgeMs: 1000 * 60 * 60 * 24 * 7, fetchTimeoutMs: 12000 }
            );
            if (fromCache) {
                setDetailError(t(lang, 'cachedMayStale'));
            }
            setDetail(j);
        } catch (e: any) {
            setDetailError(e?.message || t(lang, 'loadFailed'));
            setDetail(null);
        } finally {
            setDetailLoading(false);
        }
    };

    const loadMarkdownIfNeeded = async () => {
        if (markdownText || markdownLoading) return;
        if (!detailMarkdownUrl) return;
        setMarkdownLoading(true);
        try {
            const { text: md, fromCache } = await fetchTextWithOfflineCache(
                detailMarkdownUrl,
                `papertok:paper_markdown_route:${detail?.id || paperId}:lang=${lang}`,
                { maxAgeMs: 1000 * 60 * 60 * 24 * 7, fetchTimeoutMs: 15000 }
            );
            if (fromCache && !detailError) {
                setDetailError(t(lang, 'cachedMayStale'));
            }
            setMarkdownText(md);
        } catch (e: any) {
            setMarkdownText(`(${t(lang, 'loadFailed')}) ${e?.message || ''}`);
        } finally {
            setMarkdownLoading(false);
        }
    };

    useEffect(() => {
        if (!open) return;
        loadDetail();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, paperId, lang]);

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-[60] bg-black/80 backdrop-blur-sm p-4 safe-p-4 flex items-center justify-center">
            <div className="w-full max-w-3xl h-[85vh] bg-gray-950 border border-white/10 rounded-lg overflow-hidden flex flex-col">
                <div className="p-4 border-b border-white/10 flex items-start justify-between gap-3">
                    <div className="min-w-0">
                        <div className="text-lg font-bold truncate">{detail?.display_title || fallbackTitle || `Paper #${paperId}`}</div>
                        <div className="flex items-center gap-2 flex-wrap">
                            {detail?.external_id && <div className="text-xs text-white/60">arXiv: {detail.external_id}</div>}
                            {detail?.day && <div className="text-xs text-white/60">Top10: {detail.day}</div>}
                        </div>
                    </div>
                    <div className="flex gap-2">
                        <button
                            onClick={onClose}
                            className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20 whitespace-nowrap shrink-0 min-w-[3.5rem]"
                        >
                            {t(lang, 'close')}
                        </button>
                    </div>
                </div>

                <div className="p-3 border-b border-white/10 flex gap-2 overflow-x-auto">
                    <button
                        onClick={() => setTab('explain')}
                        className={`px-3 py-1.5 text-sm rounded ${tab === 'explain' ? 'bg-white/20' : 'bg-white/10 hover:bg-white/20'}`}
                    >
                        {t(lang, 'tabExplain')}
                    </button>
                    <button
                        onClick={async () => {
                            setTab('markdown');
                            await loadMarkdownIfNeeded();
                        }}
                        className={`px-3 py-1.5 text-sm rounded ${tab === 'markdown' ? 'bg-white/20' : 'bg-white/10 hover:bg-white/20'}`}
                        title="MinerU markdown"
                    >
                        {t(lang, 'tabOriginal')}
                    </button>
                    <button
                        onClick={() => setTab('images')}
                        className={`px-3 py-1.5 text-sm rounded ${tab === 'images' ? 'bg-white/20' : 'bg-white/10 hover:bg-white/20'}`}
                        title="MinerU extracted images"
                    >
                        {t(lang, 'tabImages')}
                    </button>

                    <div className="ml-auto flex gap-2">
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
                                <ExternalLink className="w-4 h-4" /> {t(lang, 'page')}
                            </a>
                        )}
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-4">
                    {detailLoading && <div className="text-white/70">{t(lang, 'loading')}</div>}
                    {detailError && <div className="text-red-300">{t(lang, 'loadFailedPrefix')}{detailError}</div>}

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
                                    {detail.content_explain || detail.content_explain_cn || detail.content_explain_en || t(lang, 'noExplain')}
                                </ReactMarkdown>
                            </div>
                        </div>
                    )}

                    {!detailLoading && !detailError && detail && tab === 'markdown' && (
                        <div className="space-y-3">
                            {(detail.epub_url_en || detail.epub_url) && (
                                <div>
                                    <a
                                        className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20 inline-flex items-center gap-2"
                                        href={`${API_BASE}${(detail.epub_url_en || detail.epub_url) as string}`}
                                        target="_blank"
                                        rel="noreferrer"
                                        download={`${(detail.external_id || 'paper')}.en.epub`}
                                    >
                                        <ExternalLink className="w-4 h-4" /> {t(lang, 'downloadEpub')}
                                    </a>
                                </div>
                            )}

                            {!detailMarkdownUrl && <div className="text-white/70">{t(lang, 'noMineruMd')}</div>}
                            {detailMarkdownUrl && markdownLoading && <div className="text-white/70">{t(lang, 'loadingMarkdown')}</div>}

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
                                                    finalSrc = `${API_BASE}${s}`;
                                                } else {
                                                    const file = s.split('/').pop();
                                                    const mdBase = (detail.raw_markdown_url || '').toString().replace(/\/[^/]+$/, '');
                                                    if (file && mdBase) {
                                                        finalSrc = `${API_BASE}${mdBase}/images/${file}`;
                                                    } else if (file && detail.external_id) {
                                                        finalSrc = `${API_BASE}/static/mineru/${detail.external_id}/txt/images/${file}`;
                                                    }
                                                }

                                                const key = finalSrc.startsWith(API_BASE) ? finalSrc.slice(API_BASE.length) : finalSrc;
                                                const cap = (detail.image_captions && (detail.image_captions as any)[key]) || '';

                                                return (
                                                    <button
                                                        type="button"
                                                        className="block my-2 text-left"
                                                        onClick={() => {
                                                            setCaptionModal({
                                                                src: finalSrc,
                                                                caption: cap || t(lang, 'noCaption'),
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
                                <div className="text-white/70">{t(lang, 'noExtractedImages')}</div>
                            ) : (
                                <div className="grid grid-cols-2 gap-3">
                                    {(detail.images || []).map((src) => {
                                        const finalSrc = src.startsWith('http') ? src : `${API_BASE}${src}`;
                                        const key = finalSrc.startsWith(API_BASE) ? finalSrc.slice(API_BASE.length) : finalSrc;
                                        const cap = (detail.image_captions && (detail.image_captions as any)[key]) || '';
                                        return (
                                            <button
                                                key={src}
                                                type="button"
                                                className="text-left"
                                                onClick={() => {
                                                    setCaptionModal({
                                                        src: finalSrc,
                                                        caption: cap || t(lang, 'noCaption'),
                                                    });
                                                }}
                                            >
                                                <img src={finalSrc} className="w-full rounded border border-white/10" />
                                            </button>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* caption modal */}
            {captionModal && (
                <div className="fixed inset-0 z-[70] bg-black/80 backdrop-blur-sm p-4 safe-p-4 flex items-center justify-center">
                    <div className="w-full max-w-2xl max-h-[85vh] bg-gray-950 border border-white/10 rounded-lg overflow-hidden flex flex-col">
                        <div className="p-3 border-b border-white/10 flex items-center justify-between">
                            <div className="font-semibold">{t(lang, 'captionTitle')}</div>
                            <button
                                onClick={() => setCaptionModal(null)}
                                className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20"
                            >
                                {t(lang, 'close')}
                            </button>
                        </div>
                        <div className="p-4 overflow-y-auto">
                            <img src={captionModal.src} className="w-full rounded border border-white/10" />
                            <div className="mt-3 text-sm text-white/85 leading-relaxed whitespace-pre-wrap">{captionModal.caption}</div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
