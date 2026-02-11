from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Index


class PaperImage(SQLModel, table=True):
    __tablename__ = "paper_images"

    id: Optional[int] = Field(default=None, primary_key=True)

    paper_id: int = Field(index=True, foreign_key="papers.id")

    # e.g. "generated" | "mineru_extracted" (we only use generated for now)
    kind: str = Field(default="generated", index=True)

    # language variant for the generated asset: zh|en
    lang: str = Field(default="zh", index=True)

    provider: str = Field(default="seedream", index=True)

    order_idx: int = Field(default=0, index=True)

    status: str = Field(default="planned", index=True)  # planned|generated|failed
    enabled: bool = Field(default=True, index=True)

    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None

    width: Optional[int] = None
    height: Optional[int] = None

    url_path: Optional[str] = None  # e.g. /static/gen/<external_id>/01.webp
    local_path: Optional[str] = None
    sha256: Optional[str] = Field(default=None, index=True)

    error: Optional[str] = None
    meta_json: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


Index(
    "idx_paper_images_paper_kind_provider_lang_order",
    PaperImage.paper_id,
    PaperImage.kind,
    PaperImage.provider,
    PaperImage.lang,
    PaperImage.order_idx,
    unique=True,
)
