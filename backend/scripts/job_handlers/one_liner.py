from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select
from sqlalchemy import text

from app.core.config import settings
from app.db.engine import engine
from app.db.init_db import init_db
from app.models.paper import Paper
from app.services.paper_events import record_paper_event

from scripts.daily_run import build_one_liner, _extract_abstract_from_mineru_markdown


def _parse_external_ids(s: str | None) -> list[str] | None:
    if not s:
        return None
    arr = [x.strip() for x in s.replace("\n", ",").split(",")]
    arr = [x for x in arr if x]
    return arr or None


def wipe_one_liners(session: Session, *, day: str | None, external_ids: list[str] | None, langs: list[str]) -> int:
    cols = []
    if "zh" in langs:
        cols.append("one_liner=NULL")
    if "en" in langs:
        cols.append("one_liner_en=NULL")
    if not cols:
        cols = ["one_liner=NULL"]

    q = f"UPDATE papers SET {', '.join(cols)} WHERE source='hf_daily'"
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
    ap.add_argument("--job-type", required=True, help="one_liner_scoped|one_liner_regen_scoped")
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

    try:
        settings.papertok_langs = langs
    except Exception:
        pass

    # Optional overrides
    if "one_liner_max" in payload:
        try:
            settings.one_liner_max = int(payload["one_liner_max"])
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

        if job_type == "one_liner_regen_scoped":
            n = wipe_one_liners(session, day=day, external_ids=external_ids, langs=langs)
            print(
                f"WIPE_ONE_LINER_OK: cleared={n} day={day} external_ids={len(external_ids) if external_ids else 0} langs={langs}"
            )

        print(
            f"ONE_LINER_JOB_START: type={job_type} day={day} external_ids={len(external_ids) if external_ids else 0} "
            f"langs={langs} max={settings.one_liner_max}"
        )

        q = select(Paper).where(Paper.source == "hf_daily")
        if external_ids:
            q = q.where(Paper.external_id.in_(external_ids))
        elif day:
            q = q.where(Paper.day == day)

        rows = session.exec(q.order_by(Paper.id.asc()).limit(int(settings.one_liner_max))).all()
        if not rows:
            print("ONE_LINER: nothing to do")
            return

        for p in rows:
            meta = json.loads(p.meta_json) if p.meta_json else {}
            hf_abstract = (
                meta.get("paper", {}).get("summary")
                or meta.get("paper", {}).get("abstract")
                or meta.get("summary")
                or meta.get("abstract")
            )

            mineru_abstract = None
            if settings.one_liner_prefer_mineru and p.raw_text_path:
                try:
                    md_path = Path(p.raw_text_path)
                    if md_path.exists():
                        md_text = md_path.read_text(encoding="utf-8", errors="ignore")
                        md_text = md_text[: int(settings.one_liner_mineru_input_chars)]
                        mineru_abstract = _extract_abstract_from_mineru_markdown(md_text)
                except Exception:
                    mineru_abstract = None

            abstract = mineru_abstract or (hf_abstract if isinstance(hf_abstract, str) else None)

            # Generate per language
            for lang0 in langs:
                stage = "one_liner_en" if lang0 == "en" else "one_liner"

                # Skip if already exists (non-regen job)
                if job_type != "one_liner_regen_scoped":
                    if lang0 == "en" and p.one_liner_en:
                        continue
                    if lang0 == "zh" and p.one_liner:
                        continue

                try:
                    record_paper_event(session, paper_id=p.id, stage=stage, status="started")
                    out = build_one_liner(p.title, abstract, lang=lang0)
                    out = (out or "").strip()
                    if lang0 == "en":
                        p.one_liner_en = out
                    else:
                        p.one_liner = out
                    p.display_title = p.display_title or p.title
                    p.updated_at = datetime.utcnow()
                    session.add(p)
                    session.commit()
                    record_paper_event(session, paper_id=p.id, stage=stage, status="success")
                    print(f"ONE_LINER_OK[{lang0}]: {p.external_id}")
                except Exception as e:
                    record_paper_event(session, paper_id=p.id, stage=stage, status="failed", error=str(e))
                    print(f"WARN: ONE_LINER failed[{lang0}] for {p.external_id}: {e}")

    print(f"ONE_LINER_JOB_DONE: {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
