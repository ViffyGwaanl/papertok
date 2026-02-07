from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.config import settings
from app.db.engine import engine


PAPERTOK_ROOT = Path(__file__).resolve().parents[3]  # papertok/
BACKEND_DIR = PAPERTOK_ROOT / "backend"
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
LOCK_PATH = PAPERTOK_ROOT / "data" / ".db_migrate.lock"


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


def _table_exists(conn, name: str) -> bool:
    if engine.url.get_backend_name() != "sqlite":
        # generic fallback
        r = conn.execute(text("SELECT 1"))
        _ = r
        return True

    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": name},
    ).fetchone()
    return bool(row)


def _has_any_user_tables(conn) -> bool:
    if engine.url.get_backend_name() != "sqlite":
        return True

    rows = conn.execute(
        text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ).fetchall()
    # ignore alembic_version itself
    names = {r[0] for r in rows}
    names.discard("alembic_version")
    return len(names) > 0


def _alembic_cfg() -> Config:
    cfg = Config(str(ALEMBIC_INI))
    # env.py will override to settings.db_url anyway, but keep consistent.
    cfg.set_main_option("sqlalchemy.url", settings.db_url)
    return cfg


def migrate_db() -> None:
    """Migrate to Alembic head.

    Transition logic for existing local DBs:
    - If DB already has tables but has never had Alembic tracking, we stamp head.
    - If DB is empty, we run upgrade head (creates tables).
    - If already tracked, we run upgrade head.

    This function is safe to call from server + jobs + scripts.
    """

    with _file_lock(LOCK_PATH):
        cfg = _alembic_cfg()

        with engine.connect() as conn:
            has_av = _table_exists(conn, "alembic_version")
            has_tables = _has_any_user_tables(conn)

        if not has_av and has_tables:
            # Existing DB from pre-Alembic era: assume it matches the initial schema,
            # then apply newer migrations (e.g. paper_events).
            command.stamp(cfg, "4b07fddd60af")
            command.upgrade(cfg, "head")
            return

        # New DB (or already tracked): apply migrations.
        command.upgrade(cfg, "head")
