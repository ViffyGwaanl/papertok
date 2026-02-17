from __future__ import annotations

import json
import random
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import Session, select
from sqlalchemy import exists

from app.core.config import settings
from app.db.engine import engine
from app.models.paper import Paper
from app.models.paper_image import PaperImage
from app.services.app_config import get_effective_app_config

router = APIRouter(prefix="/api/papers", tags=["papers"])


def _safe_rel_url(root: str, file_path: str, *, mount_prefix: str) -> str | None:
    """Return a URL under mount_prefix if file_path is inside root."""
    try:
        root_p = Path(root).resolve()
        fp = Path(file_path).resolve()
        rel = fp.relative_to(root_p)
        # Use POSIX separators for URLs
        return mount_prefix.rstrip("/") + "/" + rel.as_posix()
    except Exception:
        return None


def _normalize_provider_name(x: str | None) -> str | None:
    if not x:
        return None
    x0 = x.strip().lower()
    if not x0:
        return None
    if x0 in {"seedream", "ark"}:
        return "seedream"
    if x0 in {"glm", "glm-image", "glm_image"}:
        return "glm"
    return x0


def _preferred_provider_order(display: str) -> list[str]:
    """Return provider ordering preference used for display.

    - If display is seedream/glm: that provider goes first.
    - If display is auto: follow generation provider preference in Settings.
    """

    d0 = (display or "seedream").strip().lower()
    if d0 in {"seedream", "glm"}:
        other = "glm" if d0 == "seedream" else "seedream"
        return [d0, other]

    # auto: follow generation preference
    pref = [_normalize_provider_name(x) for x in (settings.paper_images_providers or [])]
    pref = [x for x in pref if x]

    if not pref:
        pref = ["seedream", "glm"]

    # de-dupe, preserve order
    out: list[str] = []
    seen: set[str] = set()
    for x in pref:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)

    # ensure the common providers exist in the ordering
    for x in ["seedream", "glm"]:
        if x not in seen:
            out.append(x)
            seen.add(x)

    return out


