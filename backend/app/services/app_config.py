from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.config import settings
from app.models.app_setting import AppSetting


APP_CONFIG_KEY = "app_config"


class AppConfig(BaseModel):
    """App-level (product/ops) config.

    This is intentionally separate from .env System config (keys, paths, binding).
    Stored in DB so Admin UI changes are picked up consistently by both:
    - FastAPI server (request-time)
    - background scripts (job start-time)
    """

    # Feed gating: if true, hide papers that are not fully processed yet.
    feed_require_explain: bool = Field(
        default=True,
        description="Only show papers with content_explain_cn in the feed",
    )

    feed_require_image_captions: bool = Field(
        default=True,
        description="Only show papers with image_captions_json in the feed",
    )

    feed_require_generated_images: bool = Field(
        default=True,
        description="Only show papers that have at least one generated PaperImage (any provider)",
    )

    paper_images_display_provider: str = Field(
        default="seedream",
        description="Primary provider ordering for generated images: seedream|glm|auto",
    )

    image_caption_context_chars: int = Field(
        default=2000,
        description="Context length (chars) extracted from MinerU markdown around the image reference",
    )
    image_caption_context_strategy: str = Field(
        default="merge",
        description="How to handle multiple references of the same image in markdown: merge|last",
    )
    image_caption_context_occurrences: int = Field(
        default=3,
        description="Max occurrences to merge when strategy=merge",
    )

    # Pipeline toggles: keep env-only for now (RUN_*) to avoid surprise.


def default_app_config() -> AppConfig:
    """Defaults: derive from current Settings (env + code defaults)."""
    return AppConfig(
        feed_require_explain=True,
        feed_require_image_captions=True,
        feed_require_generated_images=True,
        paper_images_display_provider=(settings.paper_images_display_provider or "seedream"),
        image_caption_context_chars=int(getattr(settings, "image_caption_context_chars", 2000)),
        image_caption_context_strategy=str(getattr(settings, "image_caption_context_strategy", "merge")),
        image_caption_context_occurrences=int(getattr(settings, "image_caption_context_occurrences", 3)),
    )


def _safe_parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return None


def get_db_app_config(session: Session) -> Dict[str, Any]:
    row = session.exec(select(AppSetting).where(AppSetting.key == APP_CONFIG_KEY)).first()
    if not row or not row.value_json:
        return {}
    v = _safe_parse_json(row.value_json)
    if isinstance(v, dict):
        return v
    return {}


def set_db_app_config(session: Session, patch: Dict[str, Any]) -> Dict[str, Any]:
    """Merge patch into existing config and persist."""

    cur = get_db_app_config(session)
    merged = {**cur, **patch}

    # Validate by constructing AppConfig
    cfg = default_app_config().model_copy(update=merged)

    row = session.exec(select(AppSetting).where(AppSetting.key == APP_CONFIG_KEY)).first()
    if not row:
        row = AppSetting(key=APP_CONFIG_KEY, value_json="{}")

    row.value_json = json.dumps(cfg.model_dump(), ensure_ascii=False)
    row.updated_at = datetime.utcnow()

    session.add(row)
    session.commit()
    session.refresh(row)

    return cfg.model_dump()


def get_effective_app_config(session: Session) -> AppConfig:
    base = default_app_config()
    db_cfg = get_db_app_config(session)

    effective = base.model_copy(update=db_cfg)

    # Normalize / clamp
    effective.paper_images_display_provider = (
        effective.paper_images_display_provider or "seedream"
    ).strip().lower()
    if effective.paper_images_display_provider not in {"seedream", "glm", "auto"}:
        effective.paper_images_display_provider = "seedream"

    effective.image_caption_context_strategy = (
        effective.image_caption_context_strategy or "merge"
    ).strip().lower()
    if effective.image_caption_context_strategy not in {"merge", "last"}:
        effective.image_caption_context_strategy = "merge"

    effective.image_caption_context_chars = max(200, int(effective.image_caption_context_chars or 2000))
    effective.image_caption_context_occurrences = max(1, int(effective.image_caption_context_occurrences or 3))

    # Feed gating
    effective.feed_require_explain = bool(effective.feed_require_explain)
    effective.feed_require_image_captions = bool(effective.feed_require_image_captions)
    effective.feed_require_generated_images = bool(effective.feed_require_generated_images)

    return effective
