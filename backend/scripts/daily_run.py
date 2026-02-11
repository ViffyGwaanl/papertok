"""Daily pipeline (MVP):
1) Fetch HuggingFace daily papers top N
2) Upsert into DB
3) Generate one-liner summary via OpenAI-compatible API (local)

Run:
  python -m scripts.daily_run
"""

from __future__ import annotations

import json
import os
import re
import hashlib
import base64
from datetime import datetime
from pathlib import Path
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from sqlmodel import Session, select
from sqlalchemy import or_

from app.core.config import settings
from app.core.prompts import (
    CONTENT_ANALYSIS_SYSTEM_PROMPT_ZH,
    CONTENT_ANALYSIS_SYSTEM_PROMPT_EN,
)
from app.db.init_db import init_db
from app.db.engine import engine
from app.models.paper import Paper
from app.models.paper_image import PaperImage
from app.services.seedream_client import seedream_generate_image, seedream_has_keys
from app.services.glm_image_client import glm_image_generate, glm_image_has_keys
from app.services.app_config import get_effective_app_config
from app.services.paper_events import record_paper_event


def fetch_hf_daily(date: str) -> tuple[str, list[dict[str, Any]]]:
    """Fetch HF Daily Papers for a given date.

    HF sometimes rejects a "future" date (from their perspective) with 400 like:
      date must be <= "YYYY-MM-DDTHH:mm:ss.sssZ"

    In that case we automatically fallback to the max-allowed date and continue,
    so the daily job (scheduled in local time) won't fail every morning.

    Returns: (effective_date, items_top_n)
    """

    url = settings.hf_daily_papers_url
    headers = {
        # Be explicit; some CDNs rate-limit/deny default clients.
        "User-Agent": "papertok/0.1 (+https://papertok.ai)",
        "Accept": "application/json",
    }

    def _parse_max_date(err_msg: str) -> str | None:
        m = re.search(r'less than or equal to "(\d{4}-\d{2}-\d{2})T', err_msg)
        return m.group(1) if m else None

    with httpx.Client(timeout=30, trust_env=False, headers=headers) as client:
        r = client.get(url, params={"date": date})

        if r.status_code == 400:
            try:
                err = (r.json() or {}).get("error") or ""
            except Exception:
                err = r.text or ""

            max_date = _parse_max_date(str(err))
            if max_date and max_date != date:
                print(
                    f"HF_DAILY: requested date={date} rejected (400). "
                    f"Fallback to max_allowed_date={max_date}."
                )
                r = client.get(url, params={"date": max_date})
                r.raise_for_status()
                data = r.json()
                return max_date, data[: settings.hf_top_n]

        r.raise_for_status()
        data = r.json()
        return date, data[: settings.hf_top_n]


def _safe_filename(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)


def arxiv_pdf_url(arxiv_id: str) -> str:
    # supports 2602.04705, 2602.04705v2, cs/0601001
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"


def download_pdf(arxiv_id: str) -> tuple[str, str, str]:
    """Download arXiv PDF; return (pdf_url, pdf_path, sha256)."""
    os.makedirs(settings.papers_pdf_dir, exist_ok=True)

    pdf_url = arxiv_pdf_url(arxiv_id)
    filename = _safe_filename(arxiv_id) + ".pdf"
    pdf_path = os.path.join(settings.papers_pdf_dir, filename)

    if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
        # best-effort sha reuse (avoid reading entire file unless needed)
        return pdf_url, pdf_path, ""

    h = hashlib.sha256()
    with httpx.stream(
        "GET", pdf_url, timeout=120, follow_redirects=True, trust_env=False
    ) as r:
        r.raise_for_status()
        with open(pdf_path, "wb") as f:
            for chunk in r.iter_bytes():
                if not chunk:
                    continue
                f.write(chunk)
                h.update(chunk)

    return pdf_url, pdf_path, h.hexdigest()


def openai_chat(prompt: str, model: str, *, system_prompt: str = "You are a precise academic assistant.") -> str:
    """OpenAI-compatible /v1/chat/completions wrapper (tolerant parsing)."""
    url = settings.openai_base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
    }

    return _openai_chat_payload(payload, url=url, headers=headers)


def openai_vision_caption(
    *, title: str, image_path: Path, model: str, context_text: str | None = None, lang: str = "zh"
) -> str:
    """Caption one image using an OpenAI-compatible vision model (zh/en).

    Optionally includes nearby markdown context (for better table/flowchart captions).
    """

    # Encode image as data URL to avoid relying on any running HTTP server.
    suffix = image_path.suffix.lower().lstrip(".")
    mime = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(suffix, "image/jpeg")

    b = image_path.read_bytes()
    data_url = f"data:{mime};base64,{base64.b64encode(b).decode('ascii')}"

    lang0 = (lang or "zh").strip().lower()
    if lang0 not in {"zh", "en"}:
        lang0 = "zh"

    if lang0 == "en":
        system_prompt = (
            "You are a rigorous academic assistant. Write concise, accurate figure captions in English.\n"
            "Requirements:\n"
            "- Output only 1-2 sentences in English (no numbering, no prefix)\n"
            "- Identify figure type (pipeline, architecture, curve, table, diagram, etc.) and the main message\n"
            "- Do NOT fabricate numbers; if uncertain, use cautious phrasing (e.g., 'the figure suggests')\n"
        )
    else:
        system_prompt = (
            "你是一位严谨的学术助手，擅长为论文图表生成简洁准确的中文图注。\n"
            "要求：\n"
            "- 只输出 1-2 句话中文，不要编号，不要前缀\n"
            "- 描述图类型（流程图/结构图/曲线/表格/示意图等）+ 主要表达的信息\n"
            "- 不要编造数值；不确定就用‘图中显示/可能表示’等措辞\n"
        )

    ctx = (context_text or "").strip()
    if len(ctx) > 2500:
        ctx = ctx[:2500]

    if lang0 == "en":
        user_text = f"Please write an English caption for this figure.\nTitle: {title}\n"
        if ctx:
            user_text += "\nNearby paper text (from MinerU markdown, for reference):\n" + ctx + "\n"
    else:
        user_text = "请根据这张图生成中文图注。\n" f"论文标题：{title}\n"
        if ctx:
            user_text += "\n图附近原文（从 MinerU markdown 截取，供参考）：\n" + ctx + "\n"

    user_content = [
        {
            "type": "text",
            "text": user_text,
        },
        {"type": "image_url", "image_url": {"url": data_url}},
    ]

    url = settings.openai_base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
    }

    return _openai_chat_payload(payload, url=url, headers=headers)


def _openai_chat_payload(payload: dict, *, url: str, headers: dict) -> str:
    last_err = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=180, trust_env=False) as client:
                r = client.post(url, headers=headers, json=payload)
                r.raise_for_status()
                j = r.json()
            break
        except Exception as e:
            last_err = e
            if attempt < 2:
                import time

                time.sleep(1.5 * (attempt + 1))
            else:
                raise

    if last_err and 'j' not in locals():
        raise last_err

    choice0 = (j.get("choices") or [{}])[0] or {}

    # Standard OpenAI schema
    msg = choice0.get("message")
    if isinstance(msg, dict) and isinstance(msg.get("content"), str):
        return msg["content"].strip()

    # Some compat servers return `text` on choices
    if isinstance(choice0.get("text"), str):
        return choice0["text"].strip()

    raise ValueError(f"Unexpected LLM response schema: {list(j.keys())}")


