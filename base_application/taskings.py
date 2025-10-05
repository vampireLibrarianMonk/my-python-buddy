# Native
import os
from concurrent.futures import ThreadPoolExecutor

from base_application.analyzers import run_bandit_analyzer

# Django
from base_application.models import Run

# Calculate workers: CPU cores - 2, but at least 1
max_workers = max(1, (os.cpu_count() or 1) - 2)

# Global thread pool (auto-adjusted)
executor = ThreadPoolExecutor(max_workers=max_workers)


def run_analyzer_task(run_id, analyzer):
    run = Run.objects.get(id=run_id)

    # Start with Pending
    run.status = "PENDING"

    # Analyzer assignment
    if analyzer == "bandit":
        run_bandit_analyzer(run)
    else:
        # Fallback for unknown analyzers
        run.status = "ERRORED"
        run.save(update_fields=["status"])
