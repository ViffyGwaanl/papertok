"""Export an offline seed pack for the mobile app.

Goal: bundle the earliest-day Top10 (hf_daily) into the iOS/Android app so the UI
can show something even when the tunnel/network is down.

Exports:
- frontend/wikitok/frontend/public/seed/seed-pack.json
- frontend/wikitok/frontend/public/seed/images/<external_id>.jpg

Data included per paper:
- card fields (title/extract/url/day + 1 bundled image)
- detail fields (content_explain_cn)

Usage:
  cd papertok
  backend/.venv/bin/python backend/scripts/export_seed_pack.py
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class SeedCard:
    pageid: int
    title: str
    displaytitle: str
    extract: str
    url: str
    day: str | None
    thumbnail: dict[str, Any] | None
    thumbnails: list[str] | None


@dataclass
class SeedDetail:
    id: int
    external_id: str
    day: str | None
    title: str
    display_title: str
    url: str | None
    one_liner: str | None
    content_explain_cn: str | None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _db_path(root: Path) -> Path:
    # Match default layout: papertok/data/db/papertok.sqlite
    return root / "data" / "db" / "papertok.sqlite"


def _sips_convert_to_jpg(src: Path, dst: Path, quality: int = 75) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    # sips is built-in on macOS.
    cmd = [
        "sips",
        "-s",
        "format",
        "jpeg",
        "-s",
        "formatOptions",
        str(quality),
        str(src),
        "--out",
        str(dst),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> None:
    root = _repo_root()
    db = _db_path(root)
    if not db.exists():
        raise SystemExit(f"DB not found: {db}")

    seed_dir = root / "frontend" / "wikitok" / "frontend" / "public" / "seed"
    images_dir = seed_dir / "images"
    seed_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute(
        """
        SELECT MIN(day) AS min_day
        FROM papers
        WHERE source='hf_daily' AND day IS NOT NULL AND day <> ''
        """
    )
    min_day = cur.fetchone()["min_day"]
    if not min_day:
        raise SystemExit("No hf_daily day found in DB")

    # Pick top 10 processed papers for that earliest day.
    cur.execute(
        """
        SELECT id, external_id, title, COALESCE(display_title, title) AS display_title,
               one_liner, content_explain_cn, url, day
        FROM papers
        WHERE source='hf_daily'
          AND day = ?
          AND one_liner IS NOT NULL
          AND content_explain_cn IS NOT NULL
        ORDER BY id ASC
        LIMIT 10
        """,
        (min_day,),
    )
    papers = cur.fetchall()
    if not papers:
        raise SystemExit(f"No processed papers for earliest day={min_day}")

    cards: list[SeedCard] = []
    details: dict[str, SeedDetail] = {}

    missing_images: list[str] = []

    for p in papers:
        pid = int(p["id"])
        external_id = str(p["external_id"])
        title = str(p["title"])
        display_title = str(p["display_title"])
        extract = str(p["one_liner"])
        url = str(p["url"] or f"https://huggingface.co/papers/{external_id}")
        day = p["day"]

        # Find the first generated image (prefer glm, then seedream)
        img_local: str | None = None
        for provider in ("glm", "seedream"):
            cur.execute(
                """
                SELECT local_path
                FROM paper_images
                WHERE paper_id = ?
                  AND kind = 'generated'
                  AND provider = ?
                  AND enabled = 1
                  AND status = 'generated'
                  AND local_path IS NOT NULL
                ORDER BY order_idx ASC
                LIMIT 1
                """,
                (pid, provider),
            )
            row = cur.fetchone()
            if row and row["local_path"]:
                img_local = str(row["local_path"])
                break

        img_rel = None
        if img_local:
            src = Path(img_local)
            if src.exists() and src.is_file():
                dst = images_dir / f"{external_id}.jpg"
                # Convert only if missing or src newer than dst.
                if (not dst.exists()) or (src.stat().st_mtime > dst.stat().st_mtime):
                    try:
                        _sips_convert_to_jpg(src, dst, quality=75)
                    except Exception:
                        # Fallback: raw copy if conversion fails.
                        dst.write_bytes(src.read_bytes())
                img_rel = f"/seed/images/{external_id}.jpg"
            else:
                missing_images.append(external_id)
        else:
            missing_images.append(external_id)

        thumb = (
            {"source": img_rel, "width": 1088, "height": 1920}
            if img_rel
            else None
        )

        cards.append(
            SeedCard(
                pageid=pid,
                title=title,
                displaytitle=display_title,
                extract=extract,
                url=url,
                day=day,
                thumbnail=thumb,
                thumbnails=[img_rel] if img_rel else None,
            )
        )

        details[str(pid)] = SeedDetail(
            id=pid,
            external_id=external_id,
            day=day,
            title=title,
            display_title=display_title,
            url=url,
            one_liner=extract,
            content_explain_cn=str(p["content_explain_cn"]),
        )

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": {
            "kind": "hf_daily",
            "earliest_day": min_day,
            "count": len(cards),
        },
        "cards": [asdict(c) for c in cards],
        "details": {k: asdict(v) for k, v in details.items()},
        "missing_images": missing_images,
    }

    out_json = seed_dir / "seed-pack.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote: {out_json}")
    print(f"Images dir: {images_dir}")
    if missing_images:
        print(f"WARNING: missing images for {len(missing_images)} papers: {missing_images[:5]}...")


if __name__ == "__main__":
    main()
