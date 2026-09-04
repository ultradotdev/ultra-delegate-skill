"""Public evidence boundaries, separate from route-selection policy."""
import copy
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("evidence", Path(__file__).resolve().parents[1] / ".agents/skills/ultra-delegation/scripts/evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


def outcome():
    return {
        "profile": {"task_family": "code", "provider": "openai", "model": "worker", "host": "codex", "thinking": {"normalized": "medium", "native": "medium"}, "prompt_profile": "v1", "tool_policy": "v1"},
        "accepted": True,
        "gates": [{"name": "tests", "mandatory": True, "passed": True}],
        "metrics": {"quality_score": 85, "cost_usd": 0},
    }


class EvidenceTests(unittest.TestCase):
    def test_nested_contract_is_flat_and_does_not_mutate(self):
        record = outcome()
        record.pop("accepted")
        gates = record.pop("gates")
        record.pop("metrics")
        record.update({"run": {"id": "run-1", "selected": True}, "task": {"task_family": "code", "tools": ["test"]}, "quality": {"score": 85, "accepted": True, "gates": gates}, "performance": {"latency_ms": 20}, "cost": {"usd": 0, "kind": "measured", "usage": {"input_tokens": 10}}, "learning": {"status": "provisional"}})
        original = copy.deepcopy(record)
        result = evidence.validate_outcome(record)
        self.assertEqual(result["run_id"], "run-1")
        self.assertEqual(result["metrics"], {"quality_score": 85, "latency_ms": 20, "cost_usd": 0})
        self.assertEqual(result["usage"], {"input_tokens": 10})
        self.assertEqual(result["cost_kind"], "measured")
        self.assertEqual(record, original)

    def test_unknown_fields_rejected_recursively_and_legacy_projected(self):
        for path in [(), ("profile",), ("profile", "thinking"), ("metrics",), ("task_signature",), ("usage",)]:
            record = outcome()
            cursor = record
            for key in path:
                cursor = cursor.setdefault(key, {})
            cursor["arbitrary_metadata"] = {"password": "sensitive-value"}
            original = copy.deepcopy(record)
            with self.assertRaises(ValueError):
                evidence.validate_outcome(record)
            cleaned = evidence.normalize_outcome(record)
            self.assertNotIn("arbitrary_metadata", repr(cleaned))
            self.assertEqual(record, original)

    def test_gate_and_score_evidence_required(self):
        for edit in [{"gates": []}, {"gates": [{"mandatory": False, "passed": True}]}, {"gates": [{"passed": "yes"}]}, {"gates": [None]}, {"gates": [{"passed": False}]}, {"accepted": 1}, {"metrics": {}}]:
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                evidence.validate_outcome({**outcome(), **edit})
        failed = outcome()
        failed["accepted"] = False
        failed["gates"][0]["passed"] = False
        self.assertFalse(evidence.validate_outcome(failed)["accepted"])

    def test_nonfinite_negative_boolean_and_out_of_range_metrics(self):
        for key, bad in [("quality_score", 101), ("quality_score", -1), ("quality_score", True), ("cost_usd", float("nan")), ("cost_usd", float("inf")), ("latency_ms", -1), ("retries", 1.5)]:
            record = outcome()
            record["metrics"][key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                evidence.validate_outcome(record)

    def test_conflicting_duplicate_representations_rejected(self):
        record = outcome()
        record["quality"] = {"score": 90}
        with self.assertRaisesRegex(ValueError, "conflicting"):
            evidence.validate_outcome(record)

    def test_secret_and_media_detection_in_allowed_values(self):
        for text in ["data:image/png;base64,abc", "ghp_" + "a" * 30, "Bearer " + "a" * 30, "-----BEGIN PRIVATE KEY-----", "a" * 300, "password=supersecretvalue"]:
            with self.subTest(text=text[:20]), self.assertRaises(ValueError):
                evidence.validate_public_value({"summary": text})
        self.assertEqual(evidence.validate_public_value({"summary": "Tests pass; see artifact reference."})["summary"], "Tests pass; see artifact reference.")

    def test_size_depth_and_sensitive_key_boundaries(self):
        cases = [{"summary": "x " * 3000}, ["ok"] * 129, {"summary": {"api_key": "something"}}, {"value": float("nan")}]
        nested = "safe"
        for _ in range(10):
            nested = {"nested": nested}
        cases.append(nested)
        for value in cases:
            with self.assertRaises(ValueError):
                evidence.validate_public_value(value)

    def test_export_allowlist_preserves_generalized_provenance_only(self):
        learning = {"profile": outcome()["profile"], "task_signature": {"language": "Rust", "paths": ["/private/project"]}, "aggregate": {"evidence_count": 3, "mean_quality": 90, "nested_secrets": {"token": "hidden"}}, "provenance_hash": "a" * 64, "project_name": "private project", "metadata": {"source": "private"}, "source_passed_gates": True}
        clean = evidence.sanitize_learning(learning)
        self.assertEqual(clean["aggregate"], {"evidence_count": 3, "mean_quality": 90})
        self.assertEqual(clean["task_signature"], {"language": "Rust"})
        self.assertEqual(clean["provenance_hash"], "a" * 64)
        self.assertNotIn("private", repr(clean))

    def test_resource_failure_is_separate_from_quality_evidence(self):
        event = {"profile": outcome()["profile"], "accepted": False, "failure_kind": "resource",
                 "local_execution": {"status": "resource-aborted", "reason": "memory pressure", "local_dispatch_stopped": True, "cancel_owned_request": True}}
        self.assertEqual("resource", evidence.validate_outcome(event)["failure_kind"])
        for extra in ({"metrics": {"quality_score": 0}}, {"accepted": True}, {"gates": [{"passed": False}]}, {"local_execution": {"status": "eligible"}}):
            with self.assertRaises(ValueError):
                evidence.validate_outcome({**event, **extra})
        event["local_execution"]["arbitrary_payload"] = {"private": "data"}
        with self.assertRaises(ValueError):
            evidence.validate_outcome(event)


if __name__ == "__main__":
    unittest.main()
