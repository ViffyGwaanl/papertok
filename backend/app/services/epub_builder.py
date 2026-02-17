from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from app.core.config import settings
from app.models.paper import Paper
from app.models.paper_image import PaperImage
from app.services.app_config import get_effective_app_config


_MD_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


@dataclass
class BuildResult:
    kind: str  # en|zh|bilingual
    local_path: str
    url_path: str


def _lang_to_epub_lang(lang: str) -> str:
    lang0 = (lang or "en").strip().lower()
    if lang0 == "zh":
        return "zh-CN"
    return "en"


def _load_caption_by_basename(p: Paper, *, lang: str) -> dict[str, str]:
    """Return mapping: image filename -> caption text.

    Captions in DB are stored as a JSON mapping from image URL to caption.
    We normalize by basename so we can match after copying assets into the EPUB build dir.
    """

    lang0 = (lang or "en").strip().lower()
    raw = p.image_captions_en_json if lang0 == "en" else p.image_captions_json
    if not raw:
        return {}

    try:
        obj = json.loads(raw) or {}
    except Exception:
        return {}

    if not isinstance(obj, dict):
        return {}

    out: dict[str, str] = {}
    for k, v in obj.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        name = Path(k).name
        cap = " ".join(v.strip().split())
        if not name or not cap:
            continue
        # First win (stable)
        out.setdefault(name, cap)

    return out


def _preferred_provider_order(display_provider: str) -> list[str]:
    p0 = (display_provider or "").strip().lower()
    if p0 and p0 not in {"auto", ""}:
        return [p0, "seedream", "glm"]
    return ["seedream", "glm"]


def _pick_cover_image(session: Session, *, paper_id: int, lang: str) -> Path | None:
    """Pick one AI-generated illustration as cover.

    Prefer app_config's display provider ordering; fallback to any generated image for this paper/lang.
    """

    lang0 = (lang or "en").strip().lower()
    if lang0 not in {"zh", "en"}:
        lang0 = "en"

    app_cfg = get_effective_app_config(session)
    providers = _preferred_provider_order(app_cfg.paper_images_display_provider)

    rows = session.exec(
        select(PaperImage)
        .where(PaperImage.paper_id == paper_id)
        .where(PaperImage.kind == "generated")
        .where(PaperImage.status == "generated")
        .where(PaperImage.enabled == True)  # noqa: E712
        .where(PaperImage.lang == lang0)
        .order_by(PaperImage.order_idx.asc(), PaperImage.id.asc())
    ).all()

    if not rows:
        return None

    by_provider: dict[str, list[PaperImage]] = {}
    for img in rows:
        by_provider.setdefault((img.provider or "").strip().lower(), []).append(img)

    for prov in providers:
        cand = (by_provider.get(prov) or [])
        for img in cand:
            lp = (img.local_path or "").strip()
            if not lp:
                continue
            p = Path(lp)
            if p.exists() and p.is_file():
                return p

    # fallback: first available local_path
    for img in rows:
        lp = (img.local_path or "").strip()
        if not lp:
            continue
        p = Path(lp)
        if p.exists() and p.is_file():
            return p

    return None


def _rewrite_markdown_for_epub(md_text: str, *, caption_by_basename: dict[str, str]) -> str:
    """Rewrite markdown for EPUB:

    - Normalize image URLs to `images/<basename>`
    - Append footnote markers for VLM captions when available
    - Add footnote definitions at the end

    Note: We intentionally keep this as a best-effort regex pass.
    """

    if not md_text:
        return ""

    footnotes: dict[str, str] = {}  # id -> caption
    basename2fid: dict[str, str] = {}
    next_id = 1

    def repl(m: re.Match) -> str:
        nonlocal next_id
        raw = (m.group(1) or "").strip()
        # raw may include a title, keep only the URL portion
        url0 = raw.split()[0].strip()
        if not url0:
            return m.group(0)

        name = Path(url0).name
        new_url = f"images/{name}" if name else url0
        img_md = m.group(0).replace(url0, new_url)

        cap = caption_by_basename.get(name)
        if not cap:
            return img_md

        fid = basename2fid.get(name)
        if not fid:
            fid = f"cap{next_id:04d}"
            next_id += 1
            basename2fid[name] = fid
            footnotes[fid] = cap

        return img_md + f" [^{fid}]"

    out = _MD_IMG_RE.sub(repl, md_text)

    if footnotes:
        out = out.rstrip() + "\n\n---\n\n"
        for fid, cap in footnotes.items():
            out += f"[^{fid}]: {cap}\n"

    return out


