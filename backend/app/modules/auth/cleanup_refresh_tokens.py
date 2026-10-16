"""Bounded cleanup for refresh-token records past the reuse-detection window."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db import models as _models  # noqa: F401 - register all ORM relationships
from app.db.session import SessionLocal
from app.modules.auth.models import RefreshToken

logger = logging.getLogger(__name__)

RETENTION_DAYS = 30
DEFAULT_BATCH_SIZE = 500
MAX_BATCH_SIZE = 5_000


@dataclass(frozen=True)
class CleanupResult:
    eligible_count: int
    deleted_count: int
    batch_count: int
    dry_run: bool


def cleanup_expired_refresh_tokens(
    sessions: sessionmaker[Session],
    *,
    dry_run: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
    now: datetime | None = None,
) -> CleanupResult:
    """Delete rows expired beyond the retention window, committing each bounded batch."""
    if not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise ValueError(f"batch_size must be between 1 and {MAX_BATCH_SIZE}")

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RETENTION_DAYS)
    eligible_filter = RefreshToken.expires_at < cutoff

    with sessions() as session:
        eligible_count = session.scalar(
            select(func.count()).select_from(RefreshToken).where(eligible_filter)
        ) or 0

    if dry_run or eligible_count == 0:
        return CleanupResult(eligible_count, 0, 0, dry_run)

    deleted_count = 0
    batch_count = 0
    while True:
        with sessions() as session:
            with session.begin():
                eligible_ids = (
                    select(RefreshToken.id)
                    .where(eligible_filter)
                    .order_by(RefreshToken.expires_at, RefreshToken.id)
                    .limit(batch_size)
                )
                result = session.execute(
                    delete(RefreshToken).where(RefreshToken.id.in_(eligible_ids))
                )
                deleted_this_batch = max(result.rowcount or 0, 0)

        if deleted_this_batch == 0:
            break
        deleted_count += deleted_this_batch
        batch_count += 1
        if deleted_this_batch < batch_size:
            break

    logger.info(
        "refresh_token_cleanup_complete deleted_count=%d batch_count=%d retention_days=%d",
        deleted_count,
        batch_count,
        RETENTION_DAYS,
    )
    return CleanupResult(eligible_count, deleted_count, batch_count, False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Count eligible rows without deleting them")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Maximum rows per transaction (1-{MAX_BATCH_SIZE}; default {DEFAULT_BATCH_SIZE})",
    )
    args = parser.parse_args()

    result = cleanup_expired_refresh_tokens(
        SessionLocal,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
    )
    action = "would_delete" if result.dry_run else "deleted"
    action_count = result.eligible_count if result.dry_run else result.deleted_count
    print(
        f"refresh_token_cleanup eligible_count={result.eligible_count} "
        f"{action}_count={action_count} "
        f"batch_count={result.batch_count} retention_days={RETENTION_DAYS}"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
