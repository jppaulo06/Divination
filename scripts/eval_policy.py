"""Per-case comparison with a committed reference, and the delivery policy.

The reference (``backend/tests/evals/baselines/<suite>.json``) stores, for
each case, how many attempts passed when the accepted version of the
application was evaluated many times. A developer rebuilds it by hand and
commits it, so accepting new behavior is always an explicit, reviewed change.

A run is judged case by case. Each case runs once; if that attempt fails and
the case passes often enough in its reference for a decline to be provable,
it becomes a *suspect* and gets extra attempts. The pooled attempts are then
compared with the reference with a one-sided Fisher exact test: "if this
case's pass rate had not changed, how likely would this many failures be?"
Below ``regression_below`` the case is a confirmed *regression*. The policy
blocks only on a confirmed regression or on missing evidence (an incomplete
attempt, or a case without a reference). Everything else is reported.
"""

import json
from math import comb
import os
from pathlib import Path
import re
import sys


SCHEMA_VERSION = 2

DEFAULT_POLICY = {
    # Attempts per case when the reference is rebuilt.
    "baseline_attempts": 20,
    # Extra attempts for a case whose first attempt failed, before it can block.
    "confirmation_attempts": 5,
    # Pooled attempts less likely than this under an unchanged pass rate are a
    # confirmed regression. With 20 reference attempts and 6 pooled attempts,
    # 0.01 falsely blocks a case at most ~0.3% of the time (about one false
    # block per 40 pull requests for this suite), while a case that stops
    # passing is always caught.
    "regression_below": 0.01,
    # Rebuild report: a case whose new reference differs from the previous one
    # with less likelihood than this is listed as worse or improved.
    "change_below": 0.05,
}

BLOCKING_VERDICTS = ("regression", "no_reference", "incomplete")


# ---------------------------------------------------------------- settings


def _worst_case_p_value(reference, pooled_attempts):
    """The p-value if every pooled attempt failed: the strongest evidence a
    confirmation could produce against this reference."""
    return decline_p_value(reference, {"passed": 0, "attempts": pooled_attempts})


def load_policy(path):
    """Load and validate a delivery policy JSON file."""
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError("Delivery policy must be a JSON object.")
    unknown = set(raw) - set(DEFAULT_POLICY)
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"Unknown delivery policy keys: {names}")

    policy = {**DEFAULT_POLICY, **raw}
    for key in ("baseline_attempts", "confirmation_attempts"):
        value = policy[key]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"Policy field '{key}' must be a positive integer.")
    for key in ("regression_below", "change_below"):
        value = policy[key]
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not 0 < value < 1
        ):
            raise ValueError(f"Policy field '{key}' must be between 0 and 1.")
        policy[key] = float(value)
    perfect = {
        "passed": policy["baseline_attempts"],
        "attempts": policy["baseline_attempts"],
    }
    pooled = 1 + policy["confirmation_attempts"]
    if _worst_case_p_value(perfect, pooled) >= policy["regression_below"]:
        raise ValueError(
            "Policy fields 'baseline_attempts' and 'confirmation_attempts' are "
            "too small: even a case that always passed and now fails every "
            "attempt could not be confirmed below 'regression_below'."
        )
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
                f"result filename '{safe}'."
            )
        seen_names.add(name)
        seen_files[safe] = name
        names.append(name)
    return names


# ---------------------------------------------------------------- attempts


def collect_attempts(results_dir, expected_cases):
    """Group a run's attempt files by case, keeping the dataset's order.

    The recorder writes one JSON file per attempt; a case with no file has no
    attempts and is judged as missing evidence. Only ``expected_cases`` are
    collected.
    """
    attempts = {name: [] for name in expected_cases}
    directory = Path(results_dir)
    if directory.exists():
        # Rounds write to subdirectories; order attempts by time, so the
        # "latest failed attempt" shown in reports really is the latest.
        paths = sorted(
            directory.rglob("*.json"),
            key=lambda path: (path.stat().st_mtime_ns, path.name),
        )
        for path in paths:
            if path.name.startswith("."):
                continue
            record = json.loads(path.read_text())
            name = record.get("name") if isinstance(record, dict) else None
            # Files for cases outside this run's selection are ignored, so
            # they can never enter a reference or a decision.
            if name in attempts:
                attempts[name].append(record)
    return attempts


