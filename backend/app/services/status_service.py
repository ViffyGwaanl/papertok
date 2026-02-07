from __future__ import annotations

from datetime import datetime
import json

from sqlalchemy import case, func
from sqlmodel import Session, select

from app.core.config import settings
from app.db.engine import engine
from app.models.job import Job
from app.models.paper import Paper
from app.models.paper_event import PaperEvent
from app.models.paper_image import PaperImage
from app.services.app_config import get_effective_app_config


def get_status_snapshot(*, limit: int = 50, include_sensitive: bool = False) -> dict:
    """Return a status snapshot.

    - Public mode (include_sensitive=False): safe to expose on the public site.
      Must not include local absolute paths (e.g. /Users/...), log paths, or
      detailed operational errors.

    - Admin mode (include_sensitive=True): includes operational details such as
      recent failures with log_path and job running list.
    """

    limit = max(1, min(int(limit or 50), 200))

    with Session(engine) as session:
        app_cfg = get_effective_app_config(session)

        papers = session.exec(select(Paper).where(Paper.source == "hf_daily")).all()
        latest_day = session.exec(
            select(Paper.day)
            .where(Paper.source == "hf_daily")
            .where(Paper.day.is_not(None))
            .order_by(Paper.day.desc())
            .limit(1)
        ).first()

        pdf = sum(1 for p in papers if p.pdf_path)
        mineru = sum(1 for p in papers if p.raw_text_path)
        explain = sum(1 for p in papers if p.content_explain_cn)
        captions = sum(1 for p in papers if p.image_captions_json)

        # Caption coverage (best-effort)
        caption_entries = 0
        for p in papers:
            if not p.image_captions_json:
                continue
            try:
                d = json.loads(p.image_captions_json) or {}
                if isinstance(d, dict):
                    caption_entries += len(d)
            except Exception:
                pass

        missing_pdf = session.exec(
            select(Paper.external_id)
            .where(Paper.source == "hf_daily")
            .where(Paper.pdf_path.is_(None))
            .limit(limit)
        ).all()
        missing_mineru = session.exec(
            select(Paper.external_id)
            .where(Paper.source == "hf_daily")
            .where(Paper.raw_text_path.is_(None))
            .limit(limit)
        ).all()
        missing_explain = session.exec(
            select(Paper.external_id)
            .where(Paper.source == "hf_daily")
            .where(Paper.content_explain_cn.is_(None))
            .limit(limit)
        ).all()
        missing_captions = session.exec(
            select(Paper.external_id)
            .where(Paper.source == "hf_daily")
            .where(Paper.image_captions_json.is_(None))
            .limit(limit)
        ).all()

        # paper_images per provider (public-safe aggregates)
        rows = session.exec(
            select(
                PaperImage.provider,
                func.count(PaperImage.id),
                func.sum(case((PaperImage.status == "generated", 1), else_=0)),
                func.sum(case((PaperImage.status == "failed", 1), else_=0)),
            )
            .where(PaperImage.kind == "generated")
            .where(PaperImage.enabled == True)  # noqa: E712
            .group_by(PaperImage.provider)
        ).all()

        by_provider = {
            prov: {"rows": int(n or 0), "generated": int(gen or 0), "failed": int(f or 0)}
            for (prov, n, gen, f) in rows
        }

        # recent image generation failures
        recent_failed_imgs = session.exec(
            select(
                Paper.external_id,
                PaperImage.provider,
                PaperImage.order_idx,
                PaperImage.error,
                PaperImage.updated_at,
            )
            .join(Paper, Paper.id == PaperImage.paper_id)
            .where(PaperImage.kind == "generated")
            .where(PaperImage.status == "failed")
            .order_by(PaperImage.updated_at.desc())
            .limit(min(limit, 50))
        ).all()

        # recent paper-level failures (mineru/explain/caption/paper_images/pdf)
        recent_paper_failed = session.exec(
            select(
                Paper.external_id,
                PaperEvent.stage,
                PaperEvent.error,
                PaperEvent.log_path,
                PaperEvent.created_at,
            )
            .select_from(PaperEvent)
            .join(Paper, Paper.id == PaperEvent.paper_id)
            .where(PaperEvent.status == "failed")
            .order_by(PaperEvent.created_at.desc())
            .limit(min(limit, 50))
        ).all()

        stage_rows = session.exec(
            select(PaperEvent.stage, func.count(PaperEvent.id))
            .where(PaperEvent.status == "failed")
            .group_by(PaperEvent.stage)
        ).all()
        failed_by_stage = {stage: int(n or 0) for (stage, n) in stage_rows}

        skipped_rows = session.exec(
            select(PaperEvent.stage, func.count(PaperEvent.id))
            .where(PaperEvent.status == "skipped")
            .group_by(PaperEvent.stage)
        ).all()
        skipped_by_stage = {stage: int(n or 0) for (stage, n) in skipped_rows}

        # job queue summary (public-safe aggregates)
        job_rows = session.exec(select(Job.status, func.count(Job.id)).group_by(Job.status)).all()
        jobs_by_status = {st: int(n or 0) for (st, n) in job_rows}

        running_jobs = session.exec(
            select(Job.id, Job.job_type, Job.status, Job.started_at, Job.log_path)
            .where(Job.status == "running")
            .order_by(Job.started_at.desc())
            .limit(20)
        ).all()

        recent_paper_skipped = session.exec(
            select(
                Paper.external_id,
                PaperEvent.stage,
                PaperEvent.error,
                PaperEvent.log_path,
                PaperEvent.created_at,
            )
            .select_from(PaperEvent)
            .join(Paper, Paper.id == PaperEvent.paper_id)
            .where(PaperEvent.status == "skipped")
            .order_by(PaperEvent.created_at.desc())
            .limit(min(limit, 50))
        ).all()

    # Build response
    res: dict = {
        "now": datetime.now().isoformat(timespec="seconds"),
        "latest_day": latest_day,
        "config": {
            "app": app_cfg.model_dump(),
        },
        "pipeline": {
            "hf_top_n": int(settings.hf_top_n),
            "download_pdf": bool(settings.download_pdf),
            "run_mineru": bool(settings.run_mineru),
            "mineru_max": int(settings.mineru_max),
            "mineru_model_source": settings.mineru_model_source,
            "mineru_repair_on_fail": bool(settings.mineru_repair_on_fail),
            "mineru_repair_tool": settings.mineru_repair_tool,
            "run_content_analysis": bool(settings.run_content_analysis),
            "content_analysis_max": int(settings.content_analysis_max),
            "run_image_caption": bool(settings.run_image_caption),
            "image_caption_model": settings.image_caption_model,
            "image_caption_max": int(settings.image_caption_max),
            "image_caption_per_paper": int(settings.image_caption_per_paper),
            "run_paper_images": bool(settings.run_paper_images),
            "paper_images_per_paper": int(settings.paper_images_per_paper),
            "paper_images_max_papers": int(settings.paper_images_max_papers),
            "paper_images_providers": settings.paper_images_providers,
        },
        "papers": {
            "total": len(papers),
            "pdf": pdf,
            "mineru_md": mineru,
            "content_explain_cn": explain,
            "image_captions_json": captions,
            "caption_entries": caption_entries,
            "missing": {
                "pdf": {"count": max(0, len(papers) - pdf), "examples": missing_pdf},
                "mineru_md": {"count": max(0, len(papers) - mineru), "examples": missing_mineru},
                "content_explain_cn": {"count": max(0, len(papers) - explain), "examples": missing_explain},
                "image_captions_json": {"count": max(0, len(papers) - captions), "examples": missing_captions},
            },
        },
        "paper_images": {
            "by_provider": by_provider,
            "recent_failed": [],
            "recent_failed_count": len(recent_failed_imgs),
        },
        "paper_events": {
            "failed_by_stage": failed_by_stage,
            "skipped_by_stage": skipped_by_stage,
            "recent_failed": [],
            "recent_failed_count": len(recent_paper_failed),
            "recent_skipped": [],
            "recent_skipped_count": len(recent_paper_skipped),
        },
        "jobs": {
            "by_status": jobs_by_status,
            "running": [],
            "running_count": len(running_jobs),
        },
    }

    if include_sensitive:
        res["paper_images"]["recent_failed"] = [
            {
                "external_id": eid,
                "provider": prov,
                "order_idx": int(oidx or 0),
                "error": err,
                "updated_at": (t.isoformat(timespec="seconds") if hasattr(t, "isoformat") else str(t)),
            }
            for (eid, prov, oidx, err, t) in recent_failed_imgs
        ]

        res["paper_events"]["recent_failed"] = [
            {
                "external_id": eid,
                "stage": stage,
                "error": err,
                "log_path": logp,
                "created_at": (t.isoformat(timespec="seconds") if hasattr(t, "isoformat") else str(t)),
            }
            for (eid, stage, err, logp, t) in recent_paper_failed
        ]

        res["paper_events"]["recent_skipped"] = [
            {
                "external_id": eid,
                "stage": stage,
                "error": err,
                "log_path": logp,
                "created_at": (t.isoformat(timespec="seconds") if hasattr(t, "isoformat") else str(t)),
            }
            for (eid, stage, err, logp, t) in recent_paper_skipped
        ]

        res["jobs"]["running"] = [
            {
                "id": int(i),
                "job_type": jt,
                "status": st,
                "started_at": (t.isoformat(timespec="seconds") if hasattr(t, "isoformat") and t else None),
                "log_path": lp,
            }
            for (i, jt, st, t, lp) in running_jobs
        ]

    return res