def _extract_abstract_from_mineru_markdown(md_text: str) -> str | None:
    """Best-effort extraction of the Abstract section from MinerU markdown."""

    if not md_text or not md_text.strip():
        return None

    lines = md_text.splitlines()

    # Find a heading like "# Abstract" / "## Abstract" / "# 摘要"
    start_idx = None
    start_level = None
    for i, line in enumerate(lines):
        m = re.match(r"^\s*(#{1,6})\s*(abstract|摘要)\b", line.strip(), flags=re.I)
        if m:
            start_idx = i + 1
            start_level = len(m.group(1))
            break

    if start_idx is None:
        return None

    # Collect until next heading of same or higher level.
    buf: list[str] = []
    for line in lines[start_idx:]:
        if re.match(r"^\s*#{1,%d}\s+" % start_level, line):
            break

        s = line.strip()
        if not s:
            if buf and buf[-1] != "":
                buf.append("")
            continue

        # Skip images / tables / obvious markdown noise
        if s.startswith("![](") or s.startswith("!["):
            continue
        if s.startswith("|"):
            continue

        buf.append(s)

    text = "\n".join(buf).strip()
    text = re.sub(r"\s+", " ", text)
    return text or None


def build_one_liner(title: str, abstract: str | None, *, lang: str = "zh") -> str:
    abstract = (abstract or "").strip()
    lang0 = (lang or "zh").strip().lower()
    if lang0 not in {"zh", "en"}:
        lang0 = "zh"

    if lang0 == "en":
        prompt = (
            "Write exactly ONE sentence in English summarizing this paper.\n"
            "Requirements:\n"
            "- Output only one sentence, no prefix, no numbering\n"
            "- ~15-25 words, high information density\n"
            "- Try to include at least two of: problem, method, contribution\n\n"
            f"Title: {title}\n"
            f"Abstract: {abstract}\n"
        )
    else:
        prompt = (
            "请【必须用中文】输出：一句话总结这篇论文，要求：\n"
            "- 只输出一句话，不要编号，不要前缀\n"
            "- 20~35个汉字左右，信息密度高\n"
            "- 尽量包含：问题/方法/贡献中的至少两项\n\n"
            f"标题：{title}\n"
            f"摘要：{abstract}\n"
        )

    return openai_chat(prompt, settings.llm_model_text)



def run_mineru_for_pending(
    session: Session, *, day: str | None = None, external_ids: list[str] | None = None
) -> None:
    """Optionally run mineru for a few pending PDFs (heavy)."""

    if not settings.run_mineru:
        return

    try:
        # Import lazily so base MVP can run without mineru deps installed.
        from app.services.mineru_runner import run_mineru_pdf_to_md
    except Exception as e:
        print(f"WARN: RUN_MINERU=1 but mineru is not available: {e}")
        return

    max_n = max(0, int(settings.mineru_max))
    if max_n == 0:
        print("MINERU: enabled but MINERU_MAX=0 -> skipping")
        return

    q = (
        select(Paper)
        .where(Paper.pdf_path.is_not(None))
        .where(Paper.raw_text_path.is_(None))
    )
    if external_ids:
        q = q.where(Paper.external_id.in_(external_ids))
    elif day:
        q = q.where(Paper.day == day)

    rows = session.exec(q.order_by(Paper.id.asc()).limit(max_n)).all()

    if not rows:
        print("MINERU: nothing to do")
        return

    for p in rows:
        try:
            record_paper_event(session, paper_id=p.id, stage="mineru", status="started")
            print(f"MINERU: {p.external_id} -> parsing...")

            def _try_parse(pdf_in: str):
                return run_mineru_pdf_to_md(
                    pdf_path=pdf_in,
                    out_root=settings.mineru_out_root,
                    model_source=settings.mineru_model_source,
                    backend="pipeline",
                    method="txt",
                    lang="en",
                    formula=False,
                    table=False,
                )

            # Attempt 1: original PDF
            first_err: Exception | None = None
            try:
                res = _try_parse(p.pdf_path)
            except Exception as e1:
                first_err = e1
                # create a dummy result-like object so code below can proceed
                class _Dummy:
                    md_path = Path(settings.mineru_out_root) / (p.external_id or "") / "txt" / f"{p.external_id}.md"
                res = _Dummy()  # type: ignore

            # If md missing OR mineru threw, optionally try repair+retry (cache copy) once.
            if (first_err is not None or not Path(getattr(res, "md_path")).exists()) and settings.mineru_repair_on_fail:
                from app.services.pdf_repair import repair_pdf_for_pdfium

                stem = Path(p.pdf_path).stem
                repaired_pdf = Path(settings.mineru_repair_cache_dir) / f"{stem}.pdf"

                # Only attempt repair on failure; keep original PDF untouched.
                if not repaired_pdf.exists() or repaired_pdf.stat().st_size < 1024:
                    record_paper_event(session, paper_id=p.id, stage="pdf_repair", status="started")
                    rr = repair_pdf_for_pdfium(
                        input_pdf=p.pdf_path,
                        output_pdf=repaired_pdf,
                        tool=settings.mineru_repair_tool,
                    )
                    if rr.ok:
                        record_paper_event(
                            session,
                            paper_id=p.id,
                            stage="pdf_repair",
                            status="success",
                            meta={"tool": rr.tool, "output_pdf": str(repaired_pdf)},
                        )
                        print(f"PDF_REPAIR_OK: {p.external_id} tool={rr.tool} -> {repaired_pdf}")
                    else:
                        record_paper_event(
                            session,
                            paper_id=p.id,
                            stage="pdf_repair",
                            status="failed",
                            error=rr.error or "repair failed",
                            meta={"tool": settings.mineru_repair_tool, "output_pdf": str(repaired_pdf)},
                        )
                        print(f"WARN: PDF_REPAIR failed for {p.external_id}: {rr.error}")

                # Attempt 2: repaired cache copy (if exists)
                if repaired_pdf.exists() and repaired_pdf.stat().st_size >= 1024:
                    print(f"MINERU_RETRY: {p.external_id} using repaired PDF -> parsing...")
                    res = _try_parse(str(repaired_pdf))

            if res.md_path.exists():
                p.raw_text_path = str(res.md_path)
                p.updated_at = datetime.utcnow()
                session.add(p)
                session.commit()
                record_paper_event(
                    session,
                    paper_id=p.id,
                    stage="mineru",
                    status="success",
                    meta={"md_path": str(res.md_path)},
                )
                print(f"MINERU_OK: {p.external_id} -> {res.md_path}")
            else:
                err_msg = None
                if first_err is not None:
                    err_msg = str(first_err)
                else:
                    err_msg = f"mineru output missing md: {res.md_path}"

                record_paper_event(
                    session,
                    paper_id=p.id,
                    stage="mineru",
                    status="failed",
                    error=err_msg,
                )
                print(f"WARN: mineru failed for {p.external_id}: {err_msg}")
        except Exception as e:
            record_paper_event(session, paper_id=p.id, stage="mineru", status="failed", error=str(e))
            print(f"WARN: mineru failed for {p.external_id}: {e}")



def build_content_explain(*, title: str, markdown_text: str, lang: str = "zh") -> str:
    """Generate teaching-style explanation for a paper markdown (zh/en)."""

    lang0 = (lang or "zh").strip().lower()
    if lang0 not in {"zh", "en"}:
        lang0 = "zh"

    if lang0 == "en":
        prompt = (
            "Below is Markdown extracted from a research paper PDF (via MinerU).\n"
            "Follow the system instructions strictly.\n"
            "Important: do NOT fabricate numbers or results; if unknown, say so.\n\n"
            f"Title: {title}\n\n"
            "Body (may be truncated):\n"
            f"{markdown_text}\n"
        )
        system_prompt = CONTENT_ANALYSIS_SYSTEM_PROMPT_EN
    else:
        prompt = (
            "下面是用 MinerU 从论文 PDF 解析出来的 Markdown 文本。\n"
            "请严格遵循系统提示词的要求来分析和讲解。\n"
            "注意：不要编造数字或实验结论；涉及数字时必须来自原文或明确写出‘原文未给出/需查证’。\n"
            "并且【必须输出中文】。\n"
            "输出尽量控制在 800~1500 个中文字符以内。\n\n"
            f"论文标题：{title}\n\n"
            "正文（可能被截断）：\n"
            f"{markdown_text}\n"
        )
        system_prompt = CONTENT_ANALYSIS_SYSTEM_PROMPT_ZH

    return openai_chat(
        prompt,
        settings.llm_model_analysis,
        system_prompt=system_prompt,
    )


