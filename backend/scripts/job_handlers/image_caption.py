from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select
from sqlalchemy import text

from app.db.init_db import init_db
from app.db.engine import engine
from app.models.paper import Paper
from app.core.config import settings

# We reuse the existing caption implementation.
from scripts.daily_run import run_image_caption_for_pending


def _latest_day(session: Session) -> str | None:
    return session.exec(
        select(Paper.day)
        .where(Paper.source == "hf_daily")
        .where(Paper.day.is_not(None))
        .order_by(Paper.day.desc())
        .limit(1)
    ).first()


def _parse_external_ids(s: str | None) -> list[str] | None:
    if not s:
        return None
    arr = [x.strip() for x in s.replace("\n", ",").split(",")]
    arr = [x for x in arr if x]
    return arr or None


def wipe_captions(
    session: Session,
    *,
    day: str | None,
    external_ids: list[str] | None,
    langs: list[str],
) -> int:
    """Clear cached captions for scoped papers (zh/en)."""

    cols = []
    if "zh" in langs:
        cols.append("image_captions_json=NULL")
    if "en" in langs:
        cols.append("image_captions_en_json=NULL")
    if not cols:
        cols = ["image_captions_json=NULL"]

    q = f"UPDATE papers SET {', '.join(cols)} WHERE raw_text_path IS NOT NULL"
    params: dict = {}
    if external_ids:
        # SQLite doesn't support binding list directly in plain text; use IN (...) with named params
        keys = []
        for i, eid in enumerate(external_ids):
            k = f"eid{i}"
            keys.append(f":{k}")
            params[k] = eid
        q += f" AND external_id IN ({','.join(keys)})"
    elif day:
        q += " AND day = :day"
        params["day"] = day

    # SQLModel Session.exec does not support params in some versions; use a raw connection.
    from app.db.engine import engine

    with engine.connect() as conn:
        r = conn.execute(text(q), params)
        conn.commit()

    # rowcount may be -1 for some drivers; best-effort
    try:
        return int(getattr(r, "rowcount", 0) or 0)
    except Exception:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-type", required=True, help="image_caption_scoped|image_caption_regen_scoped")
    ap.add_argument("--payload", required=True, help="path to payload json")
    args = ap.parse_args()

    job_type = str(args.job_type)
    payload_path = Path(args.payload)

    payload: dict = {}
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8")) or {}
    except Exception:
        payload = {}

    # Optional overrides for this run (do not persist to env)
    if "image_caption_max" in payload:
        try:
            settings.image_caption_max = int(payload["image_caption_max"])
        except Exception:
            pass
    if "image_caption_per_paper" in payload:
        try:
            settings.image_caption_per_paper = int(payload["image_caption_per_paper"])
        except Exception:
            pass

    # Language scope (zh|en|both)
    lang = str(payload.get("lang") or "both").strip().lower()
    langs: list[str]
    if lang in {"zh", "en"}:
        langs = [lang]
    else:
        langs = ["zh", "en"]

    # Apply to runtime settings for this job
    try:
        settings.papertok_langs = langs
    except Exception:
        pass

    with Session(engine) as session:
        day = payload.get("day")
        if isinstance(day, str):
            day = day.strip()
        else:
            day = None

        if day == "latest":
            day = _latest_day(session)

        external_ids = payload.get("external_ids")
        if isinstance(external_ids, list):
            external_ids = [str(x).strip() for x in external_ids if str(x).strip()]
            if not external_ids:
                external_ids = None
        elif isinstance(external_ids, str):
            external_ids = _parse_external_ids(external_ids)
        else:
            external_ids = None

        init_db()

        if job_type == "image_caption_regen_scoped":
            n = wipe_captions(session, day=day, external_ids=external_ids, langs=langs)
            print(
                f"WIPE_CAPTIONS_OK: cleared={n} day={day} external_ids={len(external_ids) if external_ids else 0} langs={langs}"
            )

        print(
            f"CAPTION_JOB_START: type={job_type} day={day} external_ids={len(external_ids) if external_ids else 0} "
            f"langs={langs} max={settings.image_caption_max} per_paper={settings.image_caption_per_paper}"
        )

        run_image_caption_for_pending(session, day=day, external_ids=external_ids)

    print(f"CAPTION_JOB_DONE: {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