def _is_incomplete(record):
    if not isinstance(record, dict):
        return True
    if record.get("status") not in ("passed", "failed"):
        return True
    if record.get("error"):
        return True
    metrics = record.get("metrics")
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


def tally(records):
    """Passing attempts out of complete attempts, plus incomplete attempts.

    An attempt passes only if every metric met its threshold.
    """
    passed = failed = incomplete = 0
    for record in records:
        if _is_incomplete(record):
            incomplete += 1
        elif record["status"] == "passed":
            passed += 1
        else:
            failed += 1
    return {
        "passed": passed,
        "attempts": passed + failed,
        "incomplete": incomplete,
    }


# ---------------------------------------------------------------- Fisher


def _upper_tail(population, marked, drawn, observed):
    """P(X >= observed) for X ~ Hypergeometric(population, marked, drawn)."""
    if observed <= 0:
        return 1.0
    total = comb(population, drawn)
    return (
        sum(
            comb(marked, k) * comb(population - marked, drawn - k)
            for k in range(observed, min(marked, drawn) + 1)
        )
        / total
    )


def decline_p_value(reference, recent):
    """One-sided Fisher exact test for a lower pass rate in ``recent``.

    If both share one pass rate, every attempt is interchangeable, so the
    failures could have fallen on any of them. This is the chance that
    ``recent`` holds at least as many of them as it does.
    """
    failures = (reference["attempts"] - reference["passed"]) + (
        recent["attempts"] - recent["passed"]
    )
    return _upper_tail(
        reference["attempts"] + recent["attempts"],
        failures,
        recent["attempts"],
        recent["attempts"] - recent["passed"],
    )


def improvement_p_value(reference, recent):
    """One-sided Fisher exact test for a higher pass rate in ``recent``."""
    passes = reference["passed"] + recent["passed"]
    return _upper_tail(
        reference["attempts"] + recent["attempts"],
        passes,
        recent["attempts"],
        recent["passed"],
    )


# ---------------------------------------------------------------- verdicts


def _reference(baseline, name):
    entry = ((baseline or {}).get("cases") or {}).get(name)
    if (
        not isinstance(entry, dict)
        or not isinstance(entry.get("passed"), int)
        or not isinstance(entry.get("attempts"), int)
        or entry["attempts"] < 1
    ):
        return None
    return {"passed": entry["passed"], "attempts": entry["attempts"]}


def can_confirm(reference, policy):
    """Whether extra attempts could prove a decline for this reference.

    A case that rarely passes in its reference cannot be shown to have
    declined with a handful of attempts, so confirming it would only spend
    API calls.
    """
    pooled = 1 + policy["confirmation_attempts"]
    return _worst_case_p_value(reference, pooled) < policy["regression_below"]


def find_suspects(attempts, baseline, policy):
    """Cases whose first attempt failed and whose decline could be proven."""
    suspects = []
    for name, records in attempts.items():
        reference = _reference(baseline, name)
        result = tally(records)
        if reference is None or not result["attempts"]:
            continue
        if result["passed"] < result["attempts"] and can_confirm(reference, policy):
            suspects.append(name)
    return suspects