def build_content_explain_cn(*, title: str, markdown_text: str) -> str:
    """Backward compatible wrapper (zh)."""

    return build_content_explain(title=title, markdown_text=markdown_text, lang="zh")



def run_content_analysis_for_pending(
    session: Session, *, day: str | None = None, external_ids: list[str] | None = None
) -> None:
    """Optionally analyze parsed markdown into teaching-style explanation (LLM).

    Controlled by:
    - RUN_CONTENT_ANALYSIS=1
    - CONTENT_ANALYSIS_MAX
    - PAPERTOK_LANGS=zh,en

    Feed gating is language-aware in /api/papers/random.
    """

    if not settings.run_content_analysis:
        return

    max_n = max(0, int(settings.content_analysis_max))
    if max_n == 0:
        print("CONTENT_ANALYSIS: enabled but CONTENT_ANALYSIS_MAX=0 -> skipping")
        return

    if not settings.openai_api_key:
        print("WARN: RUN_CONTENT_ANALYSIS=1 but OPENAI_API_KEY is empty -> skipping")
        return

    langs = [x.strip().lower() for x in (settings.papertok_langs or ["zh"]) if x.strip()]
    langs = [x for x in langs if x in {"zh", "en"}] or ["zh"]

    for lang0 in langs:
        stage = "explain_en" if lang0 == "en" else "explain"
        explain_col = Paper.content_explain_en if lang0 == "en" else Paper.content_explain_cn

        q = select(Paper).where(Paper.raw_text_path.is_not(None)).where(explain_col.is_(None))
        if external_ids:
            q = q.where(Paper.external_id.in_(external_ids))
        elif day:
            q = q.where(Paper.day == day)

        rows = session.exec(q.order_by(Paper.id.asc()).limit(max_n)).all()

        if not rows:
            print(f"CONTENT_ANALYSIS[{lang0}]: nothing to do")
            continue

        # Concurrency: run LLM calls in parallel, then write results back in the main thread.
        conc = int(getattr(settings, "content_analysis_concurrency", 1) or 1)
        conc = max(1, min(conc, 16))

        items: list[tuple[int, str, str, str]] = []  # (paper_id, external_id, title, raw_text_path)
        by_id: dict[int, Paper] = {}
        for p in rows:
            by_id[int(p.id)] = p
            record_paper_event(session, paper_id=p.id, stage=stage, status="started")
            items.append((int(p.id), str(p.external_id or ""), str(p.title or ""), str(p.raw_text_path or "")))

        def _task(it: tuple[int, str, str, str]) -> tuple[int, str | None, str | None]:
            pid, eid, title, raw_path = it
            path = Path(raw_path or "")
            if not raw_path or not path.exists():
                return pid, None, f"raw_text_path missing on disk: {raw_path}"

            text = path.read_text(encoding="utf-8", errors="ignore")
            text = text[: int(settings.content_analysis_input_chars)]
            out = build_content_explain(title=title, markdown_text=text, lang=lang0)
            return pid, (out or "").strip(), None

        if conc <= 1 or len(items) <= 1:
            for it in items:
                pid, eid, _, _ = it
                try:
                    print(f"CONTENT_ANALYSIS[{lang0}]: {eid} -> generating...")
                    pid2, out, err = _task(it)
                    if err:
                        record_paper_event(session, paper_id=pid2, stage=stage, status="failed", error=err)
                        print(f"WARN: {err}")
                        continue

                    p = by_id.get(pid2)
                    if not p:
                        continue
                    if lang0 == "en":
                        p.content_explain_en = out
                    else:
                        p.content_explain_cn = out

                    p.updated_at = datetime.utcnow()
                    session.add(p)
                    session.commit()
                    record_paper_event(session, paper_id=pid2, stage=stage, status="success")
                    print(f"CONTENT_ANALYSIS_OK[{lang0}]: {eid}")
                except Exception as e:
                    record_paper_event(session, paper_id=pid, stage=stage, status="failed", error=str(e))
                    print(f"WARN: content analysis failed[{lang0}] for {eid}: {e}")
        else:
            print(f"CONTENT_ANALYSIS[{lang0}]: concurrency={conc} papers={len(items)}")
            with ThreadPoolExecutor(max_workers=conc) as ex:
                fut_map = {ex.submit(_task, it): it for it in items}
                for fut in as_completed(fut_map):
                    pid, eid, _, _ = fut_map[fut]
                    try:
                        pid2, out, err = fut.result()
                        if err:
                            record_paper_event(session, paper_id=pid2, stage=stage, status="failed", error=err)
                            print(f"WARN: {err}")
                            continue

                        p = by_id.get(pid2)
                        if not p:
                            continue
                        if lang0 == "en":
                            p.content_explain_en = out
                        else:
                            p.content_explain_cn = out

                        p.updated_at = datetime.utcnow()
                        session.add(p)
                        session.commit()
                        record_paper_event(session, paper_id=pid2, stage=stage, status="success")
                        print(f"CONTENT_ANALYSIS_OK[{lang0}]: {eid}")
                    except Exception as e:
                        record_paper_event(session, paper_id=pid, stage=stage, status="failed", error=str(e))
                        print(f"WARN: content analysis failed[{lang0}] for {eid}: {e}")



def _image_rel_url(fp: Path) -> str | None:
    """Map an on-disk file path to the relative URL served by /static/mineru."""
    try:
        root = Path(settings.mineru_out_root).resolve()
        rel = fp.resolve().relative_to(root)
        return "/static/mineru/" + rel.as_posix()
    except Exception:
        return None


_MD_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def _md_is_heading(line: str) -> tuple[int, str] | None:
    m = re.match(r"^\s*(#{1,6})\s+(.+?)\s*$", line)
    if not m:
        return None
    level = len(m.group(1))
    title = m.group(2).strip()
    return level, title


def _md_paragraph_bounds(lines: list[str], idx: int) -> tuple[int, int]:
    # paragraph = consecutive non-empty lines
    start = idx
    while start > 0 and lines[start - 1].strip() != "":
        start -= 1
    end = idx
    while end + 1 < len(lines) and lines[end + 1].strip() != "":
        end += 1
    return start, end


def _md_clean_block(block_lines: list[str]) -> str:
    cleaned: list[str] = []
    for ln in block_lines:
        s = ln.rstrip()
        if not s.strip():
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue

        # drop other images-only lines to reduce noise
        if s.lstrip().startswith("!["):
            continue

        cleaned.append(s)

    # collapse multiple blank lines
    out: list[str] = []
    for ln in cleaned:
        if ln == "" and (not out or out[-1] == ""):
            continue
        out.append(ln)

    return "\n".join(out).strip()


