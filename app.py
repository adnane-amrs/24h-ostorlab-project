"""Snapshot diff CLI: compare two finding snapshots with tenant scoping and coverage awareness.

Implements the candidate README contract: classify every finding key across a
before/after snapshot pair as new, changed, unchanged, resolved, or unknown.
Successful runs print one JSON document to stdout. Fatal input problems print a
readable ``error: ...`` line to stderr, produce no stdout, and exit with code 2.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import typing

SEVERITIES = ("critical", "high", "medium", "low", "info")
COVERAGE_STATUSES = ("complete", "partial", "failed")
CLASSIFICATIONS = ("new", "changed", "unchanged", "resolved", "unknown")
FINDING_FIELDS = ("tenant", "asset_id", "rule_id", "location", "evidence")
FindingKey = tuple[str, str, str, str]


class InputError(ValueError):
    """Raised for any invalid input; main() turns this into exit code 2."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InputError(message)


def _require_text(label: str, row: dict[str, typing.Any], field: str) -> str:
    """Return row[field] trimmed; fail when it is missing, not a string, or blank."""
    value = row.get(field)
    _require(isinstance(value, str), f"{label}: field '{field}' must be a string")
    value = value.strip()
    _require(bool(value), f"{label}: field '{field}' must not be empty")
    return value


def _load_findings(
    rows: list[typing.Any],
    snapshot: str, 
    tenant: str) -> tuple[dict[FindingKey, dict[str, str]], int]:
    """Validate and normalize one snapshot; count foreign rows without exposing them."""
    findings: dict[FindingKey, dict[str, str]] = {}
    foreign_rows = 0
    for index, row in enumerate(rows):
        label = f"{snapshot}.findings[{index}]"
        _require(isinstance(row, dict), f"{label} must be a JSON object")
        row_tenant = row.get("tenant")
        if isinstance(row_tenant, str) and row_tenant.strip() and row_tenant.strip() != tenant:
            # Foreign row: counted only. Its values are never validated or reported.
            foreign_rows += 1
            continue
        # Selected-tenant rows - and rows too broken to scope - must be fully valid.
        cleaned = {field: _require_text(label, row, field) for field in FINDING_FIELDS}
        severity = row.get("severity")
        _require(isinstance(severity, str), f"{label}: field 'severity' must be a string")
        severity = severity.strip().lower()
        _require(
            severity in SEVERITIES,
            f"{label}: severity '{severity}' must be one of: {', '.join(SEVERITIES)}",
        )
        cleaned["severity"] = severity
        key: FindingKey = (cleaned["tenant"], cleaned["asset_id"], cleaned["rule_id"], cleaned["location"])
        _require(
            key not in findings,
            f"{label}: duplicate finding key "
            f"(asset '{cleaned['asset_id']}', rule '{cleaned['rule_id']}', location '{cleaned['location']}')",
        )
        findings[key] = cleaned
    return findings, foreign_rows


def _load_coverage(rows: list[typing.Any]) -> dict[str, str]:
    """Validate the after-coverage list into an asset_id -> status lookup."""
    coverage: dict[str, str] = {}
    for index, row in enumerate(rows):
        label = f"after.coverage[{index}]"
        _require(isinstance(row, dict), f"{label} must be a JSON object")
        asset_id = _require_text(label, row, "asset_id")
        status = _require_text(label, row, "status")
        _require(
            status in COVERAGE_STATUSES,
            f"{label}: status '{status}' must be one of: {', '.join(COVERAGE_STATUSES)}",
        )
        _require(asset_id not in coverage, f"{label}: duplicate coverage entry for asset '{asset_id}'")
        coverage[asset_id] = status
    return coverage


def _validate_payload(payload: dict[str, typing.Any], selected_tenant: str) -> str:
    """Check the top-level schema and tenant match; return the tenant used for scoping."""
    selected_tenant = selected_tenant.strip()
    tenant = payload.get("tenant")
    _require(isinstance(tenant, str) and bool(tenant.strip()), "input: 'tenant' must be a nonempty string")
    tenant = tenant.strip()
    _require(
        tenant == selected_tenant,
        f"selected tenant '{selected_tenant}' does not match input tenant '{tenant}'",
    )
    for name in ("before", "after"):
        section = payload.get(name)
        _require(isinstance(section, dict), f"input: '{name}' must be a JSON object")
        _require(isinstance(section.get("findings"), list), f"input: '{name}.findings' must be a list")
    _require(isinstance(payload["after"].get("coverage"), list), "input: 'after.coverage' must be a list")
    return tenant


