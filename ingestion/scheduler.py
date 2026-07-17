"""Periodic scheduler for the live fetch job (APScheduler).

Runs fetch.run_fetch() every FETCH_INTERVAL_MINUTES (default 30), starting
with an immediate run. Any exception from a fetch cycle — including a
database that's unreachable — is caught and logged so the process keeps
running and simply retries on the next interval.

Run (from repo root, with .env populated):
    python -m ingestion.scheduler
"""
from __future__ import annotations

import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

from .config import FETCH_INTERVAL_MINUTES
from .fetch import run_fetch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _job() -> None:
    try:
        run_fetch()
    except Exception:
        # A single bad cycle (network blip, DB outage, bad payload) must not
        # kill the long-running scheduler process.
        logger.exception("Fetch job raised an unhandled exception; will retry next cycle")


def main() -> None:
    load_dotenv()
    scheduler = BackgroundScheduler()
    scheduler.add_job(_job, "interval", minutes=FETCH_INTERVAL_MINUTES)
    scheduler.start()
    logger.info("Scheduler started: fetch every %d minutes", FETCH_INTERVAL_MINUTES)

    _job()  # run once immediately on startup rather than waiting a full interval

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
