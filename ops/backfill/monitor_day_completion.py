#!/usr/bin/env python3
"""Monitor day-level backfill completion and print a report ONLY when a day is complete.

Designed to be triggered periodically (cron/systemEvent). Uses a local state file to avoid duplicates.

Completion criteria per day:
- papers=N
- zh/en one-liner counts == N
- zh/en explain counts == N
- zh/en caption counts == N
- generated images:
  - glm total (zh+en) >= N * per_paper * 2
  - seedream total (zh+en) >= N * per_paper * 2

Report format: 8 metrics
  zh/en: liner, explain, caption (6)
  glm images total, seedream images total (2)

Exit code: 0 always (best-effort)
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path


def _db_path() -> str:
    db_url = (os.getenv("DB_URL") or "").strip()
    if db_url.startswith("sqlite:////"):
        return "/" + db_url[len("sqlite:////") :]
    return os.path.expanduser("~/papertok-deploy/shared/data/db/papertok.sqlite")


def _state_path() -> Path:
    base = os.getenv("PAPERTOK_BACKFILL_STATE_DIR") or os.path.expanduser(
        "~/papertok-deploy/shared/data/backfill"
    )
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p / "day_completion_state.json"


def _load_state(p: Path) -> dict:
    if not p.exists():
        return {"reported": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {"reported": {}}
    except Exception:
        return {"reported": {}}


def _save_state(p: Path, st: dict) -> None:
    try:
        p.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    db_path = _db_path()
    if not os.path.exists(db_path):
        return

    per_paper = int(os.getenv("PAPER_IMAGES_PER_PAPER", "3") or 3)
    expected_langs = 2  # zh + en

    st_path = _state_path()
    st = _load_state(st_path)
    reported = st.get("reported") or {}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # last 7 hf_daily days in DB
    days = [
        r["day"]
        for r in conn.execute(
            """
            select day
            from papers
            where source='hf_daily' and day is not null
            group by day
            order by day desc
            limit 7;
            """
        ).fetchall()
        if r["day"]
    ]

    reports: list[str] = []

    for day in days:
        # papers & text fields
        row = conn.execute(
            """
            select
              count(*) as papers,
              sum(case when raw_text_path is not null then 1 else 0 end) as mineru,
              sum(case when one_liner is not null and one_liner!='' then 1 else 0 end) as zh_liner,
              sum(case when one_liner_en is not null and one_liner_en!='' then 1 else 0 end) as en_liner,
              sum(case when content_explain_cn is not null and content_explain_cn!='' then 1 else 0 end) as zh_exp,
              sum(case when content_explain_en is not null and content_explain_en!='' then 1 else 0 end) as en_exp,
              sum(case when image_captions_json is not null and image_captions_json!='' and image_captions_json!='{}' then 1 else 0 end) as zh_cap,
              sum(case when image_captions_en_json is not null and image_captions_en_json!='' and image_captions_en_json!='{}' then 1 else 0 end) as en_cap
            from papers
            where source='hf_daily' and day=?;
            """,
            (day,),
        ).fetchone()
        if not row:
            continue

        papers = int(row["papers"] or 0)
        if papers <= 0:
            continue

        zh_liner = int(row["zh_liner"] or 0)
        en_liner = int(row["en_liner"] or 0)
        zh_exp = int(row["zh_exp"] or 0)
        en_exp = int(row["en_exp"] or 0)
        zh_cap = int(row["zh_cap"] or 0)
        en_cap = int(row["en_cap"] or 0)

        expected_imgs = papers * per_paper * expected_langs

        # images totals by provider
        img_rows = conn.execute(
            """
            select pi.provider, count(*) as n
            from paper_images pi
            join papers p on p.id=pi.paper_id
            where p.source='hf_daily'
              and p.day=?
              and pi.kind='generated'
              and pi.enabled=1
              and pi.status='generated'
              and pi.url_path is not null
            group by pi.provider;
            """,
            (day,),
        ).fetchall()
        imgs = {str(r["provider"]): int(r["n"] or 0) for r in img_rows}
        glm_imgs = imgs.get("glm", 0)
        seedream_imgs = imgs.get("seedream", 0)

        complete = (
            zh_liner >= papers
            and en_liner >= papers
            and zh_exp >= papers
            and en_exp >= papers
            and zh_cap >= papers
            and en_cap >= papers
            and glm_imgs >= expected_imgs
            and seedream_imgs >= expected_imgs
        )

        if not complete:
            continue

        if str(day) in reported:
            continue

        # Mark reported first to avoid duplicates if sending fails.
        reported[str(day)] = {"ts": int(time.time())}

        rep = (
            f"✅ Day 完成验收：{day}（papers={papers}，每篇{per_paper}张，双语=2，单provider期望={expected_imgs}张）\n"
            f"- one-liner: zh {zh_liner}/{papers} | en {en_liner}/{papers}\n"
            f"- explain  : zh {zh_exp}/{papers} | en {en_exp}/{papers}\n"
            f"- caption  : zh {zh_cap}/{papers} | en {en_cap}/{papers}\n"
            f"- images   : glm {glm_imgs}/{expected_imgs} | seedream {seedream_imgs}/{expected_imgs}"
        )
        reports.append(rep)

    st["reported"] = reported
    _save_state(st_path, st)

    if reports:
        print("\n\n".join(reports))


if __name__ == "__main__":
    main()
