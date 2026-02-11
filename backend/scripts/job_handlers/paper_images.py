from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select
from sqlalchemy import text

from app.core.config import settings
from app.db.engine import engine
from app.db.init_db import init_db
from app.models.paper import Paper
from app.services.app_config import get_effective_app_config

# Reuse pipeline implementation
from scripts.daily_run import run_paper_images_for_pending


def _parse_external_ids(s: str | None) -> list[str] | None:
    if not s:
        return None
    arr = [x.strip() for x in s.replace("\n", ",").split(",")]
    arr = [x for x in arr if x]
    return arr or None


def _wipe_disk_for_paper(*, external_id: str, lang: str, out_root: str) -> None:
    """Best-effort remove generated files for one paper/lang."""

    if not external_id:
        return

    root = Path(out_root)
    paper_dir = root / external_id
    if lang == "en":
        target = paper_dir / "en"
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        return

    # zh: remove pngs in paper_dir (but keep en/)
    if not paper_dir.exists() or not paper_dir.is_dir():
        return

    for fp in paper_dir.iterdir():
        if fp.is_dir() and fp.name == "en":
            continue
        if fp.is_file() and fp.suffix.lower() in {".png", ".webp", ".jpg", ".jpeg"}:
            try:
                fp.unlink()
            except Exception:
                pass


def wipe_paper_images(
    session: Session,
    *,
    day: str | None,
    external_ids: list[str] | None,
    langs: list[str],
    provider: str | None,
) -> int:
    # scope paper ids first
    q = select(Paper.id, Paper.external_id).where(Paper.source == "hf_daily")
    if external_ids:
        q = q.where(Paper.external_id.in_(external_ids))
    elif day:
        q = q.where(Paper.day == day)

    rows = session.exec(q).all()
    paper_ids = [int(r[0]) for r in rows]
    paper_exts = [str(r[1]) for r in rows if r[1]]

    if not paper_ids:
        return 0

    # wipe db rows
    params: dict = {}
    keys = []
    for i, pid in enumerate(paper_ids):
        k = f"pid{i}"
        keys.append(f":{k}")
        params[k] = pid

    cond = [f"paper_id IN ({','.join(keys)})", "kind='generated'"]
    if provider in {"seedream", "glm"}:
        cond.append("provider = :prov")
        params["prov"] = provider

    # lang filter
    lang_list = [x for x in langs if x in {"zh", "en"}]
    if lang_list and len(lang_list) < 2:
        cond.append("lang = :lang")
        params["lang"] = lang_list[0]

    q_del = "DELETE FROM paper_images WHERE " + " AND ".join(cond)
    from app.db.engine import engine

    with engine.connect() as conn:
        r = conn.execute(text(q_del), params)
        conn.commit()

    # wipe disk (best-effort)
    # determine out_root(s)
    out_roots: list[str] = []
    if provider == "glm":
        out_roots = [settings.paper_gen_images_glm_dir]
    elif provider == "seedream":
        out_roots = [settings.paper_gen_images_dir]
    else:
        out_roots = [settings.paper_gen_images_dir, settings.paper_gen_images_glm_dir]

    for out_root in out_roots:
        for eid in paper_exts:
            if "zh" in langs and "en" in langs:
                # both -> remove entire paper dir
                try:
                    shutil.rmtree(Path(out_root) / eid, ignore_errors=True)
                except Exception:
                    pass
            else:
                for lang0 in langs:
                    _wipe_disk_for_paper(external_id=eid, lang=lang0, out_root=out_root)

    try:
        return int(getattr(r, "rowcount", 0) or 0)
    except Exception:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-type", required=True, help="paper_images_scoped|paper_images_regen_scoped")
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
    if "paper_images_per_paper" in payload:
        try:
            settings.paper_images_per_paper = int(payload["paper_images_per_paper"])
        except Exception:
            pass
    if "paper_images_max_papers" in payload:
        try:
            settings.paper_images_max_papers = int(payload["paper_images_max_papers"])
        except Exception:
            pass
    if "paper_images_concurrency" in payload:
        try:
            settings.paper_images_concurrency = int(payload["paper_images_concurrency"])
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

            # Provider selection
        # Default behavior (safe/cost-saving): generate ONLY the current display provider.
        # Overrides (payload):
        # - paper_images_generate_only_display: 0/1
        # - paper_images_providers / providers: ["seedream","glm"]
        # - provider: "seedream"|"glm"|"display"|"all"
        app_cfg = get_effective_app_config(session)
        display = (app_cfg.paper_images_display_provider or "seedream").strip().lower()

        # 1) read payload overrides
        gen_only = payload.get("paper_images_generate_only_display")
        if isinstance(gen_only, str):
            gen_only = gen_only.strip().lower() in {"1", "true", "yes"}
        elif isinstance(gen_only, (int, float)):
            gen_only = bool(int(gen_only))
        elif isinstance(gen_only, bool):
            gen_only = gen_only
        else:
            gen_only = None

        provs0 = payload.get("paper_images_providers")
        if provs0 is None:
            provs0 = payload.get("providers")

        providers: list[str] = []
        if isinstance(provs0, list):
            providers = [str(x).strip().lower() for x in provs0 if str(x).strip()]
        elif isinstance(provs0, str):
            providers = [x.strip().lower() for x in provs0.split(",") if x.strip()]

        prov1 = str(payload.get("provider") or "").strip().lower()
        if prov1:
            if prov1 in {"seedream", "glm"}:
                providers = [prov1]
            elif prov1 in {"all", "both"}:
                providers = ["seedream", "glm"]
            elif prov1 == "display":
                providers = [display] if display in {"seedream", "glm"} else []
                if gen_only is None:
                    gen_only = True

        # 2) apply to runtime settings for this job
        if gen_only is not None:
            try:
                settings.paper_images_generate_only_display = bool(gen_only)
            except Exception:
                pass

        if providers:
            try:
                settings.paper_images_providers = providers
            except Exception:
                pass
            # If providers are explicitly set, default to generating those providers (not display-only)
            if gen_only is None:
                try:
                    settings.paper_images_generate_only_display = False
                except Exception:
                    pass

        # Provider passed to wipe function (regen only).
        # - if display-only: restrict wipe to display provider
        # - else if providers explicitly set: wipe only when a single provider is selected
        provider: str | None = None
        if getattr(settings, "paper_images_generate_only_display", False):
            if display in {"seedream", "glm"}:
                provider = display
        else:
            # only safe to wipe precisely when exactly one provider is requested
            provs_eff = [x for x in (providers or []) if x in {"seedream", "glm"}]
            if len(provs_eff) == 1:
                provider = provs_eff[0]

        if job_type == "paper_images_regen_scoped":
            n = wipe_paper_images(session, day=day, external_ids=external_ids, langs=langs, provider=provider)
            print(
                f"WIPE_PAPER_IMAGES_OK: deleted_rows={n} day={day} external_ids={len(external_ids) if external_ids else 0} langs={langs} provider={provider}"
            )

        print(
            f"PAPER_IMAGES_JOB_START: type={job_type} day={day} external_ids={len(external_ids) if external_ids else 0} "
            f"langs={langs} per_paper={settings.paper_images_per_paper} max_papers={settings.paper_images_max_papers} "
            f"generate_only_display={getattr(settings, 'paper_images_generate_only_display', False)} "
            f"providers={getattr(settings, 'paper_images_providers', None)} wipe_provider={provider}"
        )

        settings.run_paper_images = True
        run_paper_images_for_pending(session, day=day, external_ids=external_ids)

    print(f"PAPER_IMAGES_JOB_DONE: {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
