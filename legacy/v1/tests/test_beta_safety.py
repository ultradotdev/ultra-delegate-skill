"""Adversarial release safety checks at the public CLI boundaries."""
import argparse
import json
from pathlib import Path
import tempfile
import unittest

from test_ultra_delegation import ud, profile, task
from test_local_resources import fixture


class BetaSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / ".ultra-delegation"
        ud.cmd_init(argparse.Namespace(root=str(self.root), force=False))

    def export(self, path):
        return ud.cmd_export(argparse.Namespace(root=str(self.root), output=str(path), records=None))

    def test_report_rejects_path_traversal_and_absolute_run_ids(self):
        for run_id in ("../../escaped", str(self.base / "absolute")):
            with self.subTest(run_id=run_id), self.assertRaises(ud.UserError):
                ud.cmd_report(argparse.Namespace(root=str(self.root), records=None, report_kind="run", run_id=run_id, write=True))
        self.assertFalse((self.base / "escaped.json").exists())
        self.assertFalse((self.base / "absolute.json").exists())

    def test_export_rejects_reserved_and_non_json_destinations(self):
        for name in ("policy.json", "config.json", "settings.json", "opencode.json", "mcp.json", "README.md"):
            with self.subTest(name=name), self.assertRaises(ud.UserError):
                self.export(self.base / name)
            self.assertFalse((self.base / name).exists())

    def test_export_refuses_existing_file_and_symlink_without_modifying_target(self):
        target = self.base / "existing.json"
        target.write_text("preserve me")
        alias = self.base / "alias.json"
        alias.symlink_to(target)
        for path in (target, alias):
            with self.subTest(path=path), self.assertRaises(ud.UserError):
                self.export(path)
        self.assertEqual("preserve me", target.read_text())
        self.assertTrue(alias.is_symlink())

    def test_unknown_location_is_ineligible(self):
        candidate = profile()
        candidate.pop("execution_location")
        context = {"provider": "openai", "host": "codex", "available_models": ["gpt-5.5"], "thinking_settings": {"gpt-5.5": ["medium"]}}
        self.assertEqual((False, "unknown-location"), ud.eligible(candidate, context, ud.load_policy(self.root)))

    def test_local_model_cannot_route_despite_enabled_policy_and_passing_preflight(self):
        candidate, context, policy = fixture()
        candidate["model"] = candidate["model_revision"]
        candidate.update(task_family="code", host="opencode", thinking={"normalized": "medium", "native": "medium"}, prompt_profile="v1", tool_policy="v1")
        context.update(provider=candidate["provider"], host="opencode", available_models=[candidate["model_revision"]], thinking_settings={candidate["model_revision"]: ["medium"]})
        policy = {**ud.load_policy(self.root), **policy}
        self.assertTrue(ud.evaluate_local(candidate, context, policy)["eligible"])
        eligible, reason = ud.eligible(candidate, context, policy)
        self.assertFalse(eligible)
        self.assertIn("no verified local execution adapter", reason)

    def test_rank_prior_cannot_bypass_import_trust_requirements(self):
        context = {"provider": "openai", "host": "codex", "available_models": ["gpt-5.5", "gpt-5.6"], "thinking_settings": {"gpt-5.5": ["medium"], "gpt-5.6": ["medium"]}}
        prior = {"profile": profile(), "profile_id": ud.profile_id(profile()), "task_signature": task(),
                 "source_passed_gates": True, "fresh_at": ud.now(), "promotion": "normal", "confidence": "high",
                 "aggregate": {"evidence_count": 3, "pass_count": 3, "conservative_quality": 90}}
        for change in ({"aggregate": {"evidence_count": 3, "pass_count": 1, "conservative_quality": 90}}, {"confidence": "low"}):
            with self.subTest(change=change):
                ranked = ud.cmd_rank(argparse.Namespace(root=str(self.root), records=None, context=json.dumps(context), task=json.dumps(task()),
                    candidates=json.dumps([{"profile": profile(), "imported_prior": {**prior, **change}}])))["ranked"]
                self.assertFalse(ranked[0]["pending_verification"])
                self.assertEqual(1, ranked[0]["tier"])

    def test_prior_evidence_cannot_be_attached_to_a_different_profile(self):
        context = {"provider": "openai", "host": "codex", "available_models": ["gpt-5.5", "gpt-5.6"], "thinking_settings": {"gpt-5.5": ["medium"], "gpt-5.6": ["medium"]}}
        prior = {"profile": profile(), "profile_id": ud.profile_id(profile()), "task_signature": task(),
                 "source_passed_gates": True, "fresh_at": ud.now(), "promotion": "normal", "confidence": "high",
                 "aggregate": {"evidence_count": 3, "pass_count": 3, "conservative_quality": 90}}
        args = argparse.Namespace(root=str(self.root), records=None, context=json.dumps(context), task=json.dumps(task()),
                    candidates=json.dumps([{"profile": profile("gpt-5.6"), "imported_prior": prior}]))
        try:
            ranked = ud.cmd_rank(args)["ranked"]
        except ud.UserError:
            return  # Rejecting inconsistent identity is also an appropriate boundary.
        self.assertFalse(ranked[0]["pending_verification"])
        self.assertEqual(1, ranked[0]["tier"])


if __name__ == "__main__":
    unittest.main()
