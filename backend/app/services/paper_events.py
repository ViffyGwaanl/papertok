from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from sqlmodel import Session

from app.models.paper_event import PaperEvent


def record_paper_event(
    session: Session,
    *,
    paper_id: int,
    stage: str,
    status: str,
    error: str | None = None,
    meta: dict[str, Any] | None = None,
    log_path: str | None = None,
) -> PaperEvent:
    if not log_path:
        log_path = (os.getenv("PAPERTOK_LOG_PATH") or "").strip() or None

    e = PaperEvent(
        paper_id=paper_id,
        stage=str(stage),
        status=str(status),
        error=(error[:2000] if isinstance(error, str) else None),
        meta_json=(json.dumps(meta, ensure_ascii=False) if isinstance(meta, dict) else None),
        log_path=log_path,
        created_at=datetime.utcnow(),
    )
    session.add(e)
    session.commit()
    session.refresh(e)
    return e
