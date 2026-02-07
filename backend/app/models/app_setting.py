from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Index


class AppSetting(SQLModel, table=True):
    __tablename__ = "app_settings"

    id: Optional[int] = Field(default=None, primary_key=True)

    # e.g. "app_config"
    key: str = Field(index=True)

    # JSON string (object/scalar). Keep as TEXT for SQLite simplicity.
    value_json: str = Field(default="{}")

    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


Index("idx_app_settings_key", AppSetting.key, unique=True)
