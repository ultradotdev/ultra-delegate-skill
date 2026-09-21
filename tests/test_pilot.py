import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / ".agents/skills/ultra-delegation/scripts"
sys.path.insert(0, str(SCRIPTS))
import pilot
import pilot_core as core
import jev_transport as transport


class PilotWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.p = pilot.init_project(self.root, {"mode": "shadow", "share_summaries": True,
                                               "baseline_id": "candidate-2", "share_artifacts": True})
        self.packet = pilot.fixture()
        self.packet["synthetic"] = False

    def save(self, d):
        pilot.write_new(self.root / "decisions" / (d["id"] + ".json"), d)
        return d

    def decision(self, **kwargs):
        return self.save(pilot.route_packet(self.packet, self.p, **kwargs))

    def raw(self, d):
        raw = pilot.outcome_fixture(d, d["baseline_configuration_id"])
        raw.update(reviewer_kind="frontier", reviewer_id="independent-reviewer")
        return raw

    def test_dry_run_has_no_credentials_calls_or_writes(self):
        with patch.object(transport, "credential", side_effect=AssertionError), patch.object(transport, "request", side_effect=AssertionError):
            preview = pilot.route_packet(self.packet, self.p, dry_run=True, live=True)
        self.assertIn("payload", preview)
        self.assertEqual(4, len(preview["payload"]["state"]["candidates"]))
        self.assertEqual([], list((self.root / "decisions").iterdir()))

    def test_shadow_preserves_baseline_and_active_only_nominates_unproven(self):
        d = self.decision(live=True, call=pilot.synthetic_response, key="SECRET-SENTINEL")
        self.assertEqual("route", d["action"])
        self.assertEqual(d["baseline_configuration_id"], d["selected_configuration_id"])
        self.assertEqual("experiment", d["recommended_action"])
        active = pilot.route_packet(self.packet, {**self.p, "mode": "active"}, live=True, call=pilot.synthetic_response, key="x")
        self.assertEqual("experiment", active["action"])
        self.assertIsNone(active["selected_configuration_id"])
        self.assertEqual(4, len(active["nominated_configuration_ids"]))
        self.assertNotIn("SECRET-SENTINEL", json.dumps(d))

    def test_unavailable_service_retains_baseline_and_preserves_attempt_cost_unknown(self):
        def failed(payload, key):
            raise transport.ServiceError("deadline-exceeded", 2)
        d = self.decision(live=True, call=failed, key="x")
        self.assertEqual("unavailable", d["status"])
        self.assertEqual(d["baseline_configuration_id"], d["selected_configuration_id"])
        self.assertEqual(2, d["router"]["attempts"])
        self.assertIsNone(d["router"]["cost_usd"])

    def test_invalid_paid_response_cost_is_unknown_and_raw_fields_not_logged(self):
        def bad(payload, key):
            result, meta = pilot.synthetic_response(payload, key)
            result["answers"]["missing_requirement"]["noul"] = "SECRET-SENTINEL"
            return result, meta
        d = self.decision(live=True, call=bad, key="x")
        self.assertEqual("unavailable", d["status"])
        self.assertEqual(1, d["router"]["attempts"])
        self.assertIsNone(d["router"]["cost_usd"])
        self.assertNotIn("SECRET-SENTINEL", json.dumps(d))

    def test_explicit_choice_is_honored_only_if_eligible(self):
        self.packet["user_choice_id"] = "candidate-0"
        with patch.object(transport, "credential", side_effect=AssertionError):
            d = pilot.route_packet(self.packet, self.p, live=True)
        self.assertEqual(core.configuration_id(self.packet["candidates"][0]), d["selected_configuration_id"])
        d = pilot.route_packet(self.packet, {**self.p, "excluded_models": ["example-worker-0"]}, live=True)
        self.assertEqual("coordinator", d["action"])
        self.assertEqual(["explicit-choice-unavailable"], d["reason_codes"])

    def test_recheck_is_bound_to_saved_inputs_policy_evidence_and_freshness(self):
        d = self.decision()
        self.assertEqual("passed", pilot.recheck(self.root, d["id"], self.packet)["recheck"])
        changed = copy.deepcopy(self.packet); changed["task"]["input_tokens"] += 1
        with self.assertRaisesRegex(core.PilotError, "inputs-changed"):
            pilot.recheck(self.root, d["id"], changed)
        pilot.observe(self.root, self.raw(d))
        with self.assertRaisesRegex(core.PilotError, "evidence-changed"):
            pilot.recheck(self.root, d["id"], self.packet)

    def test_synthetic_routes_cannot_be_dispatched(self):
        self.packet["synthetic"] = True
        d = self.decision()
        with self.assertRaisesRegex(core.PilotError, "synthetic-decision"):
            pilot.recheck(self.root, d["id"], self.packet)

    def test_disabled_security_never_reads_credentials_or_calls_service(self):
        d = self.decision()
        with patch.object(transport, "credential", side_effect=AssertionError), patch.object(transport, "request", side_effect=AssertionError):
            o = pilot.observe(self.root, self.raw(d), security_input={"invalid": "ignored"}, live=True)
        self.assertTrue(o["accepted"])
        self.assertEqual("not_checked", o["security"]["status"])

    def test_security_failure_is_advisory_and_redacted(self):
        d = self.decision()
        def fail(payload, key):
            raise RuntimeError("SECRET-PROVIDER-ERROR")
        o = pilot.observe(self.root, self.raw(d), security_input={"requirements": ["Do not expose secrets"], "excerpts": ["PRIVATE-CODE"], "validation_summary": "Reviewed excerpts"}, security_check=True, live=True, call=fail, key="SECRET-KEY")
        self.assertTrue(o["accepted"])
        self.assertEqual("unavailable", o["security"]["status"])
        encoded = json.dumps(o)
        for value in ("SECRET-PROVIDER-ERROR", "PRIVATE-CODE", "SECRET-KEY"):
            self.assertNotIn(value, encoded)

    def test_credential_timeout_preserves_route_and_optional_observation(self):
        with patch.object(transport, 'credential', side_effect=transport.ServiceError('credential-store-timeout')), patch.object(transport, 'request', side_effect=AssertionError):
            d = self.decision(live=True)
            self.assertEqual(d['action'], 'route')
            self.assertEqual(d['reason_codes'], ['credential-store-timeout'])
            self.assertEqual(d['router']['attempts'], 0)
            packet = {'requirements':['Authorization required'], 'excerpts':['selected-code'], 'validation_summary':'independent checks passed'}
            o = pilot.observe(self.root, self.raw(d), security_input=packet, security_check=True, live=True)
        self.assertTrue(o['accepted'])
        self.assertEqual(o['security']['status'], 'unavailable')
        self.assertEqual(o['security']['reason_codes'], ['credential-store-timeout'])
        self.assertEqual(o['security']['attempts'], 0)

    def test_security_findings_do_not_override_independent_verdict(self):
        d = self.decision()
        def finding(payload, key):
            result, meta = pilot.synthetic_response(payload, key)
            result["answers"]["material_vulnerability"]["noul"] = 0.95
            return result, meta
        packet = {"requirements": ["Authorization required"], "excerpts": ["selected-code"], "validation_summary": "tests passed"}
        o = pilot.observe(self.root, self.raw(d), security_input=packet, security_check=True, live=True, call=finding, key="x")
        self.assertTrue(o["accepted"])
        self.assertEqual("fail", o["security"]["status"])

    def test_artifact_sharing_is_independent_from_routing(self):
        p = {**self.p, "share_artifacts": False}
        with patch.object(transport, "credential", side_effect=AssertionError):
            s = pilot.security_assessment({}, p, True, live=True)
        self.assertEqual(["artifact-sharing-disabled"], s["reason_codes"])
        self.assertEqual("unavailable", s["status"])

    def test_duplicate_outcome_rejected_before_paid_security(self):
        d = self.decision()
        raw = self.raw(d)
        pilot.observe(self.root, raw)
        with patch.object(pilot, "security_assessment", side_effect=AssertionError):
            with self.assertRaises(FileExistsError):
                pilot.observe(self.root, raw, security_check=True, live=True)

    def test_incomplete_template_cannot_poison_learning(self):
        d = self.decision()
        raw = pilot.outcome_template(d, "candidate-0")
        with self.assertRaises(core.PilotError):
            pilot.observe(self.root, raw)

    def test_report_renders_pending_and_redacts_task_text(self):
        d = self.decision()
        paths = pilot.report(self.root)
        self.assertTrue(Path(paths["html"]).is_file())
        text = Path(paths["json"]).read_text()
        self.assertNotIn(self.packet["task"]["summary"], text)
        self.assertNotIn("scope_envelope", text)

    def test_cli_diagnostics_do_not_echo_unknown_secret_arguments(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            with self.assertRaises(SystemExit):
                pilot.main(["--SECRET-KEY=do-not-print"])
        self.assertNotIn("do-not-print", err.getvalue())


if __name__ == "__main__":
    unittest.main()
