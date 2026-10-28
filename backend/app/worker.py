"""Single-process worker. Run more instances safely; PostgreSQL leases coordinate ownership."""

import argparse
import asyncio
import logging
import signal
import time

from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure.config import get_settings
from app.infrastructure.db import SessionLocal
from app.infrastructure.notifications import Notifications
from app.orchestration.store import TaskStore
from app.orchestration.workflow import execute_claim

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Mock-only durable research worker")
    parser.add_argument("--once", action="store_true", help="Claim at most one available task and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    store = TaskStore(SessionLocal, settings)
    notifications = Notifications(settings.redis_url)
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    logger.info("Mock worker started; database polling enabled")
    while not stopping:
        try:
            claim = store.claim()
            if claim:
                logger.info("Executing mock task %s attempt %s", claim.task_id, claim.attempt)
                asyncio.run(execute_claim(store, claim))
            elif not args.once:
                if not notifications.wait():
                    time.sleep(settings.poll_seconds)
        except SQLAlchemyError:
            # Do not log connection strings or arbitrary exception messages.
            logger.error("DATABASE_UNAVAILABLE; worker will poll again")
            if not args.once:
                time.sleep(settings.poll_seconds)
        if args.once:
            break


if __name__ == "__main__":
    main()