def _extract_image_context_from_markdown(
    md_text: str,
    *,
    filename: str,
    window_chars: int,
    strategy: str = "merge",
    max_occurrences: int = 3,
) -> str | None:
    """Extract cleaner context around an image reference.

    More engineered than a raw char window:
    - find markdown image refs that point to this filename
    - for each occurrence, extract: nearest heading breadcrumb + paragraph block around image
    - handle multiple occurrences via strategy:
        - last: take only the last occurrence
        - merge: merge up to max_occurrences (latest first) with separators

    The final output is truncated to window_chars.
    """

    if not md_text or not filename:
        return None

    window_chars = max(200, int(window_chars))
    max_occurrences = max(1, int(max_occurrences))
    strategy = (strategy or "merge").strip().lower()

    lines = md_text.splitlines()

    # Find line indices where an image ref includes this filename
    occ: list[int] = []
    for i, line in enumerate(lines):
        if filename not in line:
            continue
        for m in _MD_IMG_RE.finditer(line):
            url = (m.group(1) or "").strip()
            if not url:
                continue
            if filename in url:
                occ.append(i)
                break

    if not occ:
        # fallback: plain substring search (covers edge formats)
        for i, line in enumerate(lines):
            if f"images/{filename}" in line or filename in line:
                occ.append(i)
        if not occ:
            return None

    # choose occurrences
    occ = sorted(set(occ))
    if strategy == "last":
        chosen = [occ[-1]]
    else:
        chosen = list(reversed(occ))[:max_occurrences]

    def build_block(at: int) -> str | None:
        # heading breadcrumb (nearest heading, plus its parent)
        crumb: list[str] = []
        found_level: int | None = None
        for j in range(at, -1, -1):
            h = _md_is_heading(lines[j])
            if not h:
                continue
            lvl, title = h
            if found_level is None:
                crumb.append(title)
                found_level = lvl
            else:
                if lvl < found_level:
                    crumb.append(title)
                    break

        crumb = list(reversed(crumb))

        # paragraph around image, plus neighbor paragraphs (best-effort)
        p0s, p0e = _md_paragraph_bounds(lines, at)

        def prev_paragraph(start: int) -> tuple[int, int] | None:
            k = start - 2
            if k < 0:
                return None
            while k >= 0 and lines[k].strip() == "":
                k -= 1
            if k < 0:
                return None
            return _md_paragraph_bounds(lines, k)

        def next_paragraph(end: int) -> tuple[int, int] | None:
            k = end + 2
            if k >= len(lines):
                return None
            while k < len(lines) and lines[k].strip() == "":
                k += 1
            if k >= len(lines):
                return None
            return _md_paragraph_bounds(lines, k)

        prevb = prev_paragraph(p0s)
        nextb = next_paragraph(p0e)

        block_lines: list[str] = []
        if crumb:
            block_lines.append("章节：" + " > ".join(crumb))
        if prevb:
            block_lines += lines[prevb[0] : prevb[1] + 1]
            block_lines.append("")
        block_lines += lines[p0s : p0e + 1]
        if nextb:
            block_lines.append("")
            block_lines += lines[nextb[0] : nextb[1] + 1]

        txt = _md_clean_block(block_lines)
        return txt or None

    blocks: list[str] = []
    for at in chosen:
        b = build_block(at)
        if not b:
            continue
        if b not in blocks:
            blocks.append(b)

    if not blocks:
        return None

    merged = "\n\n---\n\n".join(blocks)
    if len(merged) > window_chars:
        merged = merged[:window_chars]

    return merged.strip() or None


def run_image_caption_for_pending(
    session: Session, *, day: str | None = None, external_ids: list[str] | None = None
) -> None:
    """Optionally caption MinerU extracted images with a VLM and cache to DB (zh/en).

    Supports limited concurrency inside a single job via IMAGE_CAPTION_CONCURRENCY / settings.image_caption_concurrency.

    Controlled by:
    - RUN_IMAGE_CAPTION=1
    - PAPERTOK_LANGS=zh,en

    Captions are stored separately:
    - zh -> papers.image_captions_json
    - en -> papers.image_captions_en_json
    """

    if not settings.run_image_caption:
        return

    max_total = max(0, int(settings.image_caption_max))
    if max_total == 0:
        print("IMAGE_CAPTION: enabled but IMAGE_CAPTION_MAX=0 -> skipping")
        return

    if not settings.openai_api_key:
        print("WARN: RUN_IMAGE_CAPTION=1 but OPENAI_API_KEY is empty -> skipping")
        return

    per_paper = max(1, int(settings.image_caption_per_paper))

    # Load app-level config from DB so Admin UI changes are respected by both server + jobs.
    app_cfg = get_effective_app_config(session)
    ctx_chars = int(app_cfg.image_caption_context_chars)
    ctx_strategy = str(app_cfg.image_caption_context_strategy)
    ctx_occ = int(app_cfg.image_caption_context_occurrences)

    q = select(Paper).where(Paper.raw_text_path.is_not(None))
    if external_ids:
        q = q.where(Paper.external_id.in_(external_ids))
    elif day:
        q = q.where(Paper.day == day)

    rows = session.exec(q.order_by(Paper.id.asc())).all()

    if not rows:
        print("IMAGE_CAPTION: nothing to do")
        return

    langs = [x.strip().lower() for x in (settings.papertok_langs or ["zh"]) if x.strip()]
    langs = [x for x in langs if x in {"zh", "en"}] or ["zh"]

    done = 0

    for lang0 in langs:
        if done >= max_total:
            break

        stage = "caption_en" if lang0 == "en" else "caption"

        for p in rows:
            if done >= max_total:
                break

            md_path = Path(p.raw_text_path or "")
            img_dir = md_path.parent / "images"

            # Load markdown once for per-image context extraction
            md_text = ""
            try:
                if md_path.exists():
                    md_text = md_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                md_text = ""
            if not img_dir.exists() or not img_dir.is_dir():
                continue

            # load existing captions by lang
            captions: dict[str, str] = {}
            raw_json = p.image_captions_en_json if lang0 == "en" else p.image_captions_json
            if raw_json:
                try:
                    captions = json.loads(raw_json) or {}
                    if not isinstance(captions, dict):
                        captions = {}
                except Exception:
                    captions = {}

            # collect image files
            exts = {".jpg", ".jpeg", ".png", ".webp"}
            files = [fp for fp in sorted(img_dir.iterdir()) if fp.is_file() and fp.suffix.lower() in exts]
            if not files:
                continue

            paper_added = 0
            started_event = False
            failed_event = False

            # Build a todo list (missing captions only)
            todo: list[tuple[Path, str]] = []  # (file_path, rel_url)
            for fp in files:
                url = _image_rel_url(fp)
                if not url:
                    continue
                if captions.get(url):
                    continue
                todo.append((fp, url))
            
            if not todo:
                continue
            
            max_workers = max(1, int(getattr(settings, "image_caption_concurrency", 1) or 1))
            
            # Schedule at most remaining quotas for this paper
            remaining_total = max(0, max_total - done)
            remaining_paper = max(0, per_paper - paper_added)
            to_run = todo[: max(0, min(remaining_total, remaining_paper, len(todo)))]
            
            if not to_run:
                continue
            
            futs = {}
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                for fp, url in to_run:
                    try:
                        if not started_event:
                            record_paper_event(
                                session,
                                paper_id=p.id,
                                stage=stage,
                                status="started",
                                meta={"images_total": len(files), "concurrency": max_workers},
                            )
                            started_event = True
            
                        ctx = _extract_image_context_from_markdown(
                            md_text,
                            filename=fp.name,
                            window_chars=ctx_chars,
                            strategy=ctx_strategy,
                            max_occurrences=ctx_occ,
                        )
                        print(f"IMAGE_CAPTION[{lang0}]: {p.external_id} {fp.name} -> generating...")
                        fut = ex.submit(
                            openai_vision_caption,
                            title=p.title,
                            image_path=fp,
                            model=settings.image_caption_model,
                            context_text=ctx,
                            lang=lang0,
                        )
                        futs[fut] = (url, fp.name)
                    except Exception as e:
                        if not failed_event:
                            record_paper_event(session, paper_id=p.id, stage=stage, status="failed", error=str(e))
                            failed_event = True
                        print(f"WARN: image caption schedule failed[{lang0}] for {p.external_id} {fp.name}: {e}")
            
                for fut in as_completed(list(futs.keys())):
                    url, fname = futs.get(fut, (None, None))
                    if not url:
                        continue
                    try:
                        cap = fut.result()
                        cap = (cap or "").strip()
                        if not cap:
                            continue
                        captions[url] = cap
                        paper_added += 1
                        done += 1
            
                        # Persist incrementally so UI can see progress while the job is still running.
                        if lang0 == "en":
                            p.image_captions_en_json = json.dumps(captions, ensure_ascii=False)
                        else:
                            p.image_captions_json = json.dumps(captions, ensure_ascii=False)
                        p.updated_at = datetime.utcnow()
                        session.add(p)
                        session.commit()
                        print(
                            f"IMAGE_CAPTION_SAVE[{lang0}]: {p.external_id} saved {paper_added} / {len(files)} (total={done}/{max_total})"
                        )
            
                        if done >= max_total or paper_added >= per_paper:
                            # Do not schedule more; remaining futures will still finish but we stop counting.
                            pass
                    except Exception as e:
                        if not failed_event:
                            record_paper_event(session, paper_id=p.id, stage=stage, status="failed", error=str(e))
                            failed_event = True
                        print(f"WARN: image caption failed[{lang0}] for {p.external_id} {fname}: {e}")
            if paper_added > 0:
                record_paper_event(
                    session,
                    paper_id=p.id,
                    stage=stage,
                    status="success",
                    meta={"added": paper_added, "images_total": len(files)},
                )
                print(f"IMAGE_CAPTION_OK[{lang0}]: {p.external_id} (+{paper_added}, total={done}/{max_total})")



