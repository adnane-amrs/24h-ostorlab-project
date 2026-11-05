"""Feature tests for the snapshot diff CLI.

The starter's placeholder assertion was replaced with feature assertions; the
help and readable-file-error checks are kept from the scaffold.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

ZERO_COUNTS = {"new": 0, "changed": 0, "unchanged": 0, "resolved": 0, "unknown": 0}


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "app.py", *arguments],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )


class CliTestCase(unittest.TestCase):
    """Shared helpers: a temporary fixture directory and a minimal valid payload."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = pathlib.Path(temporary.name)

    def write_fixture(self, name: str, payload: dict) -> str:
        path = self.directory / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return str(path)

    @staticmethod
    def finding(**overrides) -> dict:
        row = {
            "tenant": "north",
            "asset_id": "api",
            "rule_id": "auth",
            "location": "/login",
            "severity": "high",
            "evidence": "evidence text",
        }
        row.update(overrides)
        return row

    def base_payload(self) -> dict:
        return {
            "tenant": "north",
            "before": {"findings": [self.finding()]},
            "after": {
                "coverage": [{"asset_id": "api", "status": "complete"}],
                "findings": [],
            },
        }

    def assertFatal(self, payload: dict, fragment: str) -> None:
        result = _run_cli("--input", self.write_fixture("fixture.json", payload))
        self.assertEqual(result.returncode, 2, msg=result.stderr)
        self.assertIn("error:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn(fragment, result.stderr)
        self.assertEqual(result.stdout, "")


class InterfaceTests(unittest.TestCase):
    """Kept from the starter scaffold: CLI surface and readable fatal errors."""

    def testCli_whenHelpRequested_returnsUsage(self) -> None:
        result = _run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--input", result.stdout)

    def testCli_whenInputMissing_reportsReadableError(self) -> None:
        result = _run_cli("--input", "inputs/does-not-exist.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stdout, "")

    def testCli_whenJsonMalformed_reportsReadableError(self) -> None:
        result = _run_cli("--input", "inputs/malformed-input.txt")
        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stdout, "")


class PrimarySnapshotTests(CliTestCase):
    """The README acceptance numbers for inputs/primary.json."""

    def testPrimary_classifiesAllFiveBucketsWithExpectedCounts(self) -> None:
        result = _run_cli("--input", "inputs/primary.json", "--tenant", "north")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(
            payload["counts"],
            {"new": 1, "changed": 1, "unchanged": 1, "resolved": 1, "unknown": 1},
        )
        self.assertEqual(payload["excluded_foreign_rows"], 2)
        entries = payload["entries"]
        self.assertEqual(len(entries), 5)
        keys = [
            (entry["tenant"], entry["asset_id"], entry["rule_id"], entry["location"])
            for entry in entries
        ]
        self.assertEqual(keys, sorted(keys), "entries must be sorted by finding key")
        by_key = {(entry["asset_id"], entry["rule_id"], entry["location"]): entry for entry in entries}
        changed = by_key[("api", "auth", "/login")]
        self.assertEqual(changed["classification"], "changed")
        self.assertEqual((changed["before_severity"], changed["after_severity"]), ("high", "critical"))
        self.assertEqual((changed["before_evidence"], changed["after_evidence"]), ("old auth", "new auth"))
        created = by_key[("api", "headers", "/")]
        self.assertEqual(created["classification"], "new")
        self.assertIsNone(created["before_severity"])
        self.assertIsNone(created["before_evidence"])
        resolved = by_key[("api", "tls", "/")]
        self.assertEqual(resolved["classification"], "resolved")
        self.assertIsNone(resolved["after_severity"])
        self.assertIsNone(resolved["after_evidence"])
        unknown = by_key[("portal", "debug", "/debug")]
        self.assertEqual(unknown["classification"], "unknown")
        unchanged = by_key[("portal", "leak", "/export")]
        self.assertEqual(unchanged["classification"], "unchanged")
        self.assertEqual(
            (unchanged["before_evidence"], unchanged["after_evidence"]),
            ("old leak", "fresh leak"),
        )

    def testPrimary_reportMatchesCountsAndHidesForeignRows(self) -> None:
        result = _run_cli("--input", "inputs/primary.json", "--tenant", "north")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        report = payload["report"]
        for classification, count in payload["counts"].items():
            self.assertIn(f"{classification} ({count}):", report)
        self.assertIn("foreign-excluded=2", report)
        for entry in payload["entries"]:
            self.assertIn(entry["location"], report)
            self.assertIn(entry["rule_id"], report)
        for leaked in ("south", "private", "/secret", "foreign new"):
            self.assertNotIn(leaked, result.stdout)

    def testPrimary_whenRunTwice_outputIsIdentical(self) -> None:
        first = _run_cli("--input", "inputs/primary.json", "--tenant", "north")
        second = _run_cli("--input", "inputs/primary.json", "--tenant", "north")
        self.assertEqual(first.returncode, 0, msg=first.stderr)
        self.assertEqual(first.stdout, second.stdout)


class SecondarySnapshotTests(CliTestCase):
    """The README acceptance numbers for inputs/secondary.json."""

    def testSecondary_emptyCoverageYieldsUnknownNotResolved(self) -> None:
        result = _run_cli("--input", "inputs/secondary.json", "--tenant", "north")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["counts"], {**ZERO_COUNTS, "unknown": 1})
        self.assertEqual(payload["excluded_foreign_rows"], 0)
        entry = payload["entries"][0]
        self.assertEqual(
            (entry["asset_id"], entry["rule_id"], entry["location"]),
            ("api", "auth", "/login"),
        )
        self.assertEqual(entry["classification"], "unknown")
        self.assertEqual((entry["before_severity"], entry["after_severity"]), ("high", None))
        self.assertEqual((entry["before_evidence"], entry["after_evidence"]), ("old", None))


