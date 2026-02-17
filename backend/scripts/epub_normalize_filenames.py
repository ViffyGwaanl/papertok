from __future__ import annotations

"""Normalize existing EPUB filenames to include external_id.

Target naming scheme:
  <EPUB_OUT_ROOT>/<external_id>/<external_id>.en.epub

We keep backward compatibility by ensuring a legacy alias also exists:
  <EPUB_OUT_ROOT>/<external_id>/en.epub

This script is safe to re-run.

Run:
  python -m scripts.epub_normalize_filenames
"""

import os
import shutil
from pathlib import Path

from sqlmodel import Session, select

from app.core.config import settings
from app.db.init_db import init_db
from app.db.engine import engine
from app.models.paper import Paper


def _ensure_alias(src: Path, alias: Path) -> None:
    if alias.exists():
        return
    try:
        os.link(src, alias)
    except Exception:
        try:
            shutil.copy2(src, alias)
        except Exception:
            pass


def main() -> None:
    init_db()

    out_root = Path(settings.epub_out_root)

    with Session(engine) as session:
        rows = session.exec(
            select(Paper)
            .where(Paper.source == "hf_daily")
            .where(Paper.external_id.is_not(None))
            .where(Paper.epub_path_en.is_not(None))
        ).all()

        updated = 0
        missing_files = 0

        for p in rows:
            external_id = (p.external_id or "").strip()
            if not external_id:
                continue

            out_dir = out_root / external_id
            new_name = f"{external_id}.en.epub"
            new_file = out_dir / new_name
            legacy_file = out_dir / "en.epub"

            # If we have legacy but not new, create new as alias.
            if not new_file.exists() and legacy_file.exists():
                _ensure_alias(legacy_file, new_file)

            # If we have new but not legacy, create legacy as alias.
            if new_file.exists() and not legacy_file.exists():
                _ensure_alias(new_file, legacy_file)

            if not new_file.exists() and not legacy_file.exists():
                missing_files += 1
                continue

            # Canonicalize DB fields to new filename.
            p.epub_path_en = str(new_file)
            p.epub_url_en = f"/static/epub/{external_id}/{new_name}"
            session.add(p)
            updated += 1

        session.commit()

    print(
        f"EPUB_NORMALIZE_DONE: updated_rows={updated} missing_files={missing_files} out_root={out_root}"
    )


if __name__ == "__main__":
    main()