@router.get("/random")
def get_random_papers(
    limit: int = Query(20, ge=1, le=50),
    day: str | None = Query(
        default=None,
        description=(
            "YYYY-MM-DD | 'latest' | 'all'. "
            "Default: all (full history)."
        ),
    ),
    lang: str = Query(
        default="zh",
        description="Content language for feed gating + fields: zh|en",
    ),
):
    """Return random PaperCards for the WikiTok-style feed.

    Default is full history. Pass `day=latest` to show only the latest Top10,
    or `day=YYYY-MM-DD` to filter to a specific day.
    """

    with Session(engine) as session:
        filter_day: str | None = None
        if day:
            d = day.strip().lower()
            if d == "all":
                filter_day = None
            elif d == "latest":
                filter_day = session.exec(
                    select(Paper.day)
                    .where(Paper.source == "hf_daily")
                    .where(Paper.day.is_not(None))
                    .order_by(Paper.day.desc())
                    .limit(1)
                ).first()
            else:
                filter_day = day

        q = select(Paper.id).where(Paper.source == "hf_daily")
        # Hide unprocessed papers by default (skip in feed until "done")
        app_cfg = get_effective_app_config(session)

        # Normalize lang
        lang0 = (lang or "zh").strip().lower()
        if lang0 not in {"zh", "en"}:
            lang0 = "zh"

        if app_cfg.feed_require_explain:
            explain_col = Paper.content_explain_en if lang0 == "en" else Paper.content_explain_cn
            q = q.where(explain_col.is_not(None)).where(Paper.raw_text_path.is_not(None))

        if app_cfg.feed_require_image_captions:
            cap_col = Paper.image_captions_en_json if lang0 == "en" else Paper.image_captions_json
            q = (
                q.where(cap_col.is_not(None))
                .where(cap_col != "")
                .where(cap_col != "{}")
                .where(cap_col != "null")
            )

        if app_cfg.feed_require_generated_images:
            # We treat paper_images_display_provider as a *display ordering* hint.
            # Feed gating should only require that at least one generated image exists.
            img_subq = (
                select(PaperImage.id)
                .where(PaperImage.paper_id == Paper.id)
                .where(PaperImage.kind == "generated")
                .where(PaperImage.lang == lang0)
                .where(PaperImage.enabled == True)  # noqa: E712
                .where(PaperImage.url_path.is_not(None))
            )

            q = q.where(exists(img_subq))

        if filter_day:
            q = q.where(Paper.day == filter_day)

        ids = session.exec(q).all()
        if not ids:
            return []

        # For daily=10, it's fine to sample in-memory; avoids RANDOM()/range-hole issues.
        chosen_ids = ids[:]
        random.shuffle(chosen_ids)
        chosen_ids = chosen_ids[: min(limit, len(chosen_ids))]

        rows = session.exec(select(Paper).where(Paper.id.in_(chosen_ids))).all()

    # Preload generated images for chosen papers (avoid N+1 queries)
    # We keep multiple providers (seedream/glm) in DB. The feed returns *both*
    # providers' images (if present), with the selected provider ordered first.

    by_paper: dict[int, list[PaperImage]] = {}
    with Session(engine) as session:
        app_cfg = get_effective_app_config(session)
        display = (app_cfg.paper_images_display_provider or "seedream").strip().lower()
        q_imgs = (
            select(PaperImage)
            .where(PaperImage.paper_id.in_([p.id for p in rows]))
            .where(PaperImage.kind == "generated")
            .where(PaperImage.lang == lang0)
            .where(PaperImage.enabled == True)  # noqa: E712
            .where(PaperImage.url_path.is_not(None))
        )

        # Always fetch all providers. We'll order them later when building card thumbnails.
        imgs = session.exec(
            q_imgs.order_by(PaperImage.paper_id.asc(), PaperImage.provider.asc(), PaperImage.order_idx.asc())
        ).all()

        for img in imgs:
            by_paper.setdefault(img.paper_id, []).append(img)

    # Map to WikiTok card shape
    cards = []
    for p in rows:
        extract = p.one_liner_en if lang0 == "en" else p.one_liner

        # Fallback: show raw abstract/summary until LLM completes.
        if not extract and p.meta_json:
            try:
                meta = json.loads(p.meta_json)
                abstract = (
                    meta.get("paper", {}).get("summary")
                    or meta.get("paper", {}).get("abstract")
                    or meta.get("summary")
                    or meta.get("abstract")
                )
                if isinstance(abstract, str) and abstract.strip():
                    extract = abstract.strip()
            except Exception:
                pass

        if not extract:
            continue

        # keep card text short-ish
        if len(extract) > 400:
            extract = extract[:397] + "..."

        # Prefer a stable external URL for "Read more" (frontend opens in a new tab)
        url = p.url or (f"https://arxiv.org/abs/{p.external_id}" if p.external_id else "")

        imgs_for_paper = by_paper.get(p.id, [])

        # Return *both* providers' images, ordered by the selected provider.
        # Example: display=seedream => [seedream 3] + [glm 3]
        provider_order = _preferred_provider_order(display)

        by_prov: dict[str, list[PaperImage]] = {}
        for img in imgs_for_paper:
            key = _normalize_provider_name(img.provider) or img.provider
            by_prov.setdefault(key, []).append(img)

        # Sort inside each provider by order_idx
        for prov, imgs0 in by_prov.items():
            imgs0.sort(key=lambda x: x.order_idx)

        ordered_imgs: list[PaperImage] = []
        for prov in provider_order:
            ordered_imgs.extend(by_prov.pop(prov, []))

        # Append any remaining providers (future-proof)
        for prov in sorted(by_prov.keys()):
            ordered_imgs.extend(by_prov[prov])

        gen_sources = [img.url_path for img in ordered_imgs if img.url_path]

        # thumbnail: prefer generated image (relative URL under /static/gen) else HF thumbnail
        thumb_src = (gen_sources[0] if gen_sources else None) or p.thumbnail_url

        cards.append(
            {
                "pageid": p.id,
                "title": p.title,
                "displaytitle": p.display_title or p.title,
                "extract": extract,
                "day": p.day,
                "thumbnail": (
                    {"source": thumb_src, "width": 1088, "height": 1920}
                    if thumb_src
                    else None
                ),
                # Non-WikiTok extension: multiple images for horizontal carousel
                "thumbnails": gen_sources,
                "url": url,
            }
        )

    # shuffle for better randomness
    random.shuffle(cards)
    return cards[:limit]


