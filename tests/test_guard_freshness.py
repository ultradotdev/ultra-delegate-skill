"""Context safeguards must never classify stale or invented telemetry as current."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

HELPER = Path(__file__).resolve().parents[1] / ".agents/skills/ultra-delegation/scripts/ultra_delegation.py"
SPEC = importlib.util.spec_from_file_location("guard_helper", HELPER)
ud = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ud)
NOW = "2026-09-04T12:00:00+00:00"


class GuardFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.clock = patch.object(ud, "now", return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.policy = copy.deepcopy(ud.DEFAULT_POLICY)
        self.snapshot = {"observed_at": NOW, "telemetry": {"availability": "measured"},
                         "context": {"used_tokens": 850, "window_tokens": 1000}}

    def evaluate(self, snapshot=None):
        return ud.evaluate_guard(self.snapshot if snapshot is None else snapshot, self.policy)

    def test_explicit_fresh_measurement_and_estimate(self):
        self.assertEqual(self.evaluate()["risk"], "high")
        self.snapshot["telemetry"]["availability"] = "estimated"
        result = self.evaluate()
        self.assertEqual(result["risk"], "high")
        self.assertEqual(result["telemetry"]["availability"], "estimated")

    def test_missing_provenance_and_observation_are_unknown(self):
        for key in ("observed_at", "telemetry"):
            snapshot = copy.deepcopy(self.snapshot)
            snapshot.pop(key)
            result = self.evaluate(snapshot)
            self.assertEqual(result["risk"], "unknown")
            self.assertIsNone(result["context_utilization"]["value"])

    def test_stale_and_future_observations_are_unknown(self):
        for stamp in ("2026-09-04T11:54:59Z", "2026-09-04T12:00:01Z"):
            self.snapshot["observed_at"] = stamp
            self.assertEqual(self.evaluate()["risk"], "unknown")
        self.snapshot["observed_at"] = "2026-09-04T11:55:00Z"
        self.assertEqual(self.evaluate()["risk"], "high")

    def test_stale_compaction_cannot_force_critical(self):
        self.snapshot["context"]["used_tokens"] = 500
        self.snapshot["compactions"] = [{"timestamp": "2026-09-04T11:54:59Z",
                                         "before_tokens": 1000, "after_tokens": 999}]
        self.assertEqual(self.evaluate()["risk"], "healthy")
        self.snapshot["compactions"][0]["timestamp"] = NOW
        self.assertEqual(self.evaluate()["risk"], "critical")

    def test_recent_compaction_retains_full_repetition_window(self):
        self.snapshot["compactions"] = [
            {"timestamp": "2026-09-04T11:54:00Z", "before_tokens": 1100, "after_tokens": 850},
            {"timestamp": "2026-09-04T11:59:00Z", "before_tokens": 1080, "after_tokens": 840}]
        self.assertEqual(self.evaluate()["risk"], "critical")

    def test_boolean_or_other_snapshot_cannot_confirm_checkpoint(self):
        self.snapshot["checkpoint"] = {"completed_for_snapshot": True}
        self.assertTrue(self.evaluate()["checkpoint_required"])
        identity = self.evaluate()["snapshot_id"]
        self.snapshot["checkpoint"]["completed_for_snapshot"] = identity
        self.assertFalse(self.evaluate()["checkpoint_required"])
        self.snapshot["context"]["used_tokens"] = 860
        self.assertTrue(self.evaluate()["checkpoint_required"])

    def test_critical_never_resumes_after_matching_checkpoint(self):
        self.snapshot["context"]["used_tokens"] = 950
        self.snapshot["checkpoint"] = {"completed_for_snapshot": self.evaluate()["snapshot_id"]}
        self.assertFalse(self.evaluate()["delegation_allowed"])

    def test_stale_measurement_uses_unknown_fallback(self):
        self.snapshot.update(observed_at="2026-09-04T10:00:00Z", unattended=True,
                             checkpoint={"minutes_since": 60})
        result = self.evaluate()
        self.assertEqual(result["risk"], "unknown")
        self.assertTrue(result["checkpoint_required"])


if __name__ == "__main__":
    unittest.main()