def _copy_tree_files(src: Path, dst: Path, *, exts: set[str] | None = None) -> int:
    if not src.exists() or not src.is_dir():
        return 0
    dst.mkdir(parents=True, exist_ok=True)

    n = 0
    for fp in sorted(src.iterdir()):
        if not fp.is_file():
            continue
        if exts and fp.suffix.lower() not in exts:
            continue
        shutil.copy2(fp, dst / fp.name)
        n += 1
    return n


def build_epub_for_paper(
    session: Session,
    *,
    paper: Paper,
    lang: str = "en",
    overwrite: bool = False,
) -> BuildResult | None:
    """Build an EPUB from the paper's MinerU markdown + assets using pandoc.

    Current PR generates the EN "original" edition.
    Translated/bilingual editions are planned for next PR.
    """

    lang0 = (lang or "en").strip().lower()
    if lang0 not in {"en", "zh"}:
        lang0 = "en"

    if not paper.raw_text_path:
        return None

    md_path = Path(paper.raw_text_path)
    if not md_path.exists() or not md_path.is_file():
        return None

    external_id = (paper.external_id or "").strip() or f"paper_{paper.id}"

    out_dir = Path(settings.epub_out_root) / external_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Naming: always include external_id in filename for easier sharing / downloads.
    # Example: 2602.04705.en.epub
    out_name = f"{external_id}.{lang0}.epub"
    out_file = out_dir / out_name
    url_path = f"/static/epub/{external_id}/{out_name}"

    # Backward compatibility: keep legacy filenames (en.epub / zh.epub) as links/copies.
    legacy_name = "en.epub" if lang0 == "en" else "zh.epub"
    legacy_file = out_dir / legacy_name

    def _ensure_alias(src: Path, alias: Path) -> None:
        if alias.exists():
            return
        try:
            import os

            os.link(src, alias)
        except Exception:
            try:
                shutil.copy2(src, alias)
            except Exception:
                pass

    # If we already have the new name, return (and ensure legacy alias exists).
    if out_file.exists() and not overwrite:
        _ensure_alias(out_file, legacy_file)
        return BuildResult(kind=lang0, local_path=str(out_file), url_path=url_path)

    # If only legacy exists (older release), create the new name as an alias and return.
    if legacy_file.exists() and not out_file.exists() and not overwrite:
        _ensure_alias(legacy_file, out_file)
        return BuildResult(kind=lang0, local_path=str(out_file), url_path=url_path)

    # Build workspace
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    build_dir = out_dir / "_build" / f"{lang0}_{ts}"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    (build_dir / "images").mkdir(parents=True, exist_ok=True)

    # Copy MinerU extracted images
    mineru_img_dir = md_path.parent / "images"
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    copied = _copy_tree_files(mineru_img_dir, build_dir / "images", exts=exts)

    # Cover: AI generated illustration (preferred)
    cover_src = _pick_cover_image(session, paper_id=int(paper.id), lang=lang0)
    cover_path: Path | None = None
    if cover_src:
        cover_path = build_dir / ("cover" + cover_src.suffix.lower())
        try:
            shutil.copy2(cover_src, cover_path)
        except Exception:
            cover_path = None

    # CSS
    css_path: Path | None = None
    try:
        p = Path(settings.epub_css_path)
        if p.exists() and p.is_file():
            css_path = build_dir / "epub.css"
            shutil.copy2(p, css_path)
    except Exception:
        css_path = None

    # Rewrite markdown
    md_text = md_path.read_text(encoding="utf-8", errors="ignore")
    caption_by_basename = _load_caption_by_basename(paper, lang=lang0)
    rewritten = _rewrite_markdown_for_epub(md_text, caption_by_basename=caption_by_basename)

    rewritten_path = build_dir / "book.md"
    rewritten_path.write_text(rewritten, encoding="utf-8")

    # Run pandoc
    out_tmp = build_dir / "out.epub"

    cmd: list[str] = [
        settings.pandoc_bin,
        "--from",
        "markdown+footnotes",
        "--to",
        "epub3",
        "--output",
        str(out_tmp),
        "--toc",
        "--toc-depth=3",
        "--epub-chapter-level=2",
        "--resource-path",
        str(build_dir),
        "--metadata",
        f"title={paper.title}",
        "--metadata",
        f"identifier={external_id}",
        "--metadata",
        f"lang={_lang_to_epub_lang(lang0)}",
    ]

    # Cover
    if cover_path and cover_path.exists():
        cmd += ["--epub-cover-image", str(cover_path)]

    # CSS
    if css_path and css_path.exists():
        cmd += ["--css", str(css_path)]

    cmd += [str(rewritten_path)]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out_tmp.exists():
        stderr = (r.stderr or "").strip()
        stdout = (r.stdout or "").strip()
        raise RuntimeError(f"pandoc failed rc={r.returncode}: {stderr or stdout}")

    # Atomic publish
    out_tmp.replace(out_file)

    # Backward compatibility: also publish legacy name.
    _ensure_alias(out_file, legacy_file)

    # Update DB (store canonical new filename)
    paper.epub_path_en = str(out_file) if lang0 == "en" else paper.epub_path_en
    paper.epub_url_en = url_path if lang0 == "en" else paper.epub_url_en
    if lang0 == "zh":
        paper.epub_path_zh = str(out_file)
        paper.epub_url_zh = url_path

    paper.updated_at = datetime.utcnow()
    session.add(paper)
    session.commit()

    return BuildResult(kind=lang0, local_path=str(out_file), url_path=url_path)


