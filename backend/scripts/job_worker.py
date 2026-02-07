from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from sqlmodel import Session, select

from app.db.init_db import init_db
from app.db.engine import engine
from app.models.job import Job


PAPERTOK_ROOT = Path(__file__).resolve().parents[2]  # papertok/
BACKEND_DIR = PAPERTOK_ROOT / "backend"
DATA_DIR = PAPERTOK_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
LOCK_PATH = DATA_DIR / ".job_worker.lock"


SUPPORTED: dict[str, list[str]] = {
    # captions
    "image_caption_scoped": [
        str(BACKEND_DIR / ".venv" / "bin" / "python"),
        "-m",
        "scripts.job_handlers.image_caption",
    ],
    "image_caption_regen_scoped": [
        str(BACKEND_DIR / ".venv" / "bin" / "python"),
        "-m",
        "scripts.job_handlers.image_caption",
    ],

    # images
    "paper_images_glm_backfill": [
        "/bin/bash",
        str(PAPERTOK_ROOT / "ops" / "run_paper_images_glm_backfill.sh"),
    ],

    # paper_events
    "paper_events_backfill": [
        str(BACKEND_DIR / ".venv" / "bin" / "python"),
        "-m",
        "scripts.job_handlers.paper_events_backfill",
    ],

    # per-paper retry
    "paper_retry_stage": [
        str(BACKEND_DIR / ".venv" / "bin" / "python"),
        "-m",
        "scripts.job_handlers.paper_retry",
    ],
}


@contextmanager
def _file_lock(path: Path):
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    f = path.open("w")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()


def _now_utc() -> datetime:
    # Keep naive UTC for SQLite compatibility in this MVP.
    return datetime.utcnow()


def _mark_stale_running_jobs_failed(session: Session) -> None:
    stale_before = _now_utc() - timedelta(hours=12)
    stale = session.exec(
        select(Job)
        .where(Job.status == "running")
        .where(Job.started_at.is_not(None))
        .where(Job.started_at < stale_before)
        .order_by(Job.id.asc())
        .limit(5)
    ).all()

    for j in stale:
        j.status = "failed"
        j.error = ((j.error or "").strip() + "\n" if j.error else "") + "stale running job auto-failed by worker"
        j.finished_at = _now_utc()
        j.updated_at = _now_utc()
        session.add(j)

    if stale:
        session.commit()


def _claim_next_job(session: Session) -> tuple[int, str, Path] | None:
    """Atomically claim the next queued job (within this session) and mark running."""

    j = session.exec(
        select(Job)
        .where(Job.status == "queued")
        .order_by(Job.id.asc())
        .limit(1)
    ).first()
    if not j:
        return None

    job_id = int(j.id)
    job_type = str(j.job_type)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"job_{job_id}_{job_type}.log"

    j.status = "running"
    j.log_path = str(log_path)
    j.started_at = _now_utc()
    j.updated_at = _now_utc()

    session.add(j)
    session.commit()

    return job_id, job_type, log_path


def _finish_job(job_id: int, *, status: str, error: str | None = None) -> None:
    with Session(engine) as session:
        j = session.get(Job, job_id)
        if not j:
            return
        j.status = status
        j.error = error
        j.finished_at = _now_utc()
        j.updated_at = _now_utc()
        session.add(j)
        session.commit()


def _execute_job(job_id: int, job_type: str, log_path: Path) -> None:
    cmd = SUPPORTED.get(job_type)
    if not cmd:
        _finish_job(job_id, status="failed", error=f"unsupported job_type: {job_type}")
        return

    # For Python-based handlers, pass payload via a JSON file path to avoid quoting issues.
    payload_path = DATA_DIR / "jobs"
    payload_path.mkdir(parents=True, exist_ok=True)
    payload_file = payload_path / f"job_{job_id}.payload.json"

    if job_type in {"image_caption_scoped", "image_caption_regen_scoped", "paper_retry_stage"}:
        with Session(engine) as session:
            j = session.get(Job, job_id)
            payload = j.payload_json if j else None
        try:
            payload_file.write_text(payload or "{}", encoding="utf-8")
        except Exception:
            payload_file.write_text("{}", encoding="utf-8")

        cmd = cmd + ["--job-type", job_type, "--payload", str(payload_file)]

    rc = 1
    err: str | None = None

    try:
        with log_path.open("ab") as f:
            f.write(
                (
                    f"\n=== JOB {job_id} {job_type} START {datetime.now().isoformat()} ===\n"
                ).encode()
            )
            f.flush()

            env = os.environ.copy()
            env["PAPERTOK_LOG_PATH"] = str(log_path)

            p = subprocess.Popen(
                cmd,
                cwd=str(BACKEND_DIR),
                stdout=f,
                stderr=subprocess.STDOUT,
                env=env,
            )
            rc = p.wait()

            f.write(
                (
                    f"\n=== JOB {job_id} {job_type} END rc={rc} {datetime.now().isoformat()} ===\n"
                ).encode()
            )
            f.flush()

    except Exception as e:
        err = str(e)
        try:
            with log_path.open("ab") as f:
                f.write(
                    (
                        f"\n=== JOB {job_id} {job_type} EXCEPTION {datetime.now().isoformat()} ===\n{err}\n"
                    ).encode()
                )
        except Exception:
            pass

    if err:
        _finish_job(job_id, status="failed", error=err)
    elif rc == 0:
        _finish_job(job_id, status="success")
    else:
        _finish_job(job_id, status="failed", error=f"command exited with code {rc}")


def main(max_jobs: int = 3) -> None:
    init_db()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with _file_lock(LOCK_PATH):
        processed = 0
        while processed < max_jobs:
            with Session(engine) as session:
                _mark_stale_running_jobs_failed(session)
                claimed = _claim_next_job(session)

            if not claimed:
                return

            job_id, job_type, log_path = claimed
            _execute_job(job_id, job_type, log_path)
            processed += 1


if __name__ == "__main__":
    mj = 3
    if len(sys.argv) >= 2:
        try:
            mj = int(sys.argv[1])
        except Exception:
            pass
    main(max_jobs=mj)
