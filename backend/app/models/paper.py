from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Index


class Paper(SQLModel, table=True):
    __tablename__ = "papers"

    id: Optional[int] = Field(default=None, primary_key=True)

    # source identifiers
    source: str = Field(index=True)  # e.g. 'hf_daily'
    external_id: str = Field(index=True)  # e.g. arXiv id

    # For hf_daily: YYYY-MM-DD (used to scope the feed to the latest day)
    day: Optional[str] = Field(default=None, index=True)

    title: str
    url: Optional[str] = None  # canonical paper url (arxiv/hf)

    # card fields
    display_title: Optional[str] = None

    # One-liner summaries
    # - legacy field `one_liner` is treated as Chinese (zh)
    one_liner: Optional[str] = None  # zh (legacy)
    one_liner_en: Optional[str] = None  # en

    golden_line: Optional[str] = None

    thumbnail_url: Optional[str] = None

    # raw material
    pdf_url: Optional[str] = None
    pdf_path: Optional[str] = None
    pdf_sha256: Optional[str] = None

    raw_text_path: Optional[str] = None  # mineru/md output path etc.

    # LLM-generated longform explanation based on parsed paper content (optional)
    content_explain_cn: Optional[str] = None  # zh
    content_explain_en: Optional[str] = None  # en

    # Optional: image -> caption mapping (JSON). Keys are relative URLs from /api/papers/{id} images[].
    image_captions_json: Optional[str] = None  # zh
    image_captions_en_json: Optional[str] = None  # en

    # EPUB artifacts (stored under EPUB_OUT_ROOT and served via /static/epub)
    epub_path_en: Optional[str] = None
    epub_url_en: Optional[str] = None
    # Future: translated / bilingual editions (next PR)
    epub_path_zh: Optional[str] = None
    epub_url_zh: Optional[str] = None
    epub_path_bilingual: Optional[str] = None
    epub_url_bilingual: Optional[str] = None

    meta_json: Optional[str] = None

    content_sha256: Optional[str] = Field(default=None, index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


Index("idx_papers_source_external", Paper.source, Paper.external_id, unique=True)
