from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from app.core.config import settings
from app.db.engine import engine
from app.services.app_config import (
    default_app_config,
    get_db_app_config,
    get_effective_app_config,
    set_db_app_config,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


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


@router.get("/config")
def get_config(request: Request, session: Session = Depends(get_session)):
    _require_admin(request)

    defaults = default_app_config().model_dump()
    db_cfg = get_db_app_config(session)
    effective = get_effective_app_config(session).model_dump()

    return {
        "defaults": defaults,
        "db": db_cfg,
        "effective": effective,
        "meta": {
            "admin_token_required": bool((settings.admin_token or "").strip()),
            "editable": list(defaults.keys()),
        },
    }


@router.put("/config")
def put_config(payload: dict, request: Request, session: Session = Depends(get_session)):
    _require_admin(request)

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid payload")

    # Only allow known keys (prevent writing arbitrary garbage)
    allowed = set(default_app_config().model_dump().keys())
    patch = {k: v for k, v in payload.items() if k in allowed}

    if not patch:
        raise HTTPException(status_code=400, detail="no valid keys in payload")

    saved = set_db_app_config(session, patch)
    effective = get_effective_app_config(session).model_dump()

    return {
        "saved": saved,
        "effective": effective,
    }
