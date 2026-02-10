"""Backfill papers.day for legacy rows.

Early ingestions happened before we consistently set Paper.day.
This script fills day for hf_daily rows where day IS NULL, using created_at
(assumed to be UTC) converted to Asia/Shanghai local date.

Run:
  PYTHONPATH=backend .venv/bin/python -m scripts.backfill_paper_day
"""

from __future__ import annotations

from datetime import UTC
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.db.engine import engine
from app.models.paper import Paper


TZ = ZoneInfo("Asia/Shanghai")


def main() -> None:
    with Session(engine) as session:
        rows = session.exec(
            select(Paper)
            .where(Paper.source == "hf_daily")
            .where(Paper.day.is_(None))
            .order_by(Paper.created_at.asc())
        ).all()

        print(f"candidates: {len(rows)}")
        updated = 0
        for p in rows:
            if not p.created_at:
                continue
            dt = p.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            local_day = dt.astimezone(TZ).date().isoformat()
            p.day = local_day
            session.add(p)
            updated += 1

        session.commit()
        print(f"updated: {updated}")


if __name__ == "__main__":
    main()
