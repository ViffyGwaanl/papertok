from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Index


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: Optional[int] = Field(default=None, primary_key=True)

    job_type: str = Field(index=True)
    status: str = Field(default="queued", index=True)  # queued|running|success|failed|canceled

    payload_json: Optional[str] = None
    result_json: Optional[str] = None

    log_path: Optional[str] = None
    error: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    started_at: Optional[datetime] = Field(default=None, index=True)
    finished_at: Optional[datetime] = Field(default=None, index=True)


Index("idx_jobs_type_status_created", Job.job_type, Job.status, Job.created_at)
