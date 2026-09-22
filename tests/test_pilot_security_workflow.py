"""End-to-end workflow binding for security screening and independent review."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/skills/ultra-delegation/scripts"))
import pilot
import pilot_convenience as convenience
import pilot_core as core
import pilot_security as security
import pilot_workflow as workflow


class SecurityWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.policy = pilot.init_project(self.root, {
            "mode": "active",
            "share_summaries": True,
            "share_artifacts": True,
            "baseline_id": "candidate-2",
            "workflow": {"max_attempts": 4},
        })
        self.packet = pilot.fixture()
        self.packet["synthetic"] = False
        self.decision = pilot.route_packet(
            self.packet, self.policy, live=True, call=pilot.synthetic_response, key="fixture"
        )
        pilot.write_new(self.root / "decisions" / (self.decision["id"] + ".json"), self.decision)
        self.request = workflow.start(self.root, self.decision, self.packet, self.policy, "off")
        self.calls = 0

    def service(self, violation, sufficient=.99):
        def invoke(payload, key):
            self.calls += 1
            response, usage = pilot.synthetic_response(payload, key)
            for name in response["answers"]:
                if name.startswith("violation_"):
                    response["answers"][name]["noul"] = violation
                elif name.startswith("sufficient_"):
                    response["answers"][name]["noul"] = sufficient
            return response, usage
        return invoke

    def complete(self, attempt_id, artifact):
        request = convenience.event(
            self.root, self.request["id"], attempt_id, "launching", packet=self.packet
        )
        attempt = workflow._attempt(request, attempt_id)
        request = convenience.event(
            self.root, request["id"], attempt_id, "dispatched",
            run_id="native-" + attempt_id,
            configuration_id=attempt["configuration_id"],
            checkout_hash="a" * 64,
            base_revision="base",
        )
        self.request = convenience.event(
            self.root, request["id"], attempt_id, "completed", artifact_hash=artifact
        )
        return workflow._attempt(self.request, attempt_id)

    def security_input(self, excerpt="def delivered(): return 'toy'"):
        boundaries = copy.deepcopy(self.packet["task"]["boundaries"])
        return {
            "boundaries": boundaries,
            "requirements": copy.deepcopy(boundaries["security_requirements"]["items"]),
            "excerpts": [excerpt],
            "validation_summary": "Focused local tests completed.",
        }

    def review_raw(self, attempt_id, accepted=True):
        attempt = workflow._attempt(workflow.get(self.root, self.request["id"]), attempt_id)
        raw = pilot.outcome_fixture(self.decision, attempt["configuration_id"], accepted)
        raw.update(
            artifact_hash=attempt["artifact_hash"],
            reviewer_id="independent-frontier",
            reviewer_kind="frontier",
            worker_id=attempt["run_id"],
        )
        return raw

    def findings(self, assessment, artifact, *, disposition="dismissed", scope="delivered",
                 requirement_id="BOUND", reviewer="security-reviewer"):
        requirement = self.packet["task"]["boundaries"]["security_requirements"]["items"][0]
        if requirement_id == "BOUND":
            requirement_id = requirement["id"]
        return {
            "assessment_id": assessment["assessment_id"],
            "artifact_hash": artifact,
            "reviewer_id": reviewer,
            "reviewer_kind": "frontier",
            "reviewed_requirements": [requirement["id"]],
            "findings": [{
                "id": "finding-1",
                "requirement_id": requirement_id,
                "disposition": disposition,
                "severity": "high" if disposition == "confirmed" else "low",
                "scope": scope,
                "coordinator_disposition": None,
                "location": "toy.py:1",
                "evidence": "Independent local review of the delivered toy artifact.",
                "consequence": "The finding is confined to the synthetic workflow fixture.",
                "correction": "Apply the bounded repair and reassess the new artifact.",
            }],
        }

    def screen(self, attempt_id, packet, violation):
        return security.workflow_security(
            self.root, self.request["id"], attempt_id, packet,
            live=True, call=self.service(violation), key="mock-service",
        )

    def test_rejected_security_review_repair_gets_fresh_assessment_and_accepts(self):
        first = self.complete("attempt-1", "b" * 64)
        packet = self.security_input("def delivered(): return unsafe_value")
        assessment = self.screen(first["id"], packet, .95)
        self.assertEqual(assessment["next_step"], "independent-security-review")
        self.assertTrue(assessment["follow_up_required"])

        # The explicit workflow-security result remains binding even when the
        # workflow-review invocation does not repeat the screen flag or packet.
        with self.assertRaisesRegex(core.PilotError, "security-follow-up-required"):
            convenience.review(self.root, self.request["id"], first["id"], self.review_raw(first["id"]))

        confirmed = self.findings(assessment, first["artifact_hash"], disposition="confirmed")
        self.request = convenience.review(
            self.root, self.request["id"], first["id"], self.review_raw(first["id"]),
            repairable=True, findings_hash=core.digest(confirmed), security_findings=confirmed,
        )
        self.assertEqual(workflow._attempt(self.request, first["id"])["state"], "rejected")
        repair = self.request["attempts"][-1]
        self.assertEqual((repair["kind"], repair["parent_attempt_id"]), ("repair", first["id"]))

        repaired = self.complete(repair["id"], "c" * 64)
        fresh = self.screen(repaired["id"], self.security_input("def delivered(): return safe_value"), .01)
        self.assertNotEqual(fresh["assessment_id"], assessment["assessment_id"])
        self.assertEqual(fresh["next_step"], "workflow-review")
        self.assertFalse(fresh["follow_up_required"])
        self.request = convenience.review(
            self.root, self.request["id"], repaired["id"], self.review_raw(repaired["id"])
        )
        self.assertEqual((self.request["state"], self.request["accepted_attempt_id"]),
                         ("accepted", repaired["id"]))
        self.assertEqual(self.calls, 2)

    def test_duplicate_review_rejects_changed_findings_and_excerpts(self):
        attempt=self.complete('attempt-1','f'*64)
        packet=self.security_input()
        assessment=self.screen(attempt['id'],packet,.95)
        raw=self.review_raw(attempt['id'])
        document=self.findings(assessment,attempt['artifact_hash'])
        accepted=convenience.review(self.root,self.request['id'],attempt['id'],raw,security_findings=document)
        self.assertEqual(accepted['state'],'accepted')
        changed=self.findings(assessment,attempt['artifact_hash'],disposition='confirmed')
        with self.assertRaisesRegex(core.PilotError,'security-review-changed'):
            convenience.review(self.root,self.request['id'],attempt['id'],raw,security_findings=changed)
        with self.assertRaisesRegex(core.PilotError,'security-inputs-changed'):
            convenience.review(self.root,self.request['id'],attempt['id'],raw,security_input=self.security_input('changed'))
        self.assertEqual(convenience.review(self.root,self.request['id'],attempt['id'],raw,security_findings=document),accepted)
        self.assertEqual(self.calls,1)

    def test_interrupted_finding_publication_and_duplicate_review_are_idempotent(self):
        attempt = self.complete("attempt-1", "d" * 64)
        packet = self.security_input()
        assessment = self.screen(attempt["id"], packet, .95)
        document = self.findings(assessment, attempt["artifact_hash"])
        raw = self.review_raw(attempt["id"])
        original = security.publish_findings
        interrupted = {"raised": False}

        def publish_then_interrupt(*args, **kwargs):
            result = original(*args, **kwargs)
            if not interrupted["raised"]:
                interrupted["raised"] = True
                raise KeyboardInterrupt()
            return result

        with patch.object(security, "publish_findings", side_effect=publish_then_interrupt):
            with self.assertRaises(KeyboardInterrupt):
                convenience.review(
                    self.root, self.request["id"], attempt["id"], raw,
                    security_findings=document,
                )
        self.assertFalse(list((self.root / "outcomes").glob("*.json")))

        first = convenience.review(
            self.root, self.request["id"], attempt["id"], raw,
            security_findings=document,
        )
        duplicate = convenience.review(
            self.root, self.request["id"], attempt["id"], raw,
            security_findings=document,
        )
        self.assertEqual(first, duplicate)
        self.assertEqual(first["state"], "accepted")
        self.assertEqual(len(list((self.root / "outcomes").glob("*.json"))), 1)
        self.assertEqual(len(list((self.root / "security-findings").glob("*.json"))), 1)
        self.assertEqual(self.calls, 1)

    def test_review_scope_and_identity_gates_fail_closed(self):
        attempt = self.complete("attempt-1", "e" * 64)
        assessment = self.screen(attempt["id"], self.security_input(), .95)
        raw = self.review_raw(attempt["id"])
        cases = [
            ("task-obligation-not-unrelated", self.findings(
                assessment, attempt["artifact_hash"], disposition="confirmed", scope="pre-existing")),
            ("unknown-security-requirement", self.findings(
                assessment, attempt["artifact_hash"], requirement_id="not-in-contract")),
            ("security-artifact-changed", self.findings(assessment, "f" * 64)),
            ("worker-cannot-review-self", self.findings(
                assessment, attempt["artifact_hash"], reviewer=attempt["run_id"])),
        ]
        for message, document in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(core.PilotError, message):
                    convenience.review(
                        self.root, self.request["id"], attempt["id"], raw,
                        security_findings=document,
                    )
        self.assertFalse(list((self.root / "outcomes").glob("*.json")))

    def test_changed_security_packets_cannot_rebind_saved_assessment(self):
        attempt = self.complete("attempt-1", "1" * 64)
        packet = self.security_input()
        saved = self.screen(attempt["id"], packet, .01)

        changed_excerpt = copy.deepcopy(packet)
        changed_excerpt["excerpts"] = ["changed code for the same artifact"]
        with self.assertRaisesRegex(core.PilotError, "security-inputs-changed"):
            self.screen(attempt["id"], changed_excerpt, .01)

        changed_boundary = copy.deepcopy(packet)
        changed_boundary["boundaries"]["allowed_actions"]["items"] = ["Expanded action after dispatch."]
        with self.assertRaisesRegex(core.PilotError, "security-boundaries-changed"):
            self.screen(attempt["id"], changed_boundary, .01)

        changed_requirement = copy.deepcopy(packet)
        changed_requirement["requirements"][0]["requirement"] = "A substituted requirement."
        with self.assertRaisesRegex(ValueError, "security-requirements-boundary-mismatch"):
            self.screen(attempt["id"], changed_requirement, .01)

        same = self.screen(attempt["id"], copy.deepcopy(packet), .99)
        self.assertEqual(saved["assessment_id"], same["assessment_id"])
        self.assertEqual(self.calls, 1)


if __name__ == "__main__":
    unittest.main()