def _parse_size(size: str) -> tuple[int, int]:
    m = re.match(r"^(\d+)x(\d+)$", size.strip().lower())
    if not m:
        raise ValueError(f"Invalid size: {size}")
    return int(m.group(1)), int(m.group(2))


def build_paper_images_plan(
    *, title: str, one_liner: str, explain: str | None, n: int, lang: str = "zh"
) -> list[dict[str, str]]:
    """Generate an N-image plan for magazine collage style illustrations.

    IMPORTANT: When PAPER_IMAGES_PLAN_LLM=1, we do NOT just use the template.
    We feed the template + explanation to an LLM and ask it to rewrite prompts.
    """

    explain = (explain or "").strip()

    def _try_parse_json_array(text: str):
        text = (text or "").strip()
        try:
            return json.loads(text)
        except Exception:
            # Try to recover from code fences / extra text.
            l = text.find("[")
            r = text.rfind("]")
            if l != -1 and r != -1 and r > l:
                return json.loads(text[l : r + 1])
            raise

    lang0 = (lang or "zh").strip().lower()
    if lang0 not in {"zh", "en"}:
        lang0 = "zh"

    base_style_zh = (
        "实体手工剪贴簿/杂志拼贴风格，混合媒介，纸张纹理，撕边，胶带，便签，涂鸦箭头，手写批注，照片与图标拼贴层次，颗粒感，柔和阴影，portrait 9:16"
    )
    base_style_en = (
        "Physical handmade scrapbook / magazine collage style, mixed media, paper texture, torn edges, tape, sticky notes, doodle arrows, handwritten annotations, photo+icon+paper cutout layering, subtle grain, soft shadow, portrait 9:16"
    )
    base_style = base_style_en if lang0 == "en" else base_style_zh

    # Template is used as STRUCTURE/examples for LLM rewriting.
    hint = re.sub(r"\s+", " ", explain) if explain else ""

    templ_all = (
        [
            {
                "title": "Problem & Motivation",
                "prompt": f"{base_style}. Scene: a researcher arranges a 'problem' sticky note with messy clippings into a clear task list, symbolizing the core bottleneck. Center it around: {title}.",
                "negative_prompt": "watermark, logo, lowres, blurry, long text",
            },
            {
                "title": "Method Overview",
                "prompt": f"{base_style}. Scene: colorful paper blocks connected by arrows form a modular pipeline; small handwritten keywords and symbols highlight 'modules' and 'composition'. Based on: {one_liner}.",
                "negative_prompt": "watermark, logo, lowres, blurry, long text",
            },
            {
                "title": "Experiments & Results",
                "prompt": f"{base_style}. Scene: several small chart cards (numbers not readable) taped together, with up arrows and comparison labels to convey performance gains. Based on: {one_liner}.",
                "negative_prompt": "watermark, logo, lowres, blurry, long text",
            },
            {
                "title": "Key Mechanism",
                "prompt": f"{base_style}. Scene: gears and connection lines under a magnifying glass, linked by stickers to show information flow and the key intuition. Theme: {title}.",
                "negative_prompt": "watermark, logo, lowres, blurry, long text",
            },
            {
                "title": "Applications",
                "prompt": f"{base_style}. Scene: the method modules are pasted into several small photo frames representing different application scenarios (use abstract icons), showing transferability. Theme: {title}.",
                "negative_prompt": "watermark, logo, lowres, blurry, long text",
            },
        ]
        if lang0 == "en"
        else [
            {
                "title": "问题与动机",
                "prompt": f"{base_style}。画面：一个研究者在桌面上把‘问题’便利贴与混乱资料剪贴成一张清晰任务清单，象征论文要解决的核心瓶颈。主题围绕：{title}。",
                "negative_prompt": "watermark, logo, lowres, blurry, long text",
            },
            {
                "title": "方法概览",
                "prompt": f"{base_style}。画面：用流程箭头把几块彩色纸片拼成模块化管线，代表方法结构与关键组件，旁边有手写短词与符号强调‘方法/模块/组合’。基于：{one_liner}。",
                "negative_prompt": "watermark, logo, lowres, blurry, long text",
            },
            {
                "title": "实验与结果",
                "prompt": f"{base_style}。画面：几张小图表卡片（不可读数字）被胶带贴在一起，上方有上升箭头与对比标签贴纸，表达性能提升与对比实验。基于：{one_liner}。",
                "negative_prompt": "watermark, logo, lowres, blurry, long text",
            },
            {
                "title": "关键机制",
                "prompt": f"{base_style}。画面：放大镜下的齿轮与连接线被贴纸连接，表现关键机制与信息流，突出改进点与直觉解释。主题：{title}。",
                "negative_prompt": "watermark, logo, lowres, blurry, long text",
            },
            {
                "title": "应用场景",
                "prompt": f"{base_style}。画面：把方法模块贴到不同应用场景的小照片框里（抽象图标即可），表现可迁移与落地。主题：{title}。",
                "negative_prompt": "watermark, logo, lowres, blurry, long text",
            },
        ]
    )

    # pick a balanced subset: n=3 -> problem/method/results
    templ = templ_all[:3] if n <= 3 else templ_all[:n]

    use_llm = os.getenv("PAPER_IMAGES_PLAN_LLM", "").lower() in {"1", "true", "yes"}

    if use_llm:
        # Use explanation up to a hard cap (default 20000 chars). No chunking.
        explain_chars = int(os.getenv("PAPER_IMAGES_PLAN_EXPLAIN_CHARS", "20000"))
        explain_chars = max(1000, explain_chars)
        explain_snip = hint[:explain_chars]

        # No chunking/summarize step; feed the explanation snippet directly.

        if lang0 == "en":
            system_prompt = (
                "You are a senior prompt designer for physical handmade scrapbook / magazine collage illustrations.\n"
                f"Task: based on the paper explanation, produce prompts for {n} vertical (portrait) illustrations.\n"
                "Style requirements: physical handmade scrapbook / magazine collage, mixed media, paper texture, torn edges, tape, sticky notes, doodle arrows, handwritten annotations, layered photo+icon+paper cutouts, subtle grain, soft shadow.\n"
                "Each image should use visual metaphors to convey the paper's key points (problem/method/results), NOT screenshots.\n"
                "Safety: no real logos/watermarks. Avoid long readable paragraphs in the image (short handwritten words/symbols are ok).\n"
                "Output: ONLY a strict JSON array (no code fences, no explanation).\n"
                f"Array length must be exactly {n}. Each item must include: title, prompt, negative_prompt.\n"
                "Each prompt MUST explicitly include 'portrait 9:16' and describe the main subject + composition.\n"
                "Language: prompts MUST be written in English.\n"
            )

            user_prompt = (
                "Rewrite the TEMPLATE prompts using the EXPLANATION so each image matches the paper more closely.\n"
                "The template is structure-only; do NOT copy it verbatim. Integrate key concepts from the explanation into visual metaphors.\n\n"
                f"Title: {title}\n"
                f"One-liner: {one_liner}\n"
                + (f"Explanation (max {explain_chars} chars): {explain_snip}\n" if explain_snip else "")
                + "\nTEMPLATE prompts (rewrite each):\n"
                + json.dumps(templ, ensure_ascii=False)
            )
        else:
            system_prompt = (
                "你是一位资深杂志拼贴（scrapbook / magazine collage）插画提示词策划师。\n"
                f"任务：基于论文讲解，为 {n} 张竖版插画生成可直接用于图像模型的 prompts。\n"
                "要求：必须是实体手工剪贴簿/杂志拼贴、混合媒介、纸张纹理、撕边、胶带、便签、涂鸦箭头、手写批注、照片+图标+纸片拼贴层次、颗粒感、柔和阴影。\n"
                "每张图：用隐喻表达论文要点（问题/方法/实验结果...），不要复刻论文截图。\n"
                "安全：不要出现真实机构 logo/水印；尽量避免可读英文长句（可少量手写短词/符号）。\n"
                "输出：只输出严格 JSON 数组（不要代码块不要解释）。\n"
                f"数组长度必须为 {n}；每个元素必须包含 title, prompt, negative_prompt。\n"
                "prompt 必须显式包含 'portrait 9:16'，并写清楚画面主体与构图。\n"
                "语言：prompts 必须用中文描述画面（必要时可少量英文短词/符号）。\n"
            )

            user_prompt = (
                "请把下面的【模板 prompts】根据【讲解】进行改写与具体化，使每张图都更贴合论文内容。\n"
                "注意：模板只是结构参考，不要原样照抄；请把讲解中的关键概念融入画面隐喻。\n\n"
                f"论文标题：{title}\n"
                f"一句话：{one_liner}\n"
                + (f"讲解（最多 {explain_chars} 字）：{explain_snip}\n" if explain_snip else "")
                + "\n模板 prompts（请逐条改写）：\n"
                + json.dumps(templ, ensure_ascii=False)
            )

        last_err = None
        for attempt in range(1, 4):
            try:
                text = openai_chat(user_prompt, settings.llm_model_text, system_prompt=system_prompt)
                arr = _try_parse_json_array(text)
                if not isinstance(arr, list) or len(arr) != n:
                    raise ValueError("plan is not an N-item list")

                out: list[dict[str, str]] = []
                for i, item in enumerate(arr):
                    if not isinstance(item, dict):
                        raise ValueError("plan item is not a dict")
                    title_i = str(item.get("title") or templ[i].get("title") or f"图 {i+1}").strip()
                    prompt_i = str(item.get("prompt") or "").strip()
                    neg_i = str(item.get("negative_prompt") or "").strip()
                    if not prompt_i:
                        raise ValueError("empty prompt")
                    out.append({"title": title_i, "prompt": prompt_i, "negative_prompt": neg_i})
                return out
            except Exception as e:
                last_err = e
                print(f"WARN: PAPER_IMAGES plan LLM attempt {attempt}/3 failed, retrying: {e}")

        print(f"WARN: PAPER_IMAGES plan LLM failed; using template fallback: {last_err}")

    # fallback: templated prompts (still include a short hint)
    short_hint = hint[:420] if hint else ""
    out2: list[dict[str, str]] = []
    for i, item in enumerate(templ[:n]):
        ptxt = item["prompt"]
        if short_hint:
            ptxt = ptxt + f"\n讲解要点（用于构图隐喻，不要直接画出长文本）：{short_hint}"
        out2.append({"title": item["title"], "prompt": ptxt, "negative_prompt": item["negative_prompt"]})
    return out2


