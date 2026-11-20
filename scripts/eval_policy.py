"""Reference-baseline comparison and delivery policy for Divination evals."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re


SCHEMA_VERSION = 1

DEFAULT_POLICY = {
    "block_on_regression": True,
    "block_on_incomplete": True,
    "block_on_new_case_failure": True,
    "max_limitation_score_drop": 0.1,
    "known_limitations": {},
}

_POLICY_KEYS = set(DEFAULT_POLICY)


def load_policy(path):
    """Load and validate a delivery policy JSON file."""
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError("Delivery policy must be a JSON object.")
    unknown = set(raw) - _POLICY_KEYS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"Unknown delivery policy keys: {names}")

    policy = dict(DEFAULT_POLICY)
    policy.update(raw)

    for key in (
        "block_on_regression",
        "block_on_incomplete",
        "block_on_new_case_failure",
    ):
        if not isinstance(policy[key], bool):
            raise ValueError(f"Policy field '{key}' must be a boolean.")

    max_drop = policy["max_limitation_score_drop"]
    if (
        not isinstance(max_drop, (int, float))
        or isinstance(max_drop, bool)
        or max_drop < 0
    ):
        raise ValueError(
            "Policy field 'max_limitation_score_drop' must be >= 0."
        )
    policy["max_limitation_score_drop"] = float(max_drop)

    limitations = policy["known_limitations"]
    if not isinstance(limitations, dict):
        raise ValueError("Policy field 'known_limitations' must be an object.")
    normalized_limitations = {}
    for case_name, entry in limitations.items():
        if not isinstance(entry, dict):
            raise ValueError(
                f"Known limitation '{case_name}' must be an object."
            )
        blocking = entry.get("blocking", False)
        if not isinstance(blocking, bool):
            raise ValueError(
                f"Known limitation '{case_name}.blocking' must be a boolean."
            )
        reason = entry.get("reason", "")
        if not isinstance(reason, str):
            raise ValueError(
                f"Known limitation '{case_name}.reason' must be a string."
            )
        normalized_limitations[case_name] = {
            "blocking": blocking,
            "reason": reason,
        }
    policy["known_limitations"] = normalized_limitations
    return policy


def _safe_filename(case_name):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", case_name).strip("._")
    return cleaned or "case"


def load_expected_case_names(dataset_path):
    """Return ordered unique case names from a golden dataset JSON file."""
    path = Path(dataset_path)
    if not path.exists():
        return []
    entries = json.loads(path.read_text())
    if not isinstance(entries, list):
        raise ValueError("Evaluation dataset must be a JSON list.")
    names = []
    seen_names = set()
    seen_files = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"Dataset entry {index} must be a JSON object.")
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"Dataset entry {index} must have a non-empty string 'name'."
            )
        if name in seen_names:
            raise ValueError(f"Duplicate evaluation case name: '{name}'.")
        safe = _safe_filename(name)
        if safe in seen_files:
            other = seen_files[safe]
            raise ValueError(
                f"Evaluation case names '{other}' and '{name}' collide on "
                f"result filename '{safe}.json'."
            )
        seen_names.add(name)
        seen_files[safe] = name
        names.append(name)
    return names


def collect_run_report(
    results_dir,
    *,
    suite,
    run_id,
    commit,
    expected_cases,
    deepeval_exit_code,
):
    """Consolidate per-case result JSON files into one run report."""
    directory = Path(results_dir)
    cases = {}
    if directory.exists():
        for file_path in sorted(directory.glob("*.json")):
            if file_path.name.startswith("."):
                continue
            record = json.loads(file_path.read_text())
            name = record.get("name")
            if isinstance(name, str) and name:
                cases[name] = record

    for case_name in expected_cases:
        if case_name not in cases:
            cases[case_name] = {
                "name": case_name,
                "status": "incomplete",
                "error": "Case did not produce an evaluation result.",
                "metrics": [],
            }

    return {
        "schema_version": SCHEMA_VERSION,
        "suite": suite,
        "run_id": run_id,
        "commit": commit,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "deepeval_exit_code": deepeval_exit_code,
        "cases": cases,
    }


def _case_is_incomplete(case_record):
    if not isinstance(case_record, dict):
        return True
    if case_record.get("status") not in ("passed", "failed"):
        return True
    if case_record.get("error"):
        return True
    metrics = case_record.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        return True
    for metric in metrics:
        if not isinstance(metric, dict):
            return True
        if metric.get("error"):
            return True
        if metric.get("status") in ("error", "incomplete"):
            return True
        if not isinstance(metric.get("success"), bool):
            return True
    return False


def _metric_deltas(candidate_metrics, baseline_metrics):
    baseline_scores = {}
    for metric in baseline_metrics or []:
        name = metric.get("name")
        score = metric.get("score")
        if (
            isinstance(name, str)
            and isinstance(score, (int, float))
            and not isinstance(score, bool)
        ):
            baseline_scores[name] = float(score)

    deltas = {}
    for metric in candidate_metrics or []:
        name = metric.get("name")
        score = metric.get("score")
        if (
            isinstance(name, str)
            and isinstance(score, (int, float))
            and not isinstance(score, bool)
            and name in baseline_scores
        ):
            deltas[name] = round(float(score) - baseline_scores[name], 4)
    return deltas


def _worsened_metrics(deltas, max_drop):
    return {
        name: delta
        for name, delta in deltas.items()
        if delta < -(max_drop + 1e-9)
    }


def _newly_failing_metrics(candidate_metrics, baseline_metrics):
    baseline_pass = {
        metric.get("name"): metric.get("success")
        for metric in (baseline_metrics or [])
        if isinstance(metric, dict) and isinstance(metric.get("name"), str)
    }
    regressed = []
    for metric in candidate_metrics or []:
        if not isinstance(metric, dict):
            continue
        name = metric.get("name")
        if (
            isinstance(name, str)
            and baseline_pass.get(name) is True
            and metric.get("success") is False
        ):
            regressed.append(name)
    return sorted(regressed)


def report_has_incomplete_cases(report):
    """Return True when any case in a saved report is incomplete."""
    cases = report.get("cases", {})
    if not isinstance(cases, dict) or not cases:
        return True
    return any(_case_is_incomplete(record) for record in cases.values())


def compare_and_decide(candidate_report, baseline_report, policy):
    """Compare a candidate run against a baseline and apply delivery policy."""
    candidate_cases = candidate_report.get("cases", {})
    baseline_cases = (
        baseline_report.get("cases", {})
        if isinstance(baseline_report, dict)
        else {}
    )
    limitations = policy["known_limitations"]
    max_drop = policy["max_limitation_score_drop"]

    summary = {
        "still_passing": 0,
        "potential_regression": 0,
        "improvement_observed": 0,
        "continuing_limitation": 0,
        "new_case": 0,
        "incomplete_assessment": 0,
        "removed_cases": 0,
    }
    blocking_reasons = []
    non_blocking_notices = []
    case_details = {}

    if baseline_report is None:
        non_blocking_notices.append(
            {
                "case": None,
                "category": "no_baseline",
                "message": (
                    "No reference baseline found; evaluating each case "
                    "against its own criteria."
                ),
            }
        )

    for name in sorted(candidate_cases):
        candidate = candidate_cases[name]
        baseline = baseline_cases.get(name)
        limitation = limitations.get(name)
        non_blocking_limitation = (
            limitation is not None and not limitation["blocking"]
        )
        deltas = (
            _metric_deltas(
                candidate.get("metrics"),
                baseline.get("metrics") if baseline else [],
            )
            if baseline is not None
            else {}
        )

        if _case_is_incomplete(candidate):
            category = "incomplete_assessment"
            summary[category] += 1
            reason = (
                candidate.get("error")
                or "One or more metrics did not produce a complete verdict."
            )
            entry = {
                "case": name,
                "category": category,
                "message": reason,
            }
            if policy["block_on_incomplete"]:
                blocking_reasons.append(entry)
            else:
                non_blocking_notices.append(entry)
            case_details[name] = {
                "category": category,
                "candidate_status": "incomplete",
                "baseline_status": (
                    baseline.get("status") if baseline else None
                ),
                "metric_deltas": deltas,
                "blocking": policy["block_on_incomplete"],
                "message": reason,
            }
            continue

        cand_status = candidate["status"]
        has_valid_baseline = (
            baseline is not None and not _case_is_incomplete(baseline)
        )

        if has_valid_baseline:
            base_status = baseline["status"]
            if base_status == "passed" and cand_status == "passed":
                category = "still_passing"
                summary[category] += 1
                case_details[name] = {
                    "category": category,
                    "candidate_status": cand_status,
                    "baseline_status": base_status,
                    "metric_deltas": deltas,
                    "blocking": False,
                }
            elif base_status == "passed" and cand_status == "failed":
                category = "potential_regression"
                summary[category] += 1
                entry = {
                    "case": name,
                    "category": category,
                    "message": (
                        "Passed in reference baseline but failed in candidate."
                    ),
                }
                if policy["block_on_regression"]:
                    blocking_reasons.append(entry)
                else:
                    non_blocking_notices.append(entry)
                case_details[name] = {
                    "category": category,
                    "candidate_status": cand_status,
                    "baseline_status": base_status,
                    "metric_deltas": deltas,
                    "blocking": policy["block_on_regression"],
                }
            elif base_status == "failed" and cand_status == "passed":
                category = "improvement_observed"
                summary[category] += 1
                if limitation is not None:
                    non_blocking_notices.append(
                        {
                            "case": name,
                            "category": "resolved_limitation",
                            "message": (
                                "Case passed; once accepted, re-record the "
                                "reference baseline (record-baseline) and "
                                "remove it from known_limitations in "
                                "policy.json."
                            ),
                        }
                    )
                else:
                    non_blocking_notices.append(
                        {
                            "case": name,
                            "category": "update_baseline",
                            "message": (
                                "Case passed; once accepted, re-record the "
                                "reference baseline (record-baseline) so "
                                "future runs protect this improvement."
                            ),
                        }
                    )
                case_details[name] = {
                    "category": category,
                    "candidate_status": cand_status,
                    "baseline_status": base_status,
                    "metric_deltas": deltas,
                    "blocking": False,
                }
            else:
                category = "continuing_limitation"
                summary[category] += 1
                newly_failing = _newly_failing_metrics(
                    candidate.get("metrics"),
                    baseline.get("metrics"),
                )
                worsened = _worsened_metrics(deltas, max_drop)
                if newly_failing:
                    metric_list = ", ".join(newly_failing)
                    message = (
                        "Previously passing metric(s) now failed on a "
                        f"continuing-limitation case: {metric_list}."
                    )
                    entry = {
                        "case": name,
                        "category": "continuing_limitation_metric_regression",
                        "message": message,
                    }
                    if policy["block_on_regression"]:
                        blocking_reasons.append(entry)
                        blocked = True
                    else:
                        non_blocking_notices.append(entry)
                        blocked = False
                elif worsened:
                    drops = ", ".join(
                        f"{metric} ({delta:+.2f})"
                        for metric, delta in sorted(worsened.items())
                    )
                    message = (
                        "Continuing limitation worsened beyond tolerance "
                        f"({max_drop:.2f}): {drops}."
                    )
                    blocking_reasons.append(
                        {
                            "case": name,
                            "category": "continuing_limitation_worsened",
                            "message": message,
                        }
                    )
                    blocked = True
                elif non_blocking_limitation:
                    reason = limitation["reason"] or "Declared non-blocking."
                    non_blocking_notices.append(
                        {
                            "case": name,
                            "category": category,
                            "message": f"Non-blocking limitation: {reason}",
                        }
                    )
                    blocked = False
                else:
                    if limitation is not None:
                        message = (
                            "Known limitation is marked blocking: "
                            f"{limitation['reason'] or 'fix required.'}"
                        )
                    else:
                        message = (
                            "Continuing failure is not declared as a "
                            "non-blocking known limitation in policy.json."
                        )
                    blocking_reasons.append(
                        {
                            "case": name,
                            "category": category,
                            "message": message,
                        }
                    )
                    blocked = True
                case_details[name] = {
                    "category": category,
                    "candidate_status": cand_status,
                    "baseline_status": base_status,
                    "metric_deltas": deltas,
                    "newly_failing_metrics": newly_failing,
                    "worsened_metrics": worsened,
                    "blocking": blocked,
                }
        else:
            category = "new_case"
            summary[category] += 1
            blocked = False
            if cand_status == "failed":
                if non_blocking_limitation:
                    reason = limitation["reason"] or "Declared non-blocking."
                    non_blocking_notices.append(
                        {
                            "case": name,
                            "category": "known_limitation",
                            "message": f"Non-blocking limitation: {reason}",
                        }
                    )
                elif policy["block_on_new_case_failure"]:
                    blocking_reasons.append(
                        {
                            "case": name,
                            "category": "new_case_failure",
                            "message": (
                                "Case without baseline failed its criteria."
                            ),
                        }
                    )
                    blocked = True
                else:
                    non_blocking_notices.append(
                        {
                            "case": name,
                            "category": "new_case_failure",
                            "message": (
                                "Case without baseline failed (non-blocking "
                                "by policy)."
                            ),
                        }
                    )
            case_details[name] = {
                "category": category,
                "candidate_status": cand_status,
                "baseline_status": (
                    baseline.get("status") if baseline else None
                ),
                "metric_deltas": deltas,
                "blocking": blocked,
            }

    removed_cases = sorted(set(baseline_cases) - set(candidate_cases))
    summary["removed_cases"] = len(removed_cases)
    for name in removed_cases:
        non_blocking_notices.append(
            {
                "case": name,
                "category": "removed_case",
                "message": "Present in reference baseline but absent now.",
            }
        )

    return {
        "allow_delivery": not blocking_reasons,
        "suite": candidate_report.get("suite"),
        "candidate_commit": candidate_report.get("commit"),
        "baseline_commit": (
            baseline_report.get("commit")
            if isinstance(baseline_report, dict)
            else None
        ),
        "summary": summary,
        "blocking_reasons": blocking_reasons,
        "non_blocking_notices": non_blocking_notices,
        "removed_cases": removed_cases,
        "cases": case_details,
    }


def format_report(decision):
    """Render a concise human-readable summary of a delivery decision."""
    verdict = "ALLOW" if decision["allow_delivery"] else "BLOCK"
    summary = decision["summary"]
    lines = [
        f"Evaluation delivery policy: {verdict}",
        (
            "Suite: "
            f"{decision.get('suite') or 'unknown'} | "
            f"Candidate: {decision.get('candidate_commit') or 'uncommitted'} | "
            f"Baseline: {decision.get('baseline_commit') or 'none'}"
        ),
        (
            "Summary: "
            f"still_passing={summary['still_passing']}, "
            f"potential_regression={summary['potential_regression']}, "
            f"improvement_observed={summary['improvement_observed']}, "
            f"continuing_limitation={summary['continuing_limitation']}, "
            f"new_case={summary['new_case']}, "
            f"incomplete_assessment={summary['incomplete_assessment']}, "
            f"removed_cases={summary['removed_cases']}"
        ),
    ]
    if decision["blocking_reasons"]:
        lines.append("Blocking findings:")
        for item in decision["blocking_reasons"]:
            prefix = f"{item['case']}: " if item.get("case") else ""
            lines.append(
                f"  - [{item['category']}] {prefix}{item['message']}"
            )
    if decision["non_blocking_notices"]:
        lines.append("Non-blocking notices:")
        for item in decision["non_blocking_notices"]:
            prefix = f"{item['case']}: " if item.get("case") else ""
            lines.append(
                f"  - [{item['category']}] {prefix}{item['message']}"
            )
    return "\n".join(lines)
