from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from sqlmodel import Session
from sqlalchemy import text

from app.core.config import settings
from app.db.engine import engine
from app.db.init_db import init_db

# Reuse pipeline implementation
from scripts.daily_run import run_content_analysis_for_pending


def _parse_external_ids(s: str | None) -> list[str] | None:
    if not s:
        return None
    arr = [x.strip() for x in s.replace("\n", ",").split(",")]
    arr = [x for x in arr if x]
    return arr or None


def wipe_explain(session: Session, *, day: str | None, external_ids: list[str] | None, langs: list[str]) -> int:
    cols = []
    if "zh" in langs:
        cols.append("content_explain_cn=NULL")
    if "en" in langs:
        cols.append("content_explain_en=NULL")
    if not cols:
        cols = ["content_explain_cn=NULL"]

    q = f"UPDATE papers SET {', '.join(cols)} WHERE raw_text_path IS NOT NULL"
    params: dict = {}

    if external_ids:
        keys = []
        for i, eid in enumerate(external_ids):
            k = f"eid{i}"
            keys.append(f":{k}")
            params[k] = eid
        q += f" AND external_id IN ({','.join(keys)})"
    elif day:
        q += " AND day = :day"
        params["day"] = day

    from app.db.engine import engine

    with engine.connect() as conn:
        r = conn.execute(text(q), params)
        conn.commit()

    try:
        return int(getattr(r, "rowcount", 0) or 0)
    except Exception:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-type", required=True, help="content_analysis_scoped|content_analysis_regen_scoped")
    ap.add_argument("--payload", required=True, help="path to payload json")
    args = ap.parse_args()

    job_type = str(args.job_type)
    payload_path = Path(args.payload)

    payload: dict = {}
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8")) or {}
    except Exception:
        payload = {}

    # Language scope
    lang = str(payload.get("lang") or "both").strip().lower()
    if lang in {"zh", "en"}:
        langs = [lang]
    else:
        langs = ["zh", "en"]

    # Apply runtime overrides
    try:
        settings.papertok_langs = langs
    except Exception:
        pass

    if "content_analysis_max" in payload:
        try:
            settings.content_analysis_max = int(payload["content_analysis_max"])
        except Exception:
            pass
    if "content_analysis_input_chars" in payload:
        try:
            settings.content_analysis_input_chars = int(payload["content_analysis_input_chars"])
        except Exception:
            pass

    if "content_analysis_concurrency" in payload:
        try:
            settings.content_analysis_concurrency = int(payload["content_analysis_concurrency"])
        except Exception:
            pass

    init_db()

    with Session(engine) as session:
        day = payload.get("day")
        if isinstance(day, str):
            day = day.strip()
        else:
            day = None

        external_ids = payload.get("external_ids")
        if isinstance(external_ids, list):
            external_ids = [str(x).strip() for x in external_ids if str(x).strip()]
            if not external_ids:
                external_ids = None
        elif isinstance(external_ids, str):
            external_ids = _parse_external_ids(external_ids)
        else:
            external_ids = None

        if job_type == "content_analysis_regen_scoped":
            n = wipe_explain(session, day=day, external_ids=external_ids, langs=langs)
            print(
                f"WIPE_EXPLAIN_OK: cleared={n} day={day} external_ids={len(external_ids) if external_ids else 0} langs={langs}"
            )

        print(
            f"CONTENT_ANALYSIS_JOB_START: type={job_type} day={day} external_ids={len(external_ids) if external_ids else 0} "
            f"langs={langs} max={settings.content_analysis_max}"
        )

        # Ensure stage enabled
        settings.run_content_analysis = True
        run_content_analysis_for_pending(session, day=day, external_ids=external_ids)

    print(f"CONTENT_ANALYSIS_JOB_DONE: {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
