import copy
import datetime as dt
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".agents/skills/ultra-delegation/scripts"
sys.path.insert(0, str(SCRIPT))
import pilot_core as core

NOW = dt.datetime(2026, 9, 20, tzinfo=dt.timezone.utc)


def candidate(identifier="candidate-a", contract="contract-v1", version="prompt-v1", **changes):
    value = {"id": identifier, "provider": "openai", "model": "model-a", "model_revision": "model-a-v1",
             "host": "codex", "adapter": "codex-native", "effort": "medium", "prompt_contract": contract,
             "prompt_version": version, "tool_policy": "tests-only", "capability_description": "Bounded parser repair.",
             "scope_envelope": "One module and tests.", "available": True, "tools": ["tests"], "modalities": [],
             "context_window": 4096, "max_output_tokens": 1024, "execution_location": "remote", "estimate_usd": 0.02,
             "roles": ["economical"]}
    value.update(changes)
    return value


def packet(**changes):
    value = {"schema": "ultra-pilot-task-v1", "task_id": "task-a", "group_id": "group-current", "synthetic": False,
             "task": {"scope_id": "parser", "summary": "Repair a parser.", "requirements": ["Keep API."],
                      "worker_boundary": "Patch plus tests.", "intended_use": "Internal reviewed release.", "risk": "low",
                      "work_kind": "coding", "operation": "repair-parser", "complexity": "routine",
                      "acceptance_gates": ["tests-pass"], "required_tools": ["tests"], "required_modalities": [],
                      "input_tokens": 100, "output_tokens": 100},
             "context": {"host": "codex", "provider": "openai", "observed_at": NOW.isoformat(), "delegation_allowed": True},
             "candidates": [candidate()]}
    value.update(changes)
    return value


def outcome(candidate_value, *, accepted=True, group="group-old", synthetic=False, complexity="routine", created_at=None, score=90, gates=None):
    return {"configuration_id": core.configuration_id(candidate_value), "scope_id": "parser", "operation": "repair-parser",
            "risk": "low", "work_kind": "coding", "complexity": complexity, "group_id": group, "synthetic": synthetic,
            "created_at": (created_at or (NOW - dt.timedelta(days=1))).isoformat(), "accepted": accepted,
            "gates": gates if gates is not None else [{"id": "tests-pass", "mandatory": True, "passed": True}],
            "scores": {key: score for key in ("coverage", "correctness", "maintainability", "clarity")},
            "costs": {key: {"usd": 0.01, "kind": "measured"} for key in ("worker", "review", "retry", "fallback")}}


def answers(extended=False):
    return {"missing_requirement": {"noul": 0}, "coordinator_coupling": {"noul": 0},
            "failure_impact": {"probabilities": {"0": 1, "1": 0, "2": 0, "3": 0}},
            "work_kind": {"choice": "coding", "confidence": 1},
            "reasoning_depth": {"probabilities": {"0": 0 if extended else 1, "1": 0, "2": 1 if extended else 0, "3": 0}},
            "context_synthesis": {"noul": 0}, "code_interaction": {"noul": 0}, "external_information": {"noul": 0},
            "operation_match_0": {"noul": 1}, "scope_exceeded_0": {"noul": 0}}


