from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine_kwargs = {
    "pool_pre_ping": settings.database_pool_pre_ping,
}
if not settings.database_url.startswith("sqlite"):
    engine_kwargs.update(
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_recycle=settings.database_pool_recycle_seconds,
    )
else:
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def initialize_sqlite_schema_if_needed() -> None:
    """Create the metadata schema for temporary SQLite deployments.

    Normal shared database environments are managed by Alembic. Some temporary
    test deployments use ``sqlite:////tmp/lora_ai.db`` through Key Vault; in
    that case the migration Job and app pod do not share a filesystem, so the
    app process must ensure its own SQLite file has the baseline tables before
    knowledge ingestion/chat writes run.
    """
    if not settings.database_url.startswith("sqlite"):
        return

    # Import models so SQLAlchemy registers all table metadata before create_all.
    import app.models.ai  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
