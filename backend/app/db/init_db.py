from sqlmodel import SQLModel
from sqlalchemy import text

from app.db.engine import engine
from app.db.migrate import migrate_db

# Ensure models are registered in SQLModel metadata
from app.models.paper import Paper  # noqa: F401
from app.models.paper_image import PaperImage  # noqa: F401
from app.models.app_setting import AppSetting  # noqa: F401
from app.models.job import Job  # noqa: F401
from app.models.paper_event import PaperEvent  # noqa: F401


def _ensure_sqlite_columns() -> None:
    """Very small SQLite 'migration' helper for local MVP.

    SQLModel won't auto-migrate existing tables. We add new nullable columns
    when missing so local dev doesn't need manual DB resets.
    """

    if engine.url.get_backend_name() != "sqlite":
        return

    with engine.connect() as conn:
        cols = conn.execute(text("PRAGMA table_info(papers)")).fetchall()
        existing = {row[1] for row in cols}  # (cid, name, type, ...)

        # name -> SQL type
        needed = {
            "day": "VARCHAR",
            "pdf_url": "VARCHAR",
            "pdf_path": "VARCHAR",
            "pdf_sha256": "VARCHAR",
            "thumbnail_url": "VARCHAR",
            "content_explain_cn": "TEXT",
            "image_captions_json": "TEXT",
            # EPUB
            "epub_path_en": "VARCHAR",
            "epub_url_en": "VARCHAR",
            "epub_path_zh": "VARCHAR",
            "epub_url_zh": "VARCHAR",
            "epub_path_bilingual": "VARCHAR",
            "epub_url_bilingual": "VARCHAR",
        }

        for name, sql_type in needed.items():
            if name in existing:
                continue
            conn.execute(text(f"ALTER TABLE papers ADD COLUMN {name} {sql_type}"))
        conn.commit()


def _ensure_sqlite_indexes() -> None:
    """Small SQLite helper for index evolution.

    NOTE: This helper must not fight Alembic migrations.
    We keep it as a safety net for local MVP DBs, but align it with the latest schema.
    """

    if engine.url.get_backend_name() != "sqlite":
        return

    with engine.connect() as conn:
        # Drop legacy/obsolete indexes (pre-bilingual)
        conn.execute(text("DROP INDEX IF EXISTS idx_paper_images_paper_kind_order"))
        conn.execute(text("DROP INDEX IF EXISTS idx_paper_images_paper_kind_provider_order"))

        # Ensure the lang-aware unique index exists
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_images_paper_kind_provider_lang_order "
                "ON paper_images (paper_id, kind, provider, lang, order_idx)"
            )
        )

        # Helpful non-unique index
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_paper_images_lang ON paper_images (lang)"))

        conn.commit()


def _ensure_schema_version() -> None:
    if engine.url.get_backend_name() != "sqlite":
        return

    # Minimal forward-compat: track a single integer schema version.
    # (We still use PRAGMA checks for now; this is for future migration tooling.)
    SCHEMA_VERSION = 1

    from datetime import datetime

    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_version ("
                "id INTEGER PRIMARY KEY CHECK(id=1), "
                "version INTEGER NOT NULL, "
                "updated_at TEXT NOT NULL"
                ")"
            )
        )
        row = conn.execute(text("SELECT version FROM schema_version WHERE id=1")).fetchone()
        now = datetime.now().isoformat(timespec="seconds")
        if not row:
            conn.execute(
                text("INSERT INTO schema_version (id, version, updated_at) VALUES (1, :v, :t)"),
                {"v": SCHEMA_VERSION, "t": now},
            )
        else:
            # Always bump to current version (monotonic)
            cur = int(row[0] or 0)
            if cur < SCHEMA_VERSION:
                conn.execute(
                    text("UPDATE schema_version SET version=:v, updated_at=:t WHERE id=1"),
                    {"v": SCHEMA_VERSION, "t": now},
                )
        conn.commit()


def init_db() -> None:
    # Alembic migrations (authoritative going forward)
    migrated = False
    try:
        migrate_db()
        migrated = True
    except Exception as e:
        # Fallback: do not brick the service in MVP mode.
        print(f"WARN: migrate_db failed, falling back to create_all: {e}")

    # Legacy safety net (kept during transition)
    # IMPORTANT: When migrations are working, do NOT create tables from metadata here;
    # otherwise new models may create tables outside Alembic.
    if not migrated:
        SQLModel.metadata.create_all(engine)

    _ensure_sqlite_columns()
    _ensure_sqlite_indexes()
    _ensure_schema_version()
