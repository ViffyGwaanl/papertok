"""Batch run mineru for papers that have pdf_path but no raw_text_path.

Usage:
  source .venv/bin/activate
  python -m scripts.mineru_batch

Env:
  MINERU_OUT_ROOT=<papertok>/data/mineru
  MINERU_MODEL_SOURCE=modelscope
  MINERU_MAX=2
"""

from __future__ import annotations

import os
from datetime import datetime

from sqlmodel import Session, select

from app.core.config import settings
from app.db.init_db import init_db
from app.db.engine import engine
from app.models.paper import Paper
from app.services.mineru_runner import run_mineru_pdf_to_md


def main():
    init_db()

    out_root = os.getenv("MINERU_OUT_ROOT", settings.mineru_out_root)
    model_source = os.getenv("MINERU_MODEL_SOURCE", "modelscope")
    max_n = int(os.getenv("MINERU_MAX", "2"))

    with Session(engine) as session:
        rows = session.exec(
            select(Paper)
            .where(Paper.pdf_path.is_not(None))
            .where(Paper.raw_text_path.is_(None))
            .order_by(Paper.id.asc())
            .limit(max_n)
        ).all()

        if not rows:
            print("No pending PDFs for mineru")
            return

        for p in rows:
            print(f"MINERU: {p.external_id} -> parsing...")
            res = run_mineru_pdf_to_md(
                pdf_path=p.pdf_path,
                out_root=out_root,
                model_source=model_source,
                backend="pipeline",
                method="txt",
                lang="en",
                formula=False,
                table=False,
            )
            if res.md_path.exists():
                p.raw_text_path = str(res.md_path)
                p.updated_at = datetime.utcnow()
                session.add(p)
                session.commit()
                print(f"OK: {p.external_id} -> {res.md_path}")
            else:
                print(f"WARN: mineru output missing md: {res.md_path}")


if __name__ == "__main__":
    main()