def decide(
    attempts,
    baseline,
    policy,
    *,
    suspects=(),
    expected_attempts=None,
    require_reference=True,
):
    """Judge every case against its reference and decide delivery.

    ``expected_attempts`` maps a case to how many attempts it should have;
    fewer recorded attempts mean missing evidence. Without
    ``require_reference``, cases are reported against their own criteria
    only and never block for failing.
    """
    expected_attempts = expected_attempts or {}
    cases = {}
    for name, records in attempts.items():
        result = tally(records)
        reference = _reference(baseline, name)
        # Judged on attempts with a verdict; retried attempts that finally
        # got one make up for those that did not.
        missing = max(0, expected_attempts.get(name, 1) - result["attempts"])
        entry = {
            "run": {"passed": result["passed"], "attempts": result["attempts"]},
            "incomplete_attempts": missing,
            "reference": reference,
            "p_value": None,
            "suspect": name in suspects,
        }
        if missing or not result["attempts"]:
            verdict = "incomplete"
        elif reference is None:
            verdict = "no_reference" if require_reference else "unreferenced"
        else:
            entry["p_value"] = decline_p_value(reference, result)
            if name in suspects:
                verdict = (
                    "regression"
                    if entry["p_value"] < policy["regression_below"]
                    else "suspect_cleared"
                )
            else:
                verdict = "consistent"
        entry["verdict"] = verdict
        entry["blocking"] = verdict in BLOCKING_VERDICTS
        cases[name] = entry

    referenced = set(((baseline or {}).get("cases") or {}))
    return {
        "schema_version": SCHEMA_VERSION,
        "allow_delivery": not any(entry["blocking"] for entry in cases.values()),
        "policy": policy,
        "cases": cases,
        "stale_reference_entries": sorted(referenced - set(attempts)),
    }


# ---------------------------------------------------------------- baseline


def build_baseline(
    attempts, previous, policy, *, suite, commit, recorded_at, full
):
    """The new reference from a baseline run, and what changed.

    A case is recorded from its complete attempts if it has at least
    ``baseline_attempts`` of them; otherwise its previous entry is kept. A
    full rebuild also drops entries for cases no longer in the dataset.
    """
    minimum = policy["baseline_attempts"]
    entries = dict(((previous or {}).get("cases") or {}))
    removed = []
    if full:
        removed = sorted(set(entries) - set(attempts))
        for name in removed:
            del entries[name]

    changes = {
        "recorded": [],
        "fails": [],
        "worse": [],
        "improved": [],
        "new": [],
        "not_recorded": [],
        "removed": removed,
    }
    for name, records in attempts.items():
        result = tally(records)
        if result["attempts"] < minimum:
            changes["not_recorded"].append(
                {
                    "case": name,
                    "attempts": result["attempts"],
                    "incomplete": result["incomplete"],
                }
            )
            continue
        new = {"passed": result["passed"], "attempts": result["attempts"]}
        old = _reference(previous, name)
        if old is None:
            changes["new"].append({"case": name, "new": new})
        else:
            worse = decline_p_value(old, new)
            better = improvement_p_value(old, new)
            if worse < policy["change_below"]:
                changes["worse"].append(
                    {"case": name, "old": old, "new": new, "p_value": worse}
                )
            elif better < policy["change_below"]:
                changes["improved"].append(
                    {"case": name, "old": old, "new": new, "p_value": better}
                )
        if new["passed"] < new["attempts"]:
            changes["fails"].append({"case": name, "new": new})
        if result["incomplete"]:
            new["incomplete_attempts"] = result["incomplete"]
        entries[name] = {**new, "commit": commit, "recorded_at": recorded_at}
        changes["recorded"].append(name)

    baseline = {
        "schema_version": SCHEMA_VERSION,
        "suite": suite,
        "cases": dict(sorted(entries.items())),
    }
    return baseline, changes


# ---------------------------------------------------------------- output


_RATE_LIMIT = re.compile(r"\b429\b|rate.?limit", re.IGNORECASE)
_MAX_REASON_LENGTH = 160

_VERDICT_LABEL = {
    "regression": "REGRESSION",
    "no_reference": "NO REFERENCE",
    "incomplete": "INCOMPLETE",
    "suspect_cleared": "not confirmed",
    "unreferenced": "failed",
}

_VERDICT_STYLE = {
    "regression": ("red", "bold"),
    "no_reference": ("yellow",),
    "incomplete": ("yellow",),
    "suspect_cleared": ("dim",),
    "unreferenced": ("red",),
}

