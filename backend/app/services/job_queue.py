from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlmodel import Session, select

from app.models.job import Job


def enqueue_job(session: Session, *, job_type: str, payload: dict[str, Any] | None = None) -> Job:
    j = Job(
        job_type=job_type,
        status="queued",
        payload_json=json.dumps(payload or {}, ensure_ascii=False),
        updated_at=datetime.utcnow(),
    )
    session.add(j)
    session.commit()
    session.refresh(j)
    return j


def list_jobs(session: Session, *, limit: int = 50) -> list[Job]:
    limit = max(1, min(int(limit or 50), 200))
    return session.exec(select(Job).order_by(Job.id.desc()).limit(limit)).all()


def get_job(session: Session, job_id: int) -> Optional[Job]:
    return session.get(Job, job_id)
