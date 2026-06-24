from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Compatibility hook for migration jobs.

    Lora AI schema is managed by Alembic. Some shared Opslora Helm migration
    jobs still invoke ``python -m app.init_db`` after ``alembic upgrade head``;
    keep this command idempotent so those jobs do not fail with ModuleNotFound.
    """
    logger.info("No app.init_db work required; schema is managed by Alembic.")


if __name__ == "__main__":
    init_db()
