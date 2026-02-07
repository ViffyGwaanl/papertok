from __future__ import annotations

import json
from datetime import datetime

from sqlmodel import Session, select
from sqlalchemy import func

from app.db.init_db import init_db
from app.db.engine import engine
from app.models.paper import Paper
from app.models.paper_event import PaperEvent
from app.models.paper_image import PaperImage
from app.services.paper_events import record_paper_event


STAGES = ["pdf", "mineru", "explain", "caption", "paper_images"]


def _has_any_event(session: Session, *, paper_id: int, stage: str) -> bool:
    n = session.exec(
        select(func.count(PaperEvent.id))
        .where(PaperEvent.paper_id == paper_id)
        .where(PaperEvent.stage == stage)
    ).one()
    return int(n or 0) > 0


def main():
    init_db()

    now = datetime.now().isoformat(timespec="seconds")
    added = 0

    with Session(engine) as session:
        papers = session.exec(select(Paper).where(Paper.source == "hf_daily")).all()

        for p in papers:
            # pdf
            if not _has_any_event(session, paper_id=p.id, stage="pdf"):
                if p.pdf_path:
                    record_paper_event(session, paper_id=p.id, stage="pdf", status="success", meta={"backfill": True, "at": now})
                else:
                    record_paper_event(session, paper_id=p.id, stage="pdf", status="skipped", error="missing pdf_path", meta={"backfill": True, "at": now})
                added += 1

            # mineru
            if not _has_any_event(session, paper_id=p.id, stage="mineru"):
                if p.raw_text_path:
                    record_paper_event(session, paper_id=p.id, stage="mineru", status="success", meta={"backfill": True, "at": now})
                else:
                    reason = "missing pdf_path" if not p.pdf_path else "not parsed yet"
                    record_paper_event(session, paper_id=p.id, stage="mineru", status="skipped", error=reason, meta={"backfill": True, "at": now})
                added += 1

            # explain
            if not _has_any_event(session, paper_id=p.id, stage="explain"):
                if p.content_explain_cn:
                    record_paper_event(session, paper_id=p.id, stage="explain", status="success", meta={"backfill": True, "at": now})
                else:
                    reason = "missing raw_text_path" if not p.raw_text_path else "not generated yet"
                    record_paper_event(session, paper_id=p.id, stage="explain", status="skipped", error=reason, meta={"backfill": True, "at": now})
                added += 1

            # caption
            if not _has_any_event(session, paper_id=p.id, stage="caption"):
                if p.image_captions_json:
                    record_paper_event(session, paper_id=p.id, stage="caption", status="success", meta={"backfill": True, "at": now})
                else:
                    reason = "missing raw_text_path" if not p.raw_text_path else "not generated yet"
                    record_paper_event(session, paper_id=p.id, stage="caption", status="skipped", error=reason, meta={"backfill": True, "at": now})
                added += 1

            # paper_images
            if not _has_any_event(session, paper_id=p.id, stage="paper_images"):
                if not p.raw_text_path or not p.content_explain_cn:
                    record_paper_event(session, paper_id=p.id, stage="paper_images", status="skipped", error="missing prerequisites", meta={"backfill": True, "at": now})
                    added += 1
                else:
                    # Check enabled generated images counts per provider
                    rows = session.exec(
                        select(PaperImage.provider, func.count(PaperImage.id))
                        .where(PaperImage.paper_id == p.id)
                        .where(PaperImage.kind == "generated")
                        .where(PaperImage.enabled == True)  # noqa: E712
                        .where(PaperImage.status == "generated")
                        .group_by(PaperImage.provider)
                    ).all()
                    byp = {prov: int(n or 0) for (prov, n) in rows}
                    ok = (byp.get("seedream", 0) >= 3) and (byp.get("glm", 0) >= 3)
                    if ok:
                        record_paper_event(session, paper_id=p.id, stage="paper_images", status="success", meta={"backfill": True, "at": now, "by_provider": byp})
                    else:
                        record_paper_event(session, paper_id=p.id, stage="paper_images", status="skipped", error="not generated yet", meta={"backfill": True, "at": now, "by_provider": byp})
                    added += 1

    print(f"BACKFILL_DONE: added_events={added}")


if __name__ == "__main__":
    main()