def run_paper_images_for_pending(
    session: Session, *, day: str | None = None, external_ids: list[str] | None = None
) -> None:
    """Generate magazine-collage images per paper (Phase 2), bilingual.

    - Uses PAPERTOK_LANGS=zh,en to decide which language variants to generate.
    - Stores separate image rows by (provider, lang, order_idx).
    - When lang=en, outputs under /static/gen/<external_id>/en/* (and /static/gen_glm/...).

    Provider strategy:
    - Default behavior: generate for settings.paper_images_providers.
    - If PAPER_IMAGES_GENERATE_ONLY_DISPLAY=1: only generate the current display provider
      from DB app config (seedream|glm|auto).
    """

    if not settings.run_paper_images:
        return

    # Which languages to generate
    langs = [x.strip().lower() for x in (settings.papertok_langs or ["zh"]) if x.strip()]
    langs = [x for x in langs if x in {"zh", "en"}] or ["zh"]

    # Load app-level config from DB so Admin UI changes are respected.
    app_cfg = get_effective_app_config(session)
    display = (app_cfg.paper_images_display_provider or "seedream").strip().lower()

    # Normalize providers
    providers: list[str] = []
    if getattr(settings, "paper_images_generate_only_display", False):
        # only generate the provider that FEED is configured to display
        if display in {"seedream", "glm"}:
            providers = [display]
        else:
            # auto -> fall back to env-configured generation list
            providers = []

    if not providers:
        for p0 in (settings.paper_images_providers or []):
            k = (p0 or "").strip().lower()
            if not k:
                continue
            if k in {"seedream", "ark"}:
                providers.append("seedream")
            elif k in {"glm", "glm-image", "glm_image"}:
                providers.append("glm")
            else:
                providers.append(k)

    # De-dup while preserving order
    seen = set()
    providers = [x for x in providers if not (x in seen or seen.add(x))]
    if not providers:
        providers = ["seedream"]

    enabled: list[str] = []
    for prov in providers:
        if prov == "seedream":
            if seedream_has_keys():
                enabled.append(prov)
            else:
                print("WARN: Seedream keys not found -> skip provider seedream")
        elif prov == "glm":
            if glm_image_has_keys():
                enabled.append(prov)
            else:
                print("WARN: GLM_API_KEY not found -> skip provider glm")
        else:
            print(f"WARN: unknown paper image provider: {prov} (skip)")

    if not enabled:
        print("WARN: RUN_PAPER_IMAGES=1 but no image providers have keys -> skipping")
        return

    target_n = max(1, int(settings.paper_images_per_paper))
    max_papers = max(1, int(settings.paper_images_max_papers))

    for lang0 in langs:
        stage = "paper_images_en" if lang0 == "en" else "paper_images"
        explain_col = Paper.content_explain_en if lang0 == "en" else Paper.content_explain_cn

        # Only generate images for papers that already have explanation in the target language.
        q = (
            select(Paper)
            .where(Paper.source == "hf_daily")
            .where(Paper.raw_text_path.is_not(None))
            .where(explain_col.is_not(None))
        )
        if external_ids:
            q = q.where(Paper.external_id.in_(external_ids))
        elif day:
            q = q.where(Paper.day == day)

        papers = session.exec(q.order_by(Paper.id.asc())).all()

        picked: list[Paper] = []
        for p in papers:
            need = False
            for prov in enabled:
                imgs = session.exec(
                    select(PaperImage)
                    .where(PaperImage.paper_id == p.id)
                    .where(PaperImage.kind == "generated")
                    .where(PaperImage.provider == prov)
                    .where(PaperImage.lang == lang0)
                    .where(PaperImage.enabled == True)  # noqa: E712
                    .where(PaperImage.status == "generated")
                ).all()
                if len(imgs) < target_n:
                    need = True
                    break
            if need:
                picked.append(p)
            if len(picked) >= max_papers:
                break

        if not picked:
            print(f"PAPER_IMAGES[{lang0}]: nothing to do")
            continue

        def _process_one(sess: Session, p: Paper) -> None:
            record_paper_event(sess, paper_id=p.id, stage=stage, status="started")

            one_liner_txt = (p.one_liner_en or "").strip() if lang0 == "en" else (p.one_liner or "").strip()
            if not one_liner_txt:
                # fallback to whichever exists
                one_liner_txt = (p.one_liner or p.one_liner_en or "").strip()

            explain_txt = p.content_explain_en if lang0 == "en" else p.content_explain_cn

            plan = build_paper_images_plan(
                title=p.title,
                one_liner=one_liner_txt,
                explain=explain_txt,
                n=target_n,
                lang=lang0,
            )

            paper_key = p.external_id or str(p.id)
            rel_dir = f"{paper_key}/en" if lang0 == "en" else paper_key

            for prov in enabled:
                if prov == "seedream":
                    size = settings.paper_gen_image_size
                    out_root = settings.paper_gen_images_dir
                    mount_prefix = "/static/gen"
                elif prov == "glm":
                    size = settings.paper_glm_image_size
                    out_root = settings.paper_gen_images_glm_dir
                    mount_prefix = "/static/gen_glm"
                else:
                    continue

                w, h = _parse_size(size)

                # Existing rows for this provider + lang
                existing = sess.exec(
                    select(PaperImage)
                    .where(PaperImage.paper_id == p.id)
                    .where(PaperImage.kind == "generated")
                    .where(PaperImage.provider == prov)
                    .where(PaperImage.lang == lang0)
                    .order_by(PaperImage.order_idx.asc())
                ).all()
                by_idx = {img.order_idx: img for img in existing}

                # If rows exist but were previously disabled, re-enable and force regeneration.
                for idx, ex_img in by_idx.items():
                    if idx >= target_n:
                        continue
                    if ex_img.enabled is False:
                        ex_img.enabled = True
                        ex_img.status = "planned"
                        ex_img.local_path = None
                        ex_img.url_path = None
                        ex_img.sha256 = None
                        ex_img.error = None
                        ex_img.prompt = None
                        ex_img.negative_prompt = None
                        ex_img.updated_at = datetime.utcnow()
                        sess.add(ex_img)
                sess.commit()

                # Ensure plan rows exist
                for idx in range(target_n):
                    if idx in by_idx:
                        continue
                    item = plan[idx] if idx < len(plan) else plan[-1]
                    img = PaperImage(
                        paper_id=p.id,
                        kind="generated",
                        lang=lang0,
                        provider=prov,
                        order_idx=idx,
                        status="planned",
                        enabled=True,
                        prompt=item.get("prompt"),
                        negative_prompt=item.get("negative_prompt"),
                        width=w,
                        height=h,
                        meta_json=json.dumps({"title": item.get("title")}, ensure_ascii=False),
                    )
                    sess.add(img)
                sess.commit()

                # Generate missing images
                todo = sess.exec(
                    select(PaperImage)
                    .where(PaperImage.paper_id == p.id)
                    .where(PaperImage.kind == "generated")
                    .where(PaperImage.provider == prov)
                    .where(PaperImage.lang == lang0)
                    .where(PaperImage.enabled == True)  # noqa: E712
                    .order_by(PaperImage.order_idx.asc())
                ).all()

                out_dir = Path(out_root) / rel_dir
                out_dir.mkdir(parents=True, exist_ok=True)

                for img in todo:
                    if img.order_idx >= target_n:
                        continue
                    if (
                        img.status == "generated"
                        and img.url_path
                        and img.local_path
                        and Path(img.local_path).exists()
                    ):
                        continue

                    tmp_name = f"{img.order_idx+1:02d}.tmp.png"
                    tmp_path = out_dir / tmp_name

                    try:
                        prompt = (img.prompt or "").strip()
                        if not prompt:
                            item = plan[img.order_idx]
                            img.prompt = item.get("prompt")
                            img.negative_prompt = item.get("negative_prompt")
                            prompt = (img.prompt or "").strip()

                        print(
                            f"PAPER_IMAGES[{lang0}][{prov}]: {p.external_id} [{img.order_idx+1}/{target_n}] -> generating..."
                        )

                        if prov == "seedream":
                            res = seedream_generate_image(
                                prompt=prompt,
                                size=size,
                                out_path=tmp_path,
                                negative_prompt=img.negative_prompt,
                                watermark=False,
                            )
                            sha = res.sha256
                            remote_url = res.remote_url
                            local_path = res.local_path
                        else:
                            # GLM-Image does not support negative_prompt; ignore it.
                            res2 = glm_image_generate(
                                prompt=prompt,
                                size=size,
                                out_path=tmp_path,
                                watermark=False,
                            )
                            sha = res2.sha256
                            remote_url = res2.remote_url
                            local_path = res2.local_path

                        # Use content-hash in filename to bust browser/SW caches.
                        final_name = f"{img.order_idx+1:02d}-{sha[:8]}.png"
                        final_path = out_dir / final_name
                        try:
                            if final_path.exists():
                                final_path.unlink()
                            local_path.rename(final_path)
                        except Exception:
                            final_path = local_path
                            final_name = tmp_name

                        img.local_path = str(final_path)
                        img.url_path = f"{mount_prefix}/{rel_dir}/{final_name}"
                        img.sha256 = sha
                        img.status = "generated"
                        img.error = None
                        img.updated_at = datetime.utcnow()

                        # Add remote_url into meta_json (best-effort)
                        try:
                            meta = json.loads(img.meta_json) if img.meta_json else {}
                            if not isinstance(meta, dict):
                                meta = {}
                        except Exception:
                            meta = {}
                        meta["remote_url"] = remote_url
                        img.meta_json = json.dumps(meta, ensure_ascii=False)

                        sess.add(img)
                        sess.commit()
                        print(f"PAPER_IMAGES_OK[{lang0}][{prov}]: {p.external_id} -> {img.url_path}")
                    except Exception as e:
                        img.status = "failed"
                        img.error = str(e)[:500]
                        img.updated_at = datetime.utcnow()
                        sess.add(img)
                        sess.commit()
                        print(
                            f"WARN: PAPER_IMAGES failed[{lang0}][{prov}] for {p.external_id} idx={img.order_idx}: {e}"
                        )

            # Per-paper summary event (success if all providers reached target_n without failures).
            try:
                summary = {}
                any_failed = False
                for prov in enabled:
                    rows2 = sess.exec(
                        select(PaperImage)
                        .where(PaperImage.paper_id == p.id)
                        .where(PaperImage.kind == "generated")
                        .where(PaperImage.provider == prov)
                        .where(PaperImage.lang == lang0)
                        .where(PaperImage.enabled == True)
                    ).all()
                    gen = sum(1 for r in rows2 if r.status == "generated")
                    fail = sum(1 for r in rows2 if r.status == "failed")
                    summary[prov] = {"generated": gen, "failed": fail}
                    if fail > 0 or gen < target_n:
                        any_failed = True
                record_paper_event(
                    sess,
                    paper_id=p.id,
                    stage=stage,
                    status="failed" if any_failed else "success",
                    error="some images failed or missing" if any_failed else None,
                    meta={"providers": summary, "target_n": target_n},
                )
            except Exception:
                pass
        conc = int(getattr(settings, "paper_images_concurrency", 1) or 1)
        conc = max(1, min(conc, 16))
        if conc <= 1 or len(picked) <= 1:
            for p in picked:
                _process_one(session, p)
        else:
            print(f"PAPER_IMAGES[{lang0}]: concurrency={conc} papers={len(picked)} providers={enabled}")
            ids = [int(p.id) for p in picked]
            def _worker(pid: int) -> None:
                with Session(engine) as sess2:
                    p2 = sess2.get(Paper, pid)
                    if not p2:
                        return
                    _process_one(sess2, p2)
            with ThreadPoolExecutor(max_workers=conc) as ex:
                futs = [ex.submit(_worker, pid) for pid in ids]
                for fut in as_completed(futs):
                    try:
                        fut.result()
                    except Exception as e:
                        print(f"WARN: PAPER_IMAGES worker failed: {e}")