_ANSI = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33"}


def use_color():
    """Colors in a terminal and in GitHub Actions logs; never in files.

    NO_COLOR (https://no-color.org) turns them off; FORCE_COLOR turns them on.
    """
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR") or os.environ.get("GITHUB_ACTIONS") == "true":
        return True
    return sys.stdout.isatty()


def paint(text, *styles):
    """``text`` wrapped in ANSI styles, or unchanged when colors are off."""
    if not styles or not text or not use_color():
        return text
    codes = ";".join(_ANSI[style] for style in styles)
    return f"\033[{codes}m{text}\033[0m"


def _title(text):
    return paint(text, "bold")


def _short_reason(message):
    """One line per reason: provider rate limits collapse to a fixed text."""
    text = str(message or "").strip()
    if _RATE_LIMIT.search(text):
        return "Rate limit exceeded (HTTP 429); retry with fewer workers."
    return _one_line(text)


def _one_line(text, limit=None):
    limit = limit or _MAX_REASON_LENGTH
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


def _short_metric_name(name):
    """Display name: "AnswerRelevancyMetric" and "Rules Correctness [GEval]"
    become "Answer Relevancy" and "Rules Correctness"."""
    text = re.sub(r"\s*\[[^\]]*\]$", "", str(name or "metric"))
    text = re.sub(r"(?<=\w)Metric$", "", text)
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)


def _ratio(counts):
    return f"{counts['passed']}/{counts['attempts']}" if counts else "-"


def _p(value):
    if value is None:
        return ""
    if value < 0.0001:
        return "p < 0.0001"
    return "p = " + f"{value:.4f}".rstrip("0").rstrip(".")


def _table(rows, indent="  ", header=False):
    """Left-aligned columns; with ``header``, a bold first row and a rule.

    A cell is text, or ``(text, styles)`` to color it; padding is computed on
    the text, so colors never break the alignment.
    """
    cells = [
        [cell if isinstance(cell, tuple) else (cell, ()) for cell in row]
        for row in rows
    ]
    widths = [
        max(len(row[i][0]) for row in cells) for i in range(len(cells[0]))
    ]
    lines = []
    for number, row in enumerate(cells):
        parts = []
        for (text, styles), width in zip(row, widths):
            if header and number == 0:
                styles = ("bold",)
            padding = " " * (width - len(text))
            parts.append(paint(text, *styles) + padding)
        lines.append((indent + "  ".join(parts)).rstrip())
    if header:
        lines.insert(1, indent + paint("  ".join("-" * w for w in widths), "dim"))
    return lines


def _case_list(names, limit=3):
    shown = ", ".join(names[:limit])
    return shown + (f" and {len(names) - limit} more" if len(names) > limit else "")


def _reasons(name, records):
    """Why the latest failing or incomplete attempt of a case went wrong."""
    for record in reversed(records):
        if _is_incomplete(record):
            errors = [record.get("error")] + [
                metric.get("error") for metric in record.get("metrics") or []
            ]
            message = next((error for error in errors if error), None)
            return [
                f"  {paint(name, 'bold')}: "
                f"{_short_reason(message or 'no verdict recorded')}"
            ]
        failed = [
            metric
            for metric in record.get("metrics") or []
            if metric.get("status") == "failed"
        ]
        if failed:
            return [
                f"  {paint(name, 'bold')} / "
                f"{_short_metric_name(metric.get('name'))}: "
                f"{_one_line(metric.get('reason') or 'no reason recorded')}"
                for metric in failed
            ]
    return []


def _metric_cell(metric):
    status = metric.get("status")
    score = metric.get("score")
    style = ("green",) if status == "passed" else ("red",)
    if status in ("passed", "failed") and isinstance(score, (int, float)):
        return (f"{score:.2f} {'✓' if status == 'passed' else '✗'}", style)
    if status in ("passed", "failed"):
        return ("✓" if status == "passed" else "✗", style)
    return ("error" if status == "error" else "?", ("yellow",))


