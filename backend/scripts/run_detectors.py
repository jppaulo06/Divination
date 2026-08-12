#!/usr/bin/env python3
"""Re-run detectors over stored interactions.

Use after adding a detector or bumping one's version; existing signals are
left alone, so repeating it is safe.

    python scripts/run_detectors.py
    python scripts/run_detectors.py --summary
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from project.adapters.monitoring.CandidateQuery import (  # noqa: E402
    CandidateQuery,
)
from project.adapters.monitoring.Database import (  # noqa: E402
    MonitoringDatabase,
)
from project.adapters.monitoring.DetectorRunner import (  # noqa: E402
    DetectorRunner,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--summary",
        action="store_true",
        help="only print signal counts, without running detectors",
    )
    args = parser.parse_args()

    database = MonitoringDatabase(args.database_url)
    database.create_schema()

    if not args.summary:
        written = DetectorRunner(database).backfill(limit=args.limit)
        print(f"new signals: {written}")

    summary = CandidateQuery(database).summary()
    print(f"interactions:       {summary['interactions']}")
    print(f"pending candidates: {summary['pending_candidates']}")
    for signal_type, count in sorted(summary["signals_by_type"].items()):
        print(f"  {signal_type}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