class TenantIsolationTests(CliTestCase):
    def test_whenForeignRowsPresent_countsAndNeverExportsValues(self) -> None:
        payload = self.base_payload()
        payload["before"]["findings"].append(
            self.finding(
                tenant="south",
                asset_id="db",
                rule_id="dump",
                location="/backup",
                severity="critical",
                evidence="secret stuff",
            )
        )
        payload["after"]["coverage"] = [
            {"asset_id": "api", "status": "complete"},
            {"asset_id": "db", "status": "failed"},
        ]
        payload["after"]["findings"].append(
            self.finding(
                tenant="south",
                asset_id="db",
                rule_id="dump",
                location="/backup",
                severity="low",
                evidence="new secret stuff",
            )
        )
        result = _run_cli("--input", self.write_fixture("isolated.json", payload))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["excluded_foreign_rows"], 2)
        self.assertEqual(data["counts"], {**ZERO_COUNTS, "resolved": 1})
        for leaked in ("south", "dump", "/backup", "secret"):
            self.assertNotIn(leaked, result.stdout)

    def test_whenSelectedTenantDiffersFromInputTenant_fails(self) -> None:
        payload = self.base_payload()
        payload["tenant"] = "south"
        payload["before"]["findings"] = [self.finding(tenant="south")]
        result = _run_cli("--input", self.write_fixture("tenant.json", payload))
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not match", result.stderr)


class ValidationTests(CliTestCase):
    def test_whenDuplicateKeyWithinSnapshot_fails(self) -> None:
        payload = self.base_payload()
        payload["before"]["findings"].append(self.finding(evidence="copy"))
        self.assertFatal(payload, "duplicate")

    def test_whenDuplicateKeyAppearsOnlyAfterTrimming_fails(self) -> None:
        # Refinement: identity uses the trimmed location, so whitespace variants collide.
        payload = self.base_payload()
        payload["before"]["findings"].append(self.finding(location=" /login ", evidence="copy"))
        self.assertFatal(payload, "duplicate")

    def test_whenSeverityOutsideKnownScale_fails(self) -> None:
        payload = self.base_payload()
        payload["before"]["findings"] = [self.finding(severity="urgent")]
        self.assertFatal(payload, "severity")

    def test_whenRequiredFieldBlank_fails(self) -> None:
        payload = self.base_payload()
        payload["before"]["findings"] = [self.finding(evidence="   ")]
        self.assertFatal(payload, "evidence")

    def test_whenCoverageStatusUnknown_fails(self) -> None:
        payload = self.base_payload()
        payload["after"]["coverage"] = [{"asset_id": "api", "status": "skipped"}]
        self.assertFatal(payload, "status")

    def test_whenCoverageAssetRepeated_fails(self) -> None:
        payload = self.base_payload()
        payload["after"]["coverage"] = [
            {"asset_id": "api", "status": "complete"},
            {"asset_id": "api", "status": "partial"},
        ]
        self.assertFatal(payload, "duplicate coverage")

    def test_whenRequiredSectionMissing_fails(self) -> None:
        payload = self.base_payload()
        del payload["after"]["coverage"]
        self.assertFatal(payload, "after.coverage")


class EdgeCaseTests(CliTestCase):
    def test_whenBothSnapshotsEmpty_succeedsWithZeroCounts(self) -> None:
        payload = {
            "tenant": "north",
            "before": {"findings": []},
            "after": {"coverage": [], "findings": []},
        }
        result = _run_cli("--input", self.write_fixture("empty.json", payload))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["entries"], [])
        self.assertEqual(data["counts"], ZERO_COUNTS)
        self.assertEqual(data["excluded_foreign_rows"], 0)
        self.assertIn("no findings to compare", data["report"])

    def test_whenOnlyEvidenceChanged_isUnchanged(self) -> None:
        payload = self.base_payload()
        payload["after"]["findings"] = [self.finding(evidence="rewritten text")]
        result = _run_cli("--input", self.write_fixture("evidence.json", payload))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["counts"]["unchanged"], 1)
        entry = data["entries"][0]
        self.assertEqual(entry["classification"], "unchanged")
        self.assertEqual(
            (entry["before_evidence"], entry["after_evidence"]),
            ("evidence text", "rewritten text"),
        )

    def test_whenTrimmedAndLowercased_keyAndSeverityAreNormalized(self) -> None:
        # Constructed boundary: " /login " + " HIGH " is the same key/severity as "/login" + "high".
        payload = self.base_payload()
        payload["after"]["findings"] = [
            self.finding(location=" /login ", severity=" HIGH ", evidence="same")
        ]
        result = _run_cli("--input", self.write_fixture("normalize.json", payload))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["counts"], {**ZERO_COUNTS, "unchanged": 1})
        self.assertEqual(data["entries"][0]["classification"], "unchanged")

    def test_whenCoverageFailed_isUnknownNotResolved(self) -> None:
        payload = self.base_payload()
        payload["after"]["coverage"] = [{"asset_id": "api", "status": "failed"}]
        result = _run_cli("--input", self.write_fixture("failed.json", payload))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["counts"], {**ZERO_COUNTS, "unknown": 1})


if __name__ == "__main__":
    unittest.main()