_RESULT_STYLE = {
    "FAIL": ("red", "bold"),
    "INCOMPLETE": ("yellow",),
    "pass": ("green",),
}


def format_results(attempts):
    """A quick run's table: every case and metric, failing cases first,
    followed by the judge's reason for each failed metric."""
    columns = []
    rows = []
    for name, records in attempts.items():
        record = records[-1] if records else {"status": "incomplete", "metrics": []}
        cells = {}
        for metric in record.get("metrics") or []:
            column = _short_metric_name(metric.get("name"))
            if column not in columns:
                columns.append(column)
            cells[column] = _metric_cell(metric)
        if _is_incomplete(record):
            result = "INCOMPLETE"
        else:
            result = "pass" if record.get("status") == "passed" else "FAIL"
        rows.append((name, cells, result))
    order = {"FAIL": 0, "INCOMPLETE": 1, "pass": 2}
    rows.sort(key=lambda row: (order[row[2]], row[0]))

    table = [["Case", *columns, "Result"]] + [
        [
            name,
            *(cells.get(column, ("-", ("dim",))) for column in columns),
            (result, _RESULT_STYLE[result]),
        ]
        for name, cells, result in rows
    ]
    lines = _table(table, indent="", header=True)
    passed = sum(1 for row in rows if row[2] == "pass")
    summary = f"{passed} of {len(rows)} cases passed every metric."
    lines.append(paint(summary, "bold", "green" if passed == len(rows) else "red"))

    reasons = [
        line
        for name, _, result in rows
        if result != "pass"
        for line in _reasons(name, attempts.get(name, []))
    ]
    if reasons:
        lines += ["", _title("Why (judge's reasons, shortened):")] + reasons
    return "\n".join(lines)


def format_decision(decision, attempts, *, suite, reference_path=None):
    """The run's report: what needs attention, accepted failures, decision."""
    cases = decision["cases"]
    order = {
        "regression": 0,
        "incomplete": 1,
        "no_reference": 2,
        "suspect_cleared": 3,
        "unreferenced": 4,
    }
    attention = sorted(
        (
            (name, entry)
            for name, entry in cases.items()
            if entry["verdict"] in order
            and not (
                entry["verdict"] == "unreferenced"
                and entry["run"]["passed"] == entry["run"]["attempts"]
            )
        ),
        key=lambda item: (order[item[1]["verdict"]], item[0]),
    )

    header = f"Suite: {suite}"
    if reference_path:
        header += f" | Reference: {reference_path}"
    lines = [paint(header, "dim")]
    if attention:
        lines += ["", _title("Needs attention:")]
        rows = [["Case", "Reference", "This run", "Verdict"]]
        for name, entry in attention:
            verdict = _VERDICT_LABEL[entry["verdict"]]
            if entry["verdict"] == "incomplete":
                verdict += f" ({entry['incomplete_attempts']} attempt(s) without a verdict)"
            elif entry["p_value"] is not None:
                verdict += f" ({_p(entry['p_value'])})"
            rows.append(
                [
                    name,
                    _ratio(entry["reference"]),
                    _ratio(entry["run"]),
                    (verdict, _VERDICT_STYLE[entry["verdict"]]),
                ]
            )
        lines += _table(rows, header=True)
        reasons = [
            line
            for name, _ in attention
            for line in _reasons(name, attempts.get(name, []))
        ]
        if reasons:
            lines += [
                "",
                _title("Why (latest failed attempt, judge's reasons shortened):"),
            ]
            lines += reasons

    quiet = len(cases) - len(attention)
    summary = (
        f"{quiet} of {len(cases)} cases match their reference."
        if any(e["reference"] for e in cases.values())
        else f"{quiet} of {len(cases)} cases passed."
    )
    lines += ["", paint(summary, "green")]

    accepted = sorted(
        (
            (name, entry["reference"])
            for name, entry in cases.items()
            if entry["reference"]
            and entry["reference"]["passed"] < entry["reference"]["attempts"]
        ),
        key=lambda item: (item[1]["passed"] / item[1]["attempts"], item[0]),
    )
    if accepted:
        lines += [
            "",
            _title("Fails in the reference (accepted behavior, not regressions):"),
        ]
        lines += _table(
            [[name, (_ratio(reference), ("yellow",))] for name, reference in accepted]
        )

    if decision["stale_reference_entries"]:
        lines += [
            "",
            "The reference still has cases no longer in the dataset: "
            + _case_list(decision["stale_reference_entries"])
            + ". A full rebuild (make eval-baseline) drops them.",
        ]

    steps = _next_steps(cases)
    if steps:
        lines += ["", _title("Next steps:")] + [f"  - {step}" for step in steps]

    blocking = [entry["verdict"] for entry in cases.values() if entry["blocking"]]
    if blocking:
        counts = ", ".join(
            f"{blocking.count(verdict)} {_VERDICT_LABEL[verdict].lower()}"
            for verdict in BLOCKING_VERDICTS
            if verdict in blocking
        )
        lines += ["", paint(f"Decision: BLOCK ({counts})", "red", "bold")]
    else:
        lines += ["", paint("Decision: ALLOW", "green", "bold")]
    return "\n".join(lines)