@router.get("/{paper_id}")
def get_paper_detail(
    paper_id: int,
    lang: str = Query(default="zh", description="Content language: zh|en|both"),
):
    """Return detail for one paper (for in-app modal/detail view)."""
    with Session(engine) as session:
        paper = session.get(Paper, paper_id)
        if not paper:
            raise HTTPException(status_code=404, detail="paper not found")

    pdf_local_url = None
    if paper.pdf_path:
        pdf_local_url = _safe_rel_url(
            settings.papers_pdf_dir, paper.pdf_path, mount_prefix="/static/pdfs"
        )

    lang0 = (lang or "zh").strip().lower()
    if lang0 not in {"zh", "en", "both"}:
        lang0 = "zh"

    raw_markdown_url = None
    images: list[str] = []
    image_captions: dict[str, str] = {}
    image_captions_en: dict[str, str] = {}

    if paper.raw_text_path:
        raw_markdown_url = _safe_rel_url(
            settings.mineru_out_root,
            paper.raw_text_path,
            mount_prefix="/static/mineru",
        )

        # Load cached captions (if any)
        if lang0 in {"zh", "both"} and paper.image_captions_json:
            try:
                image_captions = json.loads(paper.image_captions_json) or {}
                if not isinstance(image_captions, dict):
                    image_captions = {}
            except Exception:
                image_captions = {}

        if lang0 in {"en", "both"} and paper.image_captions_en_json:
            try:
                image_captions_en = json.loads(paper.image_captions_en_json) or {}
                if not isinstance(image_captions_en, dict):
                    image_captions_en = {}
            except Exception:
                image_captions_en = {}

        # Pick captions by requested language
        if lang0 == "en":
            image_captions = image_captions_en

        try:
            md_path = Path(paper.raw_text_path)
            img_dir = md_path.parent / "images"
            if img_dir.exists() and img_dir.is_dir():
                exts = {".jpg", ".jpeg", ".png", ".webp"}
                for fp in sorted(img_dir.iterdir()):
                    if fp.suffix.lower() in exts and fp.is_file():
                        url = _safe_rel_url(
                            settings.mineru_out_root,
                            str(fp),
                            mount_prefix="/static/mineru",
                        )
                        if url:
                            images.append(url)
        except Exception:
            pass

    # generated images (seedream + glm)
    gen_images: list[dict] = []
    with Session(engine) as session:
        app_cfg = get_effective_app_config(session)
        display = (app_cfg.paper_images_display_provider or "seedream").strip().lower()

        q = (
            select(PaperImage)
            .where(PaperImage.paper_id == paper.id)
            .where(PaperImage.kind == "generated")
            .where(PaperImage.enabled == True)  # noqa: E712
            .where(PaperImage.url_path.is_not(None))
        )
        if lang0 in {"zh", "en"}:
            q = q.where(PaperImage.lang == lang0)

        imgs = session.exec(q.order_by(PaperImage.provider.asc(), PaperImage.order_idx.asc())).all()

        provider_order = _preferred_provider_order(display)
        by_prov: dict[str, list[PaperImage]] = {}
        for img in imgs:
            key = _normalize_provider_name(img.provider) or img.provider
            by_prov.setdefault(key, []).append(img)

        ordered: list[PaperImage] = []
        for prov in provider_order:
            ordered.extend(by_prov.pop(prov, []))
        for prov in sorted(by_prov.keys()):
            ordered.extend(by_prov[prov])

        for img in ordered:
            gen_images.append(
                {
                    "url": img.url_path,
                    "order_idx": img.order_idx,
                    "provider": img.provider,
                    "lang": img.lang,
                }
            )

    return {
        "id": paper.id,
        "source": paper.source,
        "external_id": paper.external_id,
        "day": paper.day,
        "title": paper.title,
        "display_title": paper.display_title or paper.title,
        "url": paper.url or (f"https://arxiv.org/abs/{paper.external_id}" if paper.external_id else None),
        "thumbnail_url": paper.thumbnail_url,
        "one_liner": paper.one_liner_en if lang0 == "en" else paper.one_liner,
        "one_liner_en": (paper.one_liner_en if lang0 == "both" else None),
        "content_explain_cn": paper.content_explain_cn,
        "content_explain_en": (paper.content_explain_en if lang0 in {"en", "both"} else None),
        "content_explain": (
            paper.content_explain_en if lang0 == "en" else paper.content_explain_cn
        ),
        "pdf_url": paper.pdf_url,
        "pdf_local_url": pdf_local_url,
        # raw_text_path is an internal absolute path on disk; do not expose publicly.
        "raw_markdown_url": raw_markdown_url,
        "images": images,
        "image_captions": image_captions,
        "image_captions_en": (image_captions_en if lang0 == "both" else None),
        "generated_images": gen_images,
        "epub_url_en": paper.epub_url_en,
        "epub_url_zh": (paper.epub_url_zh if lang0 in {"zh", "both"} else None),
        "epub_url_bilingual": (paper.epub_url_bilingual if lang0 == "both" else None),
        "epub_url": (
            paper.epub_url_en
            if lang0 == "en"
            else paper.epub_url_zh
            if lang0 == "zh"
            else None
        ),
        "created_at": paper.created_at,
        "updated_at": paper.updated_at,
    }
