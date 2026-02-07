from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Index


class PaperEvent(SQLModel, table=True):
    __tablename__ = "paper_events"

    id: Optional[int] = Field(default=None, primary_key=True)

    paper_id: int = Field(index=True, foreign_key="papers.id")

    # e.g. pdf|mineru|explain|caption|paper_images
    stage: str = Field(index=True)

    # started|success|failed
    status: str = Field(index=True)

    error: Optional[str] = None
    meta_json: Optional[str] = None

    # Optional: point to the launchd / job log that contains full details
    log_path: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


Index("idx_paper_events_paper_stage_created", PaperEvent.paper_id, PaperEvent.stage, PaperEvent.created_at)
