import json
from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / ".agents/skills/ultra-delegation/scripts"
sys.path.insert(0, str(SCRIPTS))
import pilot_report as report


def decision():
    return {
        "schema": "ultra-pilot-decision-v1", "id": "decision-1", "created_at": "now",
        "task_id": "security-task", "scope_id": "repo", "synthetic": False,
        "mode": "active", "status": "ok", "action": "route",
        "selected_configuration_id": "worker", "baseline_configuration_id": "worker",
        "recommended_action": "route", "recommended_configuration_id": "worker",
        "candidates": [{"id": "worker", "configuration_id": "worker", "model": "model",
                        "effort": "low", "eligible": True, "reasons": [], "shortlisted": True,
                        "evidence": {}}],
        "router": {"attempts": 1, "latency_ms": 1, "cost_usd": 0, "cost_kind": "measured"},
    }


def outcome(security):
    return {
        "schema": "ultra-pilot-outcome-v1", "id": "outcome-1", "decision_id": "decision-1",
        "task_id": "security-task", "group_id": "group", "scope_id": "repo",
        "configuration_id": "worker", "created_at": "now", "synthetic": False,
        "artifact_hash": "legacy", "reviewer_kind": "human", "reviewer_id": "reviewer",
        "accepted": True, "gates": [], "scores": {}, "costs": {}, "latency_ms": 4,
        "security": security,
    }