def build_epubs_for_pending(
    session: Session,
    *,
    day: str | None = None,
    external_ids: list[str] | None = None,
    langs: list[str] | None = None,
    max_n: int | None = None,
    overwrite: bool = False,
) -> list[BuildResult]:
    """Build EPUBs for papers that have MinerU markdown.

    For this PR, default lang should be ["en"].
    """

    max_n = int(max_n or settings.epub_max or 10)
    max_n = max(0, max_n)
    if max_n == 0:
        return []

    langs0 = [x.strip().lower() for x in (langs or ["en"]) if x.strip()]
    langs0 = [x for x in langs0 if x in {"en", "zh"}] or ["en"]

    q = select(Paper).where(Paper.raw_text_path.is_not(None)).where(Paper.source == "hf_daily")
    if external_ids:
        q = q.where(Paper.external_id.in_(external_ids))
    elif day:
        q = q.where(Paper.day == day)

    # Filter missing at SQL level when possible to avoid wasting the limit window.
    if not overwrite:
        if langs0 == ["en"]:
            q = q.where(Paper.epub_path_en.is_(None))
        elif langs0 == ["zh"]:
            q = q.where(Paper.epub_path_zh.is_(None))
        # if both: keep broader query, we'll skip per-language in Python

    rows = session.exec(q.order_by(Paper.id.asc()).limit(max_n)).all()

    import time

    out: list[BuildResult] = []
    for p in rows:
        for lang in langs0:
            # If we are not overwriting, only fill missing.
            if not overwrite:
                if lang == "en" and p.epub_path_en:
                    continue
                if lang == "zh" and p.epub_path_zh:
                    continue

            eid = (p.external_id or "").strip() or str(p.id)
            t0 = time.perf_counter()
            print(f"EPUB_BUILD_START[{lang}]: {eid}")
            r = build_epub_for_paper(session, paper=p, lang=lang, overwrite=overwrite)
            dt = time.perf_counter() - t0
            if r:
                out.append(r)
                print(f"EPUB_BUILD_DONE[{lang}]: {eid} seconds={dt:.2f} url={r.url_path}")
            else:
                print(f"EPUB_BUILD_SKIPPED[{lang}]: {eid} seconds={dt:.2f}")

    return out
