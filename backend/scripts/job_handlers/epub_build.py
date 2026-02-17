from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from app.db.init_db import init_db
from app.db.engine import engine
from app.models.paper import Paper
from app.core.config import settings
from app.services.epub_builder import build_epubs_for_pending


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-type", required=True, help="epub_build_scoped|epub_build_regen_scoped")
    ap.add_argument("--payload", required=True, help="path to payload json")
    args = ap.parse_args()

    job_type = str(args.job_type)
    payload_path = Path(args.payload)

    payload: dict = {}
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8")) or {}
    except Exception:
        payload = {}

    # Optional overrides
    if "epub_max" in payload:
        try:
            settings.epub_max = int(payload["epub_max"])
        except Exception:
            pass

    lang = str(payload.get("lang") or "en").strip().lower()
    langs: list[str]
    if lang in {"en", "zh"}:
        langs = [lang]
    elif lang in {"both", "all"}:
        langs = ["en", "zh"]
    else:
        langs = ["en"]

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

        overwrite = job_type == "epub_build_regen_scoped"

        print(
            f"EPUB_JOB_START: type={job_type} day={day} external_ids={len(external_ids) if external_ids else 0} "
            f"langs={langs} max={settings.epub_max} overwrite={overwrite}"
        )

        results = build_epubs_for_pending(
            session,
            day=day,
            external_ids=external_ids,
            langs=langs,
            max_n=settings.epub_max,
            overwrite=overwrite,
        )

        for r in results:
            print(f"EPUB_OK[{r.kind}]: {r.url_path}")

    print(f"EPUB_JOB_DONE: {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
