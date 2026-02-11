from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from app.core.config import settings
from app.db.engine import engine
from app.models.job import Job
from app.services.job_queue import enqueue_job, get_job, list_jobs

router = APIRouter(prefix="/api/admin/jobs", tags=["admin-jobs"])


def _require_admin(request: Request) -> None:
    token = (settings.admin_token or "").strip()
    if not token:
        return
    got = (request.headers.get("x-admin-token") or "").strip()
    if got != token:
        raise HTTPException(status_code=401, detail="admin token required")


def get_session():
    with Session(engine) as session:
        yield session


SUPPORTED_JOB_TYPES = {
    # one-liner
    "one_liner_scoped": "Generate one-liners for a scoped set (fill missing)",
    "one_liner_regen_scoped": "Re-generate one-liners for a scoped set (wipe then run)",

    # explanation
    "content_analysis_scoped": "Generate explanations (zh/en) for a scoped set (fill missing)",
    "content_analysis_regen_scoped": "Re-generate explanations (zh/en) for a scoped set (wipe then run)",

    # captions
    "image_caption_scoped": "Generate captions (zh/en) for a scoped set (fill missing)",
    "image_caption_regen_scoped": "Re-generate captions (zh/en) for a scoped set (wipe then run)",

    # images
    "paper_images_scoped": "Generate paper images (zh/en) for a scoped set (fill missing)",
    "paper_images_regen_scoped": "Re-generate paper images (zh/en) for a scoped set (wipe then run)",
    "paper_images_glm_backfill": "Backfill GLM generated images for all papers",

    # paper_events
    "paper_events_backfill": "Backfill paper_events for current DB state (adds skipped/success markers)",

    # per-paper retry
    "paper_retry_stage": "Retry one pipeline stage for a specific paper (pdf/mineru/explain/caption/paper_images)",
}


@router.get("")
def api_list_jobs(
    request: Request,
    limit: int = 50,
    session: Session = Depends(get_session),
):
    _require_admin(request)
    rows = list_jobs(session, limit=limit)
    return {
        "supported": SUPPORTED_JOB_TYPES,
        "jobs": [j.model_dump() for j in rows],
    }


@router.post("/{job_type}")
def api_enqueue_job(
    job_type: str,
    payload: dict | None,
    request: Request,
    session: Session = Depends(get_session),
):
    _require_admin(request)

    job_type = (job_type or "").strip()
    if job_type not in SUPPORTED_JOB_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported job_type: {job_type}")

    j = enqueue_job(session, job_type=job_type, payload=payload or {})
    return {"job": j.model_dump()}


@router.get("/{job_id}")
def api_get_job(
    job_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    _require_admin(request)
    j = get_job(session, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job": j.model_dump()}


@router.get("/{job_id}/log")
def api_get_job_log(
    job_id: int,
    request: Request,
    tail_lines: int = 200,
    session: Session = Depends(get_session),
):
    _require_admin(request)
    j = get_job(session, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="job not found")

    if not j.log_path:
        return {"log": "(no log yet)"}

    p = Path(j.log_path)
    if not p.exists() or not p.is_file():
        return {"log": f"(log missing on disk) {j.log_path}"}

    tail_lines = max(20, min(int(tail_lines or 200), 2000))

    # Read tail by lines (cheap enough for our log sizes)
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {"log": f"(failed to read log) {e}"}

    lines = txt.splitlines()
    if len(lines) > tail_lines:
        lines = lines[-tail_lines:]

    return {"log": "\n".join(lines) + "\n"}


@router.post("/worker/kick")
def api_kick_worker_now(request: Request):
    """Kick the launchd job worker to run immediately (macOS only)."""

    _require_admin(request)

    if sys.platform != "darwin":
        raise HTTPException(status_code=501, detail="kick is only supported on macOS")

    uid = os.getuid()
    target = f"gui/{uid}/com.papertok.job_worker"

    try:
        # NOTE: Do NOT use -k here; it would kill the current worker and can leave a job stuck in "running".
        r = subprocess.run(
            ["/bin/launchctl", "kickstart", target],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"kick failed: {e}")

    if r.returncode != 0:
        msg = (r.stderr.strip() or r.stdout.strip() or "").strip()
        # Some launchctl versions return non-zero when the service is already running.
        if "already" not in msg.lower() and "in progress" not in msg.lower():
            raise HTTPException(
                status_code=500,
                detail=f"kick failed rc={r.returncode}: {msg}",
            )

    return {"ok": True, "target": target, "note": (r.stderr.strip() or r.stdout.strip() or None)}

    return {"ok": True, "target": target}


@router.get("/worker_logs/meta")
def api_worker_logs_meta(request: Request):
    _require_admin(request)

    logs_dir = Path(settings.log_dir)
    err = logs_dir / "job_worker.launchd.err.log"
    out = logs_dir / "job_worker.launchd.out.log"

    def stat(p: Path):
        if not p.exists():
            return None
        st = p.stat()
        return {
            "path": str(p),
            "size": int(st.st_size),
            "mtime": int(st.st_mtime),
        }

    return {"err": stat(err), "out": stat(out)}


@router.post("/worker_logs/truncate")
def api_worker_logs_truncate(request: Request):
    _require_admin(request)

    logs_dir = Path(settings.log_dir)
    err = logs_dir / "job_worker.launchd.err.log"
    out = logs_dir / "job_worker.launchd.out.log"

    for p in [err, out]:
        try:
            if p.exists() and p.is_file():
                p.write_text("", encoding="utf-8")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"truncate failed for {p}: {e}")

    return {"ok": True}
