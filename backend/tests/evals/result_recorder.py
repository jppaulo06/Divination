"""Record structured per-attempt evaluation outcomes for CI comparison.

When ``EVAL_RESULTS_DIR`` is set, each evaluation test writes one JSON file per
attempt, so a case repeated with ``--repeat`` keeps every attempt and
``scripts/eval_policy.py`` can count passes against the committed reference.
Incomplete assessments are recorded too, even when DeepEval runs with
``--ignore-errors`` or ``--skip-on-missing-params``. When the variable is
unset, recording is a no-op and direct ``deepeval test run`` invocations keep
their standard behavior.

``EVAL_CASES`` (comma-separated case names) restricts a run to those cases.
"""

import json
import os
from pathlib import Path
import re
import uuid


def select_cases(goldens):
    """The goldens named in ``EVAL_CASES``, or all of them when it is unset."""
    raw = os.environ.get("EVAL_CASES")
    if not raw:
        return goldens
    wanted = {name.strip() for name in raw.split(",") if name.strip()}
    unknown = wanted - {golden.get("name") for golden in goldens}
    if unknown:
        raise ValueError(
            "EVAL_CASES names unknown cases: " + ", ".join(sorted(unknown))
        )
    return [golden for golden in goldens if golden.get("name") in wanted]


def _results_dir():
    raw = os.environ.get("EVAL_RESULTS_DIR")
    if not raw:
        return None
    directory = Path(raw)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _safe_filename(case_name):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", case_name).strip("._")
    return cleaned or "case"


def _write_case_record(record):
    directory = _results_dir()
    if directory is None:
        return
    # One file per attempt: repeated attempts of a case never overwrite each
    # other.
    filename = f"{_safe_filename(record['name'])}.{uuid.uuid4().hex[:12]}.json"
    target = directory / filename
    temporary = directory / f".{filename}.{os.getpid()}.tmp"
    temporary.write_text(json.dumps(record, indent=2) + "\n")
    temporary.replace(target)


def reset_metrics(metrics):
    """Clear state on shared metric instances before evaluating a new case."""
    for metric in metrics:
        for attr in ("score", "success", "error", "reason"):
            if hasattr(metric, attr):
                setattr(metric, attr, None)


def _metric_name(metric):
    name = getattr(metric, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return metric.__class__.__name__


def _snapshot_metrics(metrics):
    snapshots = []
    for metric in metrics:
        raw_score = getattr(metric, "score", None)
        score = (
            float(raw_score)
            if isinstance(raw_score, (int, float))
            and not isinstance(raw_score, bool)
            else None
        )
        raw_threshold = getattr(metric, "threshold", None)
        threshold = (
            float(raw_threshold)
            if isinstance(raw_threshold, (int, float))
            and not isinstance(raw_threshold, bool)
            else None
        )
        raw_success = getattr(metric, "success", None)
        success = raw_success if isinstance(raw_success, bool) else None
        raw_error = getattr(metric, "error", None)
        error = str(raw_error) if raw_error else None
        # The judge's explanation, kept so a failed case can be read later.
        raw_reason = getattr(metric, "reason", None)
        reason = str(raw_reason) if raw_reason else None

        if error is not None:
            status = "error"
        elif success is None:
            status = "incomplete"
        elif success:
            status = "passed"
        else:
            status = "failed"

        snapshots.append(
            {
                "name": _metric_name(metric),
                "score": score,
                "threshold": threshold,
                "success": success,
                "status": status,
                "error": error,
                "reason": reason,
            }
        )
    return snapshots


def record_execution_error(case_name, error_message):
    """Record a case that failed before DeepEval metrics could run."""
    _write_case_record(
        {
            "name": case_name,
            "status": "incomplete",
            "error": str(error_message),
            "metrics": [],
        }
    )


def run_and_record(case_name, test_case, metrics, assert_fn):
    """Run ``assert_fn`` synchronously and persist per-metric outcomes.

    DeepEval's default ``run_async=True`` scores internal copies of the metric
    objects, leaving the caller's instances with ``score=None``. Passing
    ``run_async=False`` executes on the original instances so their verdicts
    can be captured accurately.
    """
    reset_metrics(metrics)
    unexpected_error = None
    try:
        assert_fn(test_case=test_case, metrics=metrics, run_async=False)
    except AssertionError:
        raise
    except Exception as error:
        unexpected_error = str(error)
        raise
    finally:
        snapshots = _snapshot_metrics(metrics)
        if unexpected_error is not None or not snapshots:
            status = "incomplete"
        elif any(
            item["status"] in ("error", "incomplete") for item in snapshots
        ):
            status = "incomplete"
        elif all(item["status"] == "passed" for item in snapshots):
            status = "passed"
        else:
            status = "failed"

        _write_case_record(
            {
                "name": case_name,
                "status": status,
                "error": unexpected_error,
                "metrics": snapshots,
            }
        )
