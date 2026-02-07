from __future__ import annotations

from fastapi import APIRouter

from app.services.status_service import get_status_snapshot

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status")
def get_status(limit: int = 50):
    """Public status endpoint (safe for public exposure).

    MUST NOT include local absolute paths or operational log paths.
    """

    return get_status_snapshot(limit=limit, include_sensitive=False)


@router.get("/public/status")
def get_public_status(limit: int = 50):
    """Alias for public status (explicit naming)."""

    return get_status_snapshot(limit=limit, include_sensitive=False)