class PilotCoreTests(unittest.TestCase):
    def test_packet_requires_new_acceptance_gates_and_complexity(self):
        core.validate_packet(packet())
        missing = packet(); missing["task"].pop("acceptance_gates")
        with self.assertRaises(core.PilotError): core.validate_packet(missing)
        invalid = packet(); invalid["task"]["complexity"] = "unknown"
        with self.assertRaises(core.PilotError): core.validate_packet(invalid)

    def test_policy_uses_bounded_shortlist_and_experimental_signal_map(self):
        p = core.policy({"shortlist_limit": 12})
        self.assertEqual(p["thresholds"]["operation_match"], 0.85)
        self.assertEqual(p["thresholds"]["scope_exceeded"], 0.15)
        with self.assertRaises(core.PilotError): core.policy({"shortlist_limit": 13})

    def test_prepare_enforces_user_choice_pin_exclusions_host_and_capacity(self):
        base = packet(candidates=[candidate("candidate-a"), candidate("candidate-b", model="model-b", model_revision="model-b-v1", roles=[])])
        p = core.policy({"pin_id": "candidate-b"})
        prepared = core.prepare(base, p, clock=NOW)
        self.assertEqual(prepared["override"]["id"], "candidate-b")
        chosen = copy.deepcopy(base); chosen["user_choice_id"] = "candidate-a"
        self.assertEqual(core.prepare(chosen, p, clock=NOW)["override"]["id"], "candidate-a")
        excluded = core.prepare(base, core.policy({"excluded_models": ["model-b"]}), clock=NOW)
        self.assertIn("excluded-model", next(x for x in excluded["rows"] if x["id"] == "candidate-b")["reasons"])
        bad = packet(candidates=[candidate(host="claude-code")])
        row = core.prepare(bad, core.policy(), clock=NOW)["rows"][0]
        self.assertIn("outside-host-provider", row["reasons"])
        narrow = packet(candidates=[candidate(context_window=150)])
        self.assertIn("context-does-not-fit", core.prepare(narrow, core.policy(), clock=NOW)["rows"][0]["reasons"])

    def test_prepare_rejects_stale_capabilities(self):
        old = packet(); old["context"]["observed_at"] = (NOW - dt.timedelta(seconds=301)).isoformat()
        self.assertIn("stale-capabilities", core.prepare(old, core.policy(), clock=NOW)["rows"][0]["reasons"])

    def test_evidence_uses_prompt_contract_groups_and_real_outcomes(self):
        c = candidate(); base = packet()
        outcomes = [outcome(c, accepted=True, group="group-1"), outcome(c, accepted=False, group="group-1"),
                    outcome(c, accepted=True, group="group-2", synthetic=True),
                    outcome(c, accepted=True, group="group-3", complexity="complex")]
        row = core.prepare(base, core.policy({}), outcomes, NOW)["rows"][0]
        self.assertEqual(row["evidence"]["groups"], 2)  # duplicate group cannot inflate evidence
        self.assertEqual(row["evidence"]["passed_groups"], 1)
        changed_contract = candidate(contract="contract-v2")
        other = packet(candidates=[changed_contract])
        self.assertEqual(core.prepare(other, core.policy({}), outcomes, NOW)["rows"][0]["evidence"]["groups"], 0)
        changed_version = candidate(version="prompt-v2")
        same_contract = packet(candidates=[changed_version])
        self.assertEqual(core.prepare(same_contract, core.policy({}), outcomes, NOW)["rows"][0]["evidence"]["groups"], 2)

    def test_failed_group_has_no_success_confidence(self):
        c = candidate(); row = core.prepare(packet(), core.policy({}), [outcome(c, accepted=False)], NOW)["rows"][0]
        self.assertEqual(row["evidence"]["lower_bound"], 0)
        self.assertTrue(row["evidence"]["recent_failure"])

    def test_lax_historical_quality_cannot_qualify_a_stricter_policy(self):
        c = candidate()
        historical = outcome(c, accepted=True, score=75)
        strict = core.policy({"quality_floor": 80, "dimension_floor": 80})
        row = core.prepare(packet(), strict, [historical], NOW)["rows"][0]
        self.assertEqual((row["evidence"]["groups"], row["evidence"]["passed_groups"]), (1, 0))
        self.assertTrue(row["evidence"]["recent_failure"])

    def test_imported_unverified_history_cannot_change_evidence_cost_or_rank(self):
        expensive = candidate("candidate-expensive", estimate_usd=.05)
        economical = candidate("candidate-economical", model="model-b", model_revision="model-b-v1", estimate_usd=.04)
        imported = outcome(expensive, accepted=True, group="imported-group")
        imported["provenance"] = "imported-unverified"
        for component in imported["costs"].values():
            component["usd"] = .0001
        prepared = core.prepare(packet(candidates=[expensive, economical]), core.policy({}), [imported], NOW)
        expensive_row = next(row for row in prepared["rows"] if row["id"] == "candidate-expensive")
        self.assertEqual(expensive_row["evidence"]["groups"], 0)
        self.assertEqual(expensive_row["evidence"]["cost_observations"], 0)
        self.assertEqual(expensive_row["estimate_usd"], .05)
        self.assertEqual(prepared["baseline"]["id"], "candidate-economical")

    def test_reasoning_demand_routes_without_history_and_requires_review(self):
        base = packet(); prepared = {"shortlist": [{"configuration_id": core.configuration_id(base["candidates"][0]), "evidence": {"qualified": False}}], "cards": [{"evidence_cohorts": []}]}
        rec = core.recommendation(base, prepared, answers(extended=True), core.policy())
        self.assertEqual(rec["action"], "route")
        self.assertEqual(rec["required_demands"], ["reasoning"])
        self.assertEqual(rec["review_requirements"], ["review-reasoning"])
        self.assertEqual(base["task"]["complexity"], "routine")

    def test_assess_outcome_requires_independent_acceptance_gates(self):
        c = candidate(); decision = {"id": "decision-a", "task_id": "task-a", "group_id": "group-current", "scope_id": "parser", "operation": "repair-parser", "risk": "low", "work_kind": "coding", "complexity": "routine", "synthetic": False, "decision_policy_version": core.DECISION_POLICY_VERSION, "acceptance_gates": ["tests-pass"], "candidates": [{"configuration_id": core.configuration_id(c), "eligible": True}]}
        raw = {"decision_id": "decision-a", "configuration_id": core.configuration_id(c), "artifact_hash": "a" * 64, "worker_id": "native-worker-a", "reviewer_id": "reviewer-a", "reviewer_kind": "human", "review_accepted": True, "gates": [{"id": "tests-pass", "mandatory": True, "passed": True}], "scores": {key: 90 for key in ("coverage", "correctness", "maintainability", "clarity")}, "costs": {key: {"usd": 0.01, "kind": "measured"} for key in ("preparation", "worker", "review", "retry", "fallback")}, "latency_ms": 10}
        self.assertTrue(core.assess_outcome(raw, decision, core.policy())["accepted"])
        synthetic = copy.deepcopy(raw); synthetic["reviewer_kind"] = "synthetic"
        with self.assertRaisesRegex(core.PilotError, "synthetic-review-for-real-task"):
            core.assess_outcome(synthetic, decision, core.policy())
        missing_worker = copy.deepcopy(raw); missing_worker.pop("worker_id")
        with self.assertRaisesRegex(core.PilotError, "missing-worker-id"):
            core.assess_outcome(missing_worker, decision, core.policy())
        self_review = copy.deepcopy(raw); self_review["worker_id"] = self_review["reviewer_id"]
        with self.assertRaisesRegex(core.PilotError, "worker-cannot-review-self"):
            core.assess_outcome(self_review, decision, core.policy())
        raw["gates"] = [{"id": "other-gate", "mandatory": True, "passed": True}]
        with self.assertRaises(core.PilotError): core.assess_outcome(raw, decision, core.policy())
        raw["gates"] = [{"id": "tests-pass", "mandatory": True, "passed": True}]
        raw["gates"][0]["passed"] = False
        self.assertFalse(core.assess_outcome(raw, decision, core.policy())["accepted"])


if __name__ == "__main__":
    unittest.main()