def _next_steps(cases):
    def named(verdict):
        return sorted(name for name, e in cases.items() if e["verdict"] == verdict)

    steps = []
    regressions = named("regression")
    if regressions:
        steps.append(
            "Investigate the regressions (" + _case_list(regressions) + "). "
            "If the new behavior is acceptable, rebuild their reference with "
            "make eval-baseline CASE=<name> and commit it."
        )
    unreferenced = named("no_reference")
    if unreferenced:
        steps.append(
            "Build the reference for new cases ("
            + _case_list(unreferenced)
            + "): make eval-baseline CASE=<name>, then commit "
            "the baseline file."
        )
    if named("incomplete"):
        steps.append(
            "Rerun the evaluation: some attempts produced no verdict "
            "(errors or rate limits; EVAL_WORKERS=1 is the safe setting)."
        )
    return steps


def format_baseline_changes(changes, *, path, attempts_per_case):
    """What a baseline rebuild changed, for the developer to review."""
    lines = [
        f"Recorded {len(changes['recorded'])} case(s) with up to "
        f"{attempts_per_case} attempts each in {path}."
    ]

    def section(title, rows, style=()):
        if rows:
            lines.extend(["", _title(title)])
            lines.extend(
                _table([[row[0], *((cell, style) for cell in row[1:])] for row in rows])
            )

    def change(item):
        return [
            item["case"],
            f"{_ratio(item['old'])} -> {_ratio(item['new'])}",
            f"({_p(item['p_value'])})",
        ]

    section(
        "Fails in the new baseline:",
        [
            [item["case"], _ratio(item["new"])]
            for item in sorted(
                changes["fails"],
                key=lambda i: (i["new"]["passed"] / i["new"]["attempts"], i["case"]),
            )
        ],
        ("yellow",),
    )
    section(
        "Got worse than the previous baseline (accepting this accepts the decline):",
        [change(item) for item in changes["worse"]],
        ("red", "bold"),
    )
    section("Improved:", [change(item) for item in changes["improved"]], ("green",))
    section(
        "New in the baseline:",
        [[i["case"], _ratio(i["new"])] for i in changes["new"]],
    )
    if changes["removed"]:
        lines += [
            "",
            _title("Removed (no longer in the dataset): ")
            + _case_list(changes["removed"], 10),
        ]
    section(
        "NOT recorded (too few attempts with a verdict, even after retries; "
        "rerun with make eval-baseline CASE=<name>):",
        [
            [i["case"], f"{i['attempts']} complete, {i['incomplete']} without a verdict"]
            for i in changes["not_recorded"]
        ],
        ("red",),
    )
    lines += ["", _title("Review the lists above, then commit the baseline file.")]
    return "\n".join(lines)
