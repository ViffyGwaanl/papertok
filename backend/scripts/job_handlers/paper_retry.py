from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from app.db.init_db import init_db
from app.db.engine import engine
from app.models.paper import Paper
from app.core.config import settings
from app.services.paper_events import record_paper_event

# Reuse pipeline functions
from scripts.daily_run import (
    download_pdf,
    run_mineru_for_pending,
    run_content_analysis_for_pending,
    run_image_caption_for_pending,
    run_paper_images_for_pending,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-type", required=True)
    ap.add_argument("--payload", required=True)
    args = ap.parse_args()

    payload_path = Path(args.payload)
    payload: dict = {}
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8")) or {}
    except Exception:
        payload = {}

    external_id = str(payload.get("external_id") or "").strip()
    stage = str(payload.get("stage") or "").strip().lower()

    if not external_id:
        raise SystemExit("payload.external_id is required")
    if stage not in {"pdf", "mineru", "explain", "caption", "paper_images"}:
        raise SystemExit("payload.stage must be one of: pdf|mineru|explain|caption|paper_images")

    # Optional overrides
    if "image_caption_max" in payload:
        try:
            settings.image_caption_max = int(payload["image_caption_max"])
        except Exception:
            pass
    if "image_caption_per_paper" in payload:
        try:
            settings.image_caption_per_paper = int(payload["image_caption_per_paper"])
        except Exception:
            pass

    init_db()

    with Session(engine) as session:
        p = session.exec(select(Paper).where(Paper.external_id == external_id)).first()
        if not p:
            raise SystemExit(f"paper not found: {external_id}")

        print(f"RETRY_START: {external_id} stage={stage} at {datetime.now().isoformat(timespec='seconds')}")

        if stage == "pdf":
            record_paper_event(session, paper_id=p.id, stage="pdf", status="started")
            try:
                pdf_url, pdf_path, pdf_sha = download_pdf(external_id)
                p.pdf_url = pdf_url
                p.pdf_path = pdf_path
                if pdf_sha:
                    p.pdf_sha256 = pdf_sha
                p.updated_at = datetime.utcnow()
                session.add(p)
                session.commit()
                record_paper_event(session, paper_id=p.id, stage="pdf", status="success", meta={"pdf_path": pdf_path})
                print(f"RETRY_OK: pdf -> {pdf_path}")
                return
            except Exception as e:
                record_paper_event(session, paper_id=p.id, stage="pdf", status="failed", error=str(e))
                raise

        if stage == "mineru":
            if not p.pdf_path:
                record_paper_event(session, paper_id=p.id, stage="mineru", status="skipped", error="missing pdf_path")
                print("RETRY_SKIP: mineru (missing pdf_path)")
                return

            # Force this run
            settings.run_mineru = True
            settings.mineru_max = 1
            run_mineru_for_pending(session, external_ids=[external_id])
            # If still missing, record a skipped marker for visibility
            session.refresh(p)
            if not p.raw_text_path:
                record_paper_event(session, paper_id=p.id, stage="mineru", status="skipped", error="mineru did not produce raw_text_path")
            return

        if stage == "explain":
            if not p.raw_text_path:
                record_paper_event(session, paper_id=p.id, stage="explain", status="skipped", error="missing raw_text_path")
                print("RETRY_SKIP: explain (missing raw_text_path)")
                return

            settings.run_content_analysis = True
            settings.content_analysis_max = 1
            run_content_analysis_for_pending(session, external_ids=[external_id])
            session.refresh(p)
            if not p.content_explain_cn:
                record_paper_event(session, paper_id=p.id, stage="explain", status="skipped", error="explain not generated")
            return

        if stage == "caption":
            if not p.raw_text_path:
                record_paper_event(session, paper_id=p.id, stage="caption", status="skipped", error="missing raw_text_path")
                print("RETRY_SKIP: caption (missing raw_text_path)")
                return

            settings.run_image_caption = True
            run_image_caption_for_pending(session, external_ids=[external_id])
            session.refresh(p)
            if not p.image_captions_json:
                record_paper_event(session, paper_id=p.id, stage="caption", status="skipped", error="no captions generated")
            return

        if stage == "paper_images":
            if not p.raw_text_path or not p.content_explain_cn:
                record_paper_event(
                    session,
                    paper_id=p.id,
                    stage="paper_images",
                    status="skipped",
                    error="missing raw_text_path or content_explain_cn",
                )
                print("RETRY_SKIP: paper_images (missing prerequisites)")
                return

            settings.run_paper_images = True
            settings.paper_images_max_papers = 1
            run_paper_images_for_pending(session, external_ids=[external_id])
            return


if __name__ == "__main__":
    main()
