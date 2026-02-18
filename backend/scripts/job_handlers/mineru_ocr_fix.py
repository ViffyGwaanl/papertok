from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from app.core.config import settings
from app.db.init_db import init_db
from app.db.engine import engine
from app.models.paper import Paper
from app.services.paper_events import record_paper_event


def _latest_day(session: Session) -> str | None:
    return session.exec(
        select(Paper.day)
        .where(Paper.source == "hf_daily")
        .where(Paper.day.is_not(None))
        .order_by(Paper.day.desc())
        .limit(1)
    ).first()


def _parse_external_ids(s: str | None) -> list[str] | None:
    if not s:
        return None
    arr = [x.strip() for x in s.replace("\n", ",").split(",")]
    arr = [x for x in arr if x]
    return arr or None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--job-type",
        required=True,
        help="mineru_ocr_fix_scoped|mineru_ocr_fix_regen_scoped",
    )
    ap.add_argument("--payload", required=True, help="path to payload json")
    args = ap.parse_args()

    job_type = str(args.job_type)
    payload_path = Path(args.payload)

    payload: dict = {}
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8")) or {}
    except Exception:
        payload = {}

    day = payload.get("day")
    if isinstance(day, str):
        day = day.strip()
    else:
        day = None

    external_ids = payload.get("external_ids")
    if isinstance(external_ids, list):
        external_ids = [str(x).strip() for x in external_ids if str(x).strip()]
        if not external_ids:
            external_ids = None
    elif isinstance(external_ids, str):
        external_ids = _parse_external_ids(external_ids)
    else:
        external_ids = None

    regen_epub = bool(payload.get("regen_epub") or payload.get("also_regen_epub"))

    # thresholds (overrideable)
    qmarks_threshold = int(payload.get("qmarks_threshold") or settings.mineru_ocr_qmarks_threshold or 80)
    qmarks_per_k_threshold = float(
        payload.get("qmarks_per_k_threshold")
        or settings.mineru_ocr_qmarks_per_k_threshold
        or 1.0
    )

    # max papers (safety)
    max_n = int(payload.get("max_n") or 200)
    max_n = max(1, min(max_n, 2000))

    overwrite = job_type == "mineru_ocr_fix_regen_scoped" or bool(payload.get("overwrite") or payload.get("force"))

    init_db()

    with Session(engine) as session:
        if day == "latest":
            day = _latest_day(session)

        q = (
            select(Paper)
            .where(Paper.source == "hf_daily")
            .where(Paper.pdf_path.is_not(None))
            .where(Paper.raw_text_path.is_not(None))
        )
        if external_ids:
            q = q.where(Paper.external_id.in_(external_ids))
        elif day:
            q = q.where(Paper.day == day)

        rows = session.exec(q.order_by(Paper.id.asc()).limit(max_n)).all()

        print(
            "MINERU_OCR_FIX_START: "
            f"type={job_type} day={day} external_ids={len(external_ids) if external_ids else 0} "
            f"candidates={len(rows)} max_n={max_n} overwrite={overwrite} regen_epub={regen_epub} "
            f"qmarks_threshold={qmarks_threshold} qmarks_per_k_threshold={qmarks_per_k_threshold}"
        )

        from app.services.mineru_runner import run_mineru_pdf_to_md, MineruResult
        from app.services.mineru_quality import measure_md_quality, is_garbled
        from app.services.mineru_fallback import merge_mineru_outputs

        fixed: list[str] = []

        for p in rows:
            eid = (p.external_id or "").strip() or str(p.id)
            try:
                md_path = Path(str(p.raw_text_path))
                if not md_path.exists():
                    print(f"MINERU_OCR_FIX_SKIP: {eid} reason=md_missing path={md_path}")
                    continue

                q0 = measure_md_quality(md_path)
                bad = is_garbled(
                    q0,
                    qmarks_threshold=qmarks_threshold,
                    qmarks_per_k_threshold=qmarks_per_k_threshold,
                )
                if (not overwrite) and (not bad):
                    print(f"MINERU_OCR_FIX_SKIP: {eid} qmarks={q0.qmarks} per_k={q0.qmarks_per_k:.2f}")
                    continue

                record_paper_event(
                    session,
                    paper_id=p.id,
                    stage="mineru_ocr_fix",
                    status="started",
                    meta={
                        "qmarks": q0.qmarks,
                        "qmarks_per_k": q0.qmarks_per_k,
                        "qruns": q0.qruns,
                        "max_run": q0.max_run,
                    },
                )

                # Run OCR parse into separate output dir: <out_root>/<eid>/ocr/
                ocr_res = run_mineru_pdf_to_md(
                    pdf_path=str(p.pdf_path),
                    out_root=settings.mineru_out_root,
                    model_source=settings.mineru_model_source,
                    backend="pipeline",
                    method="ocr",
                    lang="en",
                    formula=False,
                    table=False,
                )

                # Merge OCR into the existing txt output for stable URLs.
                # dst is inferred from current md path's directory.
                txt_dir = md_path.parent
                dst = MineruResult(
                    out_dir=txt_dir,
                    md_path=txt_dir / f"{eid}.md",
                    images_dir=txt_dir / "images",
                )

                merged = merge_mineru_outputs(dst=dst, src=ocr_res)

                q1 = measure_md_quality(dst.md_path)
                record_paper_event(
                    session,
                    paper_id=p.id,
                    stage="mineru_ocr_fix",
                    status="success",
                    meta={
                        "before": {
                            "qmarks": q0.qmarks,
                            "qmarks_per_k": q0.qmarks_per_k,
                            "qruns": q0.qruns,
                            "max_run": q0.max_run,
                        },
                        "after": {
                            "qmarks": q1.qmarks,
                            "qmarks_per_k": q1.qmarks_per_k,
                            "qruns": q1.qruns,
                            "max_run": q1.max_run,
                        },
                        "merged": merged,
                        "ocr_md_path": str(ocr_res.md_path),
                    },
                )

                p.raw_text_path = str(dst.md_path)
                p.updated_at = datetime.utcnow()
                session.add(p)
                session.commit()

                fixed.append(eid)
                print(
                    f"MINERU_OCR_FIX_OK: {eid} qmarks {q0.qmarks}->{q1.qmarks} "
                    f"copied_images={merged.get('copied_images')}"
                )

            except Exception as e:
                record_paper_event(
                    session,
                    paper_id=p.id,
                    stage="mineru_ocr_fix",
                    status="failed",
                    error=str(e),
                )
                print(f"MINERU_OCR_FIX_FAIL: {eid} err={e}")

        if regen_epub and fixed:
            try:
                from app.services.epub_builder import build_epubs_for_pending

                print(f"MINERU_OCR_FIX_REGEN_EPUB: papers={len(fixed)}")
                build_epubs_for_pending(
                    session,
                    external_ids=fixed,
                    langs=["en"],
                    max_n=len(fixed),
                    overwrite=True,
                )
            except Exception as e:
                print(f"WARN: MINERU_OCR_FIX_REGEN_EPUB failed: {e}")

        print(
            f"MINERU_OCR_FIX_DONE: fixed={len(fixed)} candidates={len(rows)} at={datetime.now().isoformat(timespec='seconds')}"
        )


if __name__ == "__main__":
    main()