def _classify(
    before: dict[FindingKey, dict[str, str]],
    after: dict[FindingKey, dict[str, str]],
    coverage: dict[str, str],
) -> list[dict[str, typing.Any]]:
    """Apply the five-way classification to every finding key, sorted by key."""
    entries: list[dict[str, typing.Any]] = []
    for key in sorted(set(before) | set(after)):
        before_row = before.get(key)
        after_row = after.get(key)
        if before_row is None:
            classification = "new"
        elif after_row is None:
            # Uncertainty preservation: only a fully rescanned asset may be called resolved.
            classification = "resolved" if coverage.get(key[1]) == "complete" else "unknown"
        elif before_row["severity"] != after_row["severity"]:
            classification = "changed"
        else:
            classification = "unchanged"
        entries.append(
            {
                "tenant": key[0],
                "asset_id": key[1],
                "rule_id": key[2],
                "location": key[3],
                "classification": classification,
                "before_severity": before_row["severity"] if before_row else None,
                "after_severity": after_row["severity"] if after_row else None,
                "before_evidence": before_row["evidence"] if before_row else None,
                "after_evidence": after_row["evidence"] if after_row else None,
            }
        )
    return entries


def _describe_entry(entry: dict[str, typing.Any]) -> str:
    where = f"asset '{entry['asset_id']}', rule '{entry['rule_id']}', location '{entry['location']}'"
    if entry["classification"] == "new":
        return f"{where}: severity={entry['after_severity']}, evidence=\"{entry['after_evidence']}\""
    if entry["classification"] in ("changed", "unchanged"):
        return (
            f"{where}: severity={entry['before_severity']}->{entry['after_severity']}, "
            f"evidence=\"{entry['before_evidence']}\" -> \"{entry['after_evidence']}\""
        )
    return f"{where}: severity={entry['before_severity']}, evidence=\"{entry['before_evidence']}\""


def _build_report(
    tenant: str,
    entries: list[dict[str, typing.Any]],
    counts: dict[str, int],
    excluded_foreign_rows: int,
    coverage: dict[str, str],
) -> str:
    """Build a readable multiline summary strictly from the same entries and counts."""
    lines = [
        f"Snapshot diff for tenant '{tenant}'",
        (
            f"counts: new={counts['new']} changed={counts['changed']} unchanged={counts['unchanged']} "
            f"resolved={counts['resolved']} unknown={counts['unknown']} foreign-excluded={excluded_foreign_rows}"
        ),
    ]
    if not entries:
        lines.append("no findings to compare")
    for classification in CLASSIFICATIONS:
        group = [entry for entry in entries if entry["classification"] == classification]
        if not group:
            continue
        lines.append(f"{classification} ({len(group)}):")
        for entry in group:
            line = f"  - {_describe_entry(entry)}"
            if classification in ("resolved", "unknown"):
                line += f" (asset coverage: {coverage.get(entry['asset_id'], 'missing')})"
            lines.append(line)
    return "\n".join(lines)


def diff_snapshots(payload: dict[str, typing.Any], arguments: argparse.Namespace) -> dict[str, typing.Any]:
    """Validate the payload, scope to the tenant, diff the snapshots, build the report."""
    tenant = _validate_payload(payload, arguments.tenant)
    before, before_foreign = _load_findings(payload["before"]["findings"], "before", tenant)
    after, after_foreign = _load_findings(payload["after"]["findings"], "after", tenant)
    coverage = _load_coverage(payload["after"]["coverage"])
    entries = _classify(before, after, coverage)
    counts = {classification: 0 for classification in CLASSIFICATIONS}
    for entry in entries:
        counts[entry["classification"]] += 1
    excluded_foreign_rows = before_foreign + after_foreign
    return {
        "entries": entries,
        "counts": counts,
        "excluded_foreign_rows": excluded_foreign_rows,
        "report": _build_report(tenant, entries, counts, excluded_foreign_rows, coverage),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare finding snapshots while respecting tenant and coverage.")
    parser.add_argument("--input", default="inputs/primary.json", help="UTF-8 fixture JSON")
    parser.add_argument("--tenant", default="north")
    arguments = parser.parse_args()
    try:
        payload = json.loads(pathlib.Path(arguments.input).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("input must be a JSON object")
        result = diff_snapshots(payload, arguments)
        print(json.dumps(result, indent=2, sort_keys=True))
    except (OSError, UnicodeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