def upsert_paper(session: Session, item: dict[str, Any], *, day: str | None) -> Paper:
    # The HF daily_papers object shape may evolve; store raw JSON too.
    paper_obj = item.get("paper", {}) or {}

    title = paper_obj.get("title") or item.get("title") or ""
    external_id = paper_obj.get("id") or item.get("id") or title

    # Prefer HF paper page; fall back to arXiv abs
    url = item.get("url") or paper_obj.get("url")
    if not url and external_id:
        url = f"https://huggingface.co/papers/{external_id}"

    thumbnail_url = item.get("thumbnail") or paper_obj.get("thumbnail")

    existing = session.exec(
        select(Paper).where(
            Paper.source == "hf_daily", Paper.external_id == str(external_id)
        )
    ).first()

    if existing:
        p = existing
        p.title = title or p.title
        p.url = url or p.url
        p.thumbnail_url = thumbnail_url or p.thumbnail_url
        if day:
            p.day = day
        p.meta_json = json.dumps(item, ensure_ascii=False)
        p.updated_at = datetime.utcnow()
        return p

    p = Paper(
        source="hf_daily",
        external_id=str(external_id),
        day=day,
        title=title,
        url=url,
        thumbnail_url=thumbnail_url,
        meta_json=json.dumps(item, ensure_ascii=False),
    )
    session.add(p)
    return p