class PilotSecurityReportTests(unittest.TestCase):
    def complete_security(self):
        digest = "a" * 64
        return {
            "mode": "advisory", "status": "fail", "reason_codes": ["security-review"],
            "latency_ms": 7, "cost_usd": .003, "cost_kind": "measured", "attempts": 1,
            "model": "jev", "question_version": "pilot-security-v2",
            "input_hash": "input", "question_hash": "question", "input_tokens": 12,
            "output_tokens": 4, "assessment_id": "assessment-1", "artifact_hash": "b" * 64,
            "boundary_hash": "c" * 64, "coverage_hash": "d" * 64, "excerpt_count": 3,
            "follow_up_required": True, "reviewed": True, "disposition": "handoff",
            "requirements": [
                {"id": "auth", "mandatory": True, "violation_probability": .91,
                 "evidence_probability": .97, "signal": "strong-concern", "follow_up": True,
                 "requirement": "PRIVATE REQUIREMENT PROSE"},
                {"id": "logging", "mandatory": False, "violation_probability": .2,
                 "evidence_probability": .4, "signal": "insufficient-evidence", "follow_up": True},
            ],
            "findings": [
                {"id": "finding-1", "requirement_id": "auth", "disposition": "confirmed",
                 "severity": "high", "scope": "delivered", "coordinator_disposition": "handoff",
                 "details": "PRIVATE FINDING PROSE"},
                {"id": "finding-2", "requirement_id": "logging", "disposition": "unresolved",
                 "severity": "low", "scope": "pre-existing", "coordinator_disposition": None},
            ],
            "details_hash": digest, "details_ref": f"security-findings/{digest}.json",
            "provider_body": "PRIVATE PROVIDER BODY",
        }

    def test_projection_is_metadata_only_and_preserves_raw_telemetry(self):
        result = report.build_report([decision()], [outcome(self.complete_security())])
        security = result["outcomes"][0]["security"]
        self.assertEqual(security["assessment_id"], "assessment-1")
        self.assertEqual(security["input_tokens"], 12)
        self.assertEqual(security["output_tokens"], 4)
        self.assertEqual(security["requirements"][0]["signal"], "strong-concern")
        self.assertEqual(security["findings"][0]["severity"], "high")
        encoded = json.dumps(result)
        self.assertNotIn("PRIVATE REQUIREMENT PROSE", encoded)
        self.assertNotIn("PRIVATE FINDING PROSE", encoded)
        self.assertNotIn("PRIVATE PROVIDER BODY", encoded)

    def test_firstscreen_and_details_show_review_state_without_claiming_security(self):
        result = report.build_report([decision()], [outcome(self.complete_security())])
        attempt = result["overview"][0]["attempts"][0]
        self.assertEqual(attempt["security"], "completed")
        self.assertEqual(attempt["security_summary"]["confirmed"], 1)
        self.assertEqual(attempt["security_summary"]["unresolved"], 1)
        self.assertEqual(attempt["security_summary"]["requirement_ids"], ["auth", "logging"])
        page = report.render_html(result)
        self.assertIn("confirmed 1, unresolved 1", page)
        self.assertIn("requirements auth, logging; probabilities auth: violation 0.91, evidence 0.97", page)
        self.assertIn("excerpts 3; follow-up required; disposition handoff", page)
        self.assertIn("Violation probability", page)
        self.assertIn("0.91", page)
        self.assertIn("security-findings/" + "a" * 64 + ".json", page)
        self.assertIn('href="../security-findings/' + "a" * 64 + '.json"', page)

    def test_native_review_metadata_remains_visible_when_screening_was_off(self):
        security = self.complete_security()
        security.update(mode="off", status="not_checked", disposition="completed",
                        requirements=[], follow_up_required=False)
        result = report.build_report([decision()], [outcome(security)])
        attempt = result["overview"][0]["attempts"][0]
        self.assertEqual(attempt["security"], "off")
        page = report.render_html(result)
        self.assertIn("off; confirmed 1, unresolved 1", page)
        self.assertIn("security off<details>", page)
        self.assertIn("Disposition:</b> completed", page)

    def test_details_reference_is_exact_relative_hash_path_and_injection_is_dropped(self):
        security = self.complete_security()
        security["details_ref"] = 'security-findings/../../x"><script>alert(1)</script>.json'
        security["requirements"].append({
            "id": '<img src=x onerror=alert(1)>', "mandatory": True,
            "violation_probability": 1, "evidence_probability": 1,
            "signal": "strong-concern", "follow_up": True,
        })
        result = report.build_report([decision()], [outcome(security)])
        clean = result["outcomes"][0]["security"]
        self.assertIsNone(clean["details_ref"])
        self.assertEqual([item["id"] for item in clean["requirements"]], ["auth", "logging"])
        page = report.render_html(result)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertNotIn("onerror=alert(1)", page)
        self.assertIn("Local evidence reference:</b> unavailable", page)

    def test_old_and_unavailable_records_remain_explicit(self):
        old = report.build_report([decision()], [outcome({"mode": "advisory", "status": "pass"})])
        clean = old["outcomes"][0]["security"]
        self.assertEqual(clean["requirements"], [])
        self.assertEqual(clean["findings"], [])
        self.assertIn("no concern detected in assessed evidence", report.render_html(old))

        unavailable = report.build_report(
            [decision()], [outcome({"mode": "advisory", "status": "unavailable", "disposition": "unavailable"})])
        self.assertEqual(unavailable["overview"][0]["attempts"][0]["security"], "unavailable")
        page = report.render_html(unavailable)
        self.assertIn("security advisory unavailable", page)
        self.assertNotIn("secure</", page.lower())

    def test_pending_saved_assessment_is_bound_to_attempt_without_becoming_outcome(self):
        artifact_hash = "e" * 64
        request = {
            "schema": "ultra-pilot-request-v1", "id": "request-1", "task_id": "security-task",
            "decision_id": "decision-1", "decision_history": ["decision-1"], "state": "in-progress",
            "attempts": [{"id": "attempt-1", "decision_id": "decision-1", "configuration_id": "worker",
                          "kind": "initial", "state": "completed", "artifact_hash": artifact_hash}],
        }
        assessment = self.complete_security()
        assessment.update(
            schema="ultra-pilot-security-v1", assessment_id="assessment-pending",
            artifact_hash=artifact_hash, status="indeterminate", disposition="pending", reviewed=False,
            findings=[], details_hash=None, details_ref=None, cost_usd=.003, cost_kind="measured",
            binding={"request_id": "request-1", "attempt_id": "attempt-1",
                     "decision_id": "decision-1", "artifact_hash": artifact_hash},
        )
        assessment["requirements"] = [{
            "id": "auth", "mandatory": True, "violation_probability": .96,
            "evidence_probability": .25, "signal": "insufficient-evidence", "follow_up": True,
        }]
        result = report.build_report([decision()], [], [request], [assessment])
        self.assertEqual(result["summary"]["outcomes"], 0)
        self.assertEqual(len(result["security_assessments"]), 1)
        attempt = result["overview"][0]["attempts"][0]
        self.assertEqual(attempt["security_source"], "assessment")
        self.assertEqual(attempt["security"], "completed")
        self.assertTrue(attempt["security_summary"]["follow_up_required"])
        self.assertEqual(attempt["security_summary"]["disposition"], "pending")
        self.assertAlmostEqual(result["summary"]["cost"]["usd"], .003)
        page = report.render_html(result)
        self.assertIn("violation 0.96, evidence 0.25 (insufficient-evidence)", page)
        self.assertIn("follow-up required; disposition pending", page)

    def test_outcome_attached_assessment_is_not_counted_or_exposed_twice(self):
        artifact_hash = "f" * 64
        request = {
            "schema": "ultra-pilot-request-v1", "id": "request-1", "task_id": "security-task",
            "decision_id": "decision-1", "decision_history": ["decision-1"], "state": "accepted",
            "attempts": [{"id": "attempt-1", "decision_id": "decision-1", "configuration_id": "worker",
                          "kind": "initial", "state": "accepted", "artifact_hash": artifact_hash,
                          "outcome_id": "outcome-1"}],
        }
        security = self.complete_security()
        security.update(assessment_id="assessment-attached", artifact_hash=artifact_hash, cost_usd=.003)
        attached_outcome = outcome(security)
        attached_outcome.update(request_id="request-1", attempt_id="attempt-1", attempt_kind="initial")
        assessment = dict(security, schema="ultra-pilot-security-v1",
                          binding={"request_id": "request-1", "attempt_id": "attempt-1",
                                   "decision_id": "decision-1", "artifact_hash": artifact_hash})
        result = report.build_report([decision()], [attached_outcome], [request], [assessment])
        self.assertEqual(result["security_assessments"], [])
        self.assertEqual(result["overview"][0]["attempts"][0]["security_source"], "outcome")
        self.assertAlmostEqual(result["summary"]["cost"]["usd"], .003)

    def test_saved_assessment_with_different_artifact_is_not_attached(self):
        attempt_hash, other_hash = "1" * 64, "2" * 64
        request = {
            "schema": "ultra-pilot-request-v1", "id": "request-1", "task_id": "security-task",
            "decision_id": "decision-1", "decision_history": ["decision-1"], "state": "in-progress",
            "attempts": [{"id": "attempt-1", "decision_id": "decision-1", "configuration_id": "worker",
                          "kind": "initial", "state": "completed", "artifact_hash": attempt_hash}],
        }
        assessment = self.complete_security()
        assessment.update(schema="ultra-pilot-security-v1", assessment_id="assessment-other",
                          artifact_hash=other_hash,
                          binding={"request_id": "request-1", "attempt_id": "attempt-1",
                                   "decision_id": "decision-1", "artifact_hash": other_hash})
        result = report.build_report([decision()], [], [request], [assessment])
        self.assertEqual(result["security_assessments"], [])
        attempt = result["overview"][0]["attempts"][0]
        self.assertIsNone(attempt["security_source"])
        self.assertEqual(attempt["security"], "unavailable")


if __name__ == "__main__":
    unittest.main()
