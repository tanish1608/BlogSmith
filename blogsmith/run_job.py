"""Cloud Run Job entrypoint.

Executes a single run's Phase A in a fresh container. The API service dispatches
the job with RUN_UID / RUN_SITE_ID / RUN_ID env overrides; the job runs the
pipeline to the email gate (or completion) and exits. Results are already in
Firestore, so a crash never loses progress.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from blogsmith.firestore_db import init_firebase
from blogsmith.runner import execute_run

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> int:
    uid = os.environ.get("RUN_UID")
    site_id = os.environ.get("RUN_SITE_ID")
    run_id = os.environ.get("RUN_ID")
    if not (uid and site_id and run_id):
        logger.error("RUN_UID, RUN_SITE_ID and RUN_ID must all be set.")
        return 2

    init_firebase()
    logger.info("Executing run %s (site %s, user %s)", run_id, site_id, uid)
    asyncio.run(execute_run(uid, site_id, run_id))
    logger.info("Run %s phase-A complete.", run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