def main():
    init_db()

    # Optional override for backfills: HF_DATE=YYYY-MM-DD
    date = (os.getenv("HF_DATE") or "").strip() or datetime.now().strftime("%Y-%m-%d")

    effective_date = date

    items: list[dict[str, Any]] = []
    if settings.hf_top_n > 0:
        effective_date, items = fetch_hf_daily(date)
    else:
        print("HF_TOP_N=0 -> skipping HuggingFace fetch")

    with Session(engine) as session:
        active_external_ids: set[str] = set()

        for item in items:
            p = upsert_paper(session, item, day=effective_date)

            # Ensure p.id is available before writing paper_events.
            session.add(p)
            session.commit()
            session.refresh(p)

            if p.external_id:
                active_external_ids.add(str(p.external_id))

            if settings.download_pdf and p.external_id:
                try:
                    record_paper_event(session, paper_id=p.id, stage="pdf", status="started")
                    pdf_url, pdf_path, pdf_sha = download_pdf(p.external_id)
                    p.pdf_url = pdf_url
                    p.pdf_path = pdf_path
                    if pdf_sha:
                        p.pdf_sha256 = pdf_sha
                    p.updated_at = datetime.utcnow()
                    session.add(p)
                    session.commit()
                    record_paper_event(
                        session,
                        paper_id=p.id,
                        stage="pdf",
                        status="success",
                        meta={"pdf_path": pdf_path},
                    )
                except Exception as e:
                    record_paper_event(
                        session,
                        paper_id=p.id,
                        stage="pdf",
                        status="failed",
                        error=str(e),
                    )
                    print(f"WARN: failed to download PDF for {p.external_id}: {e}")

        session.commit()

        # Note: we do NOT clear old days. Daily job only *processes* the fetched Top10,
        # while the feed can show full history.

        # When fetching HF daily papers (HF_TOP_N>0), we scope the heavy pipeline to the fetched day.
        active_day = effective_date if settings.hf_top_n > 0 else None
        active_ids = sorted(active_external_ids) if settings.hf_top_n > 0 else None

        # Optional: PDF -> markdown + images via mineru (heavy, controlled by env flags).
        run_mineru_for_pending(session, day=active_day, external_ids=active_ids)

        # Optional: markdown -> Chinese teaching-style explanation (LLM)
        run_content_analysis_for_pending(session, day=active_day, external_ids=active_ids)

        # Optional: MinerU images -> captions (VLM)
        run_image_caption_for_pending(session, day=active_day, external_ids=active_ids)

        # Optional: generated illustrations (Seedream / GLM-Image)
        run_paper_images_for_pending(session, day=active_day, external_ids=active_ids)

        # `SKIP_LLM` historically only meant: skip the *one-liner* stage.
        # We keep that behavior for existing ops scripts, but allow running one-liners
        # in isolation via RUN_ONE_LINER=1.
        if settings.skip_llm and not settings.run_one_liner:
            print("SKIP_LLM=1 -> ingest done; skipping one-liner generation")
            return

        if not settings.openai_api_key:
            raise SystemExit(
                "OPENAI_API_KEY is empty. Put it in papertok/.env (do NOT commit)."
            )

        langs = [x.strip().lower() for x in (settings.papertok_langs or ["zh"]) if x.strip()]
        langs = [x for x in langs if x in {"zh", "en"}] or ["zh"]

        # generate one-liners for those missing (or rewrite from MinerU if enabled)
        if settings.rewrite_one_liner_from_mineru:
            from datetime import timedelta

            cutoff = datetime.utcnow() - timedelta(minutes=int(settings.rewrite_one_liner_skip_recent_minutes))
            q = (
                select(Paper)
                .where(Paper.source == "hf_daily")
                .where(Paper.raw_text_path.is_not(None))
                .where(Paper.updated_at < cutoff)
            )
            if active_ids:
                q = q.where(Paper.external_id.in_(active_ids))
            elif active_day:
                q = q.where(Paper.day == active_day)

            rows = session.exec(q.order_by(Paper.id.asc()).limit(int(settings.rewrite_one_liner_max))).all()
            print(
                "ONE_LINER: rewrite enabled -> "
                f"candidates={len(rows)} cutoff_utc={cutoff.isoformat()} langs={langs}"
            )
        else:
            need = []
            if "zh" in langs:
                need.append(Paper.one_liner.is_(None))
            if "en" in langs:
                need.append(Paper.one_liner_en.is_(None))

            q = select(Paper).where(Paper.source == "hf_daily").where(or_(*need))
            if active_ids:
                q = q.where(Paper.external_id.in_(active_ids))
            elif active_day:
                q = q.where(Paper.day == active_day)

            rows = session.exec(q.order_by(Paper.id.asc()).limit(int(settings.one_liner_max))).all()

        for p in rows:
            meta = json.loads(p.meta_json) if p.meta_json else {}
            hf_abstract = (
                meta.get("paper", {}).get("summary")
                or meta.get("paper", {}).get("abstract")
                or meta.get("summary")
                or meta.get("abstract")
            )

            mineru_abstract = None
            if settings.one_liner_prefer_mineru and p.raw_text_path:
                try:
                    md_path = Path(p.raw_text_path)
                    if md_path.exists():
                        md_text = md_path.read_text(encoding="utf-8", errors="ignore")
                        md_text = md_text[: int(settings.one_liner_mineru_input_chars)]
                        mineru_abstract = _extract_abstract_from_mineru_markdown(md_text)
                except Exception:
                    mineru_abstract = None

            abstract = mineru_abstract or (hf_abstract if isinstance(hf_abstract, str) else None)

            changed = False
            if "zh" in langs and (settings.rewrite_one_liner_from_mineru or p.one_liner is None):
                p.one_liner = build_one_liner(p.title, abstract, lang="zh")
                changed = True

            if "en" in langs and (p.one_liner_en is None):
                p.one_liner_en = build_one_liner(p.title, abstract, lang="en")
                changed = True

            if changed:
                p.display_title = p.display_title or p.title
                p.updated_at = datetime.utcnow()
                session.add(p)
                session.commit()

                msg = f"ONE_LINER_OK: {p.external_id}"
                if "zh" in langs:
                    msg += f" zh={((p.one_liner or '')[:60]).strip()}"
                if "en" in langs:
                    msg += f" en={((p.one_liner_en or '')[:60]).strip()}"
                print(msg)


if __name__ == "__main__":
    main()
