import copy
import unittest

from test_pilot_core import NOW, answers, candidate, outcome, packet

import pilot_core as core


def demand_answers(count=1, *, reasoning=0, code=0, context=0, kind="coding", confidence=1):
    value = answers()
    value["reasoning_depth"] = {"probabilities": {"0": 1 - reasoning, "1": 0, "2": reasoning, "3": 0}}
    value["code_interaction"] = {"noul": code}
    value["context_synthesis"] = {"noul": context}
    value["work_kind"] = {"choice": kind, "confidence": confidence}
    for i in range(count):
        for tag in core.DEMAND_GATES:
            value[f"{tag}_fit_{i}"] = {"noul": 1}
        value[f"operation_match_{i}"] = {"noul": 1}
        value[f"scope_exceeded_{i}"] = {"noul": 0}
        value[f"evidence_comparable_{i}_0"] = {"noul": 1}
    return value


def reviewed_outcome(candidate_value, demand, *, accepted=True, group="group-old", mandatory=True):
    value = outcome(candidate_value, accepted=accepted, group=group)
    value["reviewed_demands"] = [demand]
    value["gates"].append({"id": "review-" + demand.replace("_", "-"),
                           "mandatory": mandatory, "passed": accepted})
    return value


class PilotDemandProfileTests(unittest.TestCase):
    def policy(self):
        return core.policy({})

    def test_demand_profile_has_thresholded_tags_and_noncoding_code_is_not_applicable(self):
        coding = packet()
        profile = core.demand_profile(coding["task"], demand_answers(reasoning=.7, code=.5, context=.3), self.policy())
        self.assertEqual(profile, {"reasoning": "required", "code_interaction": "uncertain",
                                   "context_synthesis": "absent"})

        noncoding = packet()
        noncoding["task"]["work_kind"] = "writing"
        profile = core.demand_profile(noncoding["task"], demand_answers(code=1, kind="writing"), self.policy())
        self.assertEqual(profile["code_interaction"], "not-applicable")

    def test_demand_bands_are_independently_overridable_and_validate(self):
        policy = core.policy({"demand_bands": {"code_interaction": {"absent": .2, "required": .9}}})
        profile = core.demand_profile(packet()["task"], demand_answers(reasoning=.7, code=.85, context=.3), policy)
        self.assertEqual(profile, {"reasoning": "required", "code_interaction": "uncertain",
                                   "context_synthesis": "absent"})
        self.assertEqual(core.demand_profile(packet()["task"], demand_answers(code=.2), policy)["code_interaction"], "absent")
        with self.assertRaisesRegex(core.PilotError, "invalid-demand-band"):
            core.policy({"demand_bands": {"code_interaction": {"absent": .9, "required": .2}}})
        with self.assertRaisesRegex(core.PilotError, "invalid-demand-band"):
            core.policy({"demand_bands": {"unknown": {"absent": .2, "required": .9}}})

    def test_historical_cards_use_recorded_counts_and_coverage_only_when_history_matches(self):
        c = candidate()
        base = packet()
        records = [reviewed_outcome(c, "reasoning", group="recorded-success"),
                   outcome(c, accepted=False, group="recorded-failure")]
        prepared = core.prepare(base, self.policy(), records, NOW)
        description = prepared["cards"][0]["evidence_cohorts"][0]["task_description"]
        self.assertIn("scope parser; operation repair-parser; kind coding; risk low; complexity routine", description)
        self.assertIn("Independent groups 2; passing 1; failed 1", description)
        self.assertIn("Reviewer-confirmed demand coverage counts: reasoning=1", description)

        without_history = core.prepare(base, self.policy(), (), NOW)
        self.assertEqual(without_history["cards"][0]["evidence_cohorts"], [])

    def test_routine_interaction_demand_routes_instead_of_stopping_for_complex_scope(self):
        base = packet()
        prepared = core.prepare(base, self.policy(), clock=NOW)
        decision = core.recommendation(base, prepared, demand_answers(reasoning=1), self.policy())
        self.assertEqual(decision["action"], "route")
        self.assertIn("reasoning", decision["required_demands"])
        self.assertIn("review-reasoning", decision["review_requirements"])
        self.assertEqual(len(decision["candidate_assessments"]), 1)

    def test_missing_demand_history_does_not_disqualify_semantically_suitable_worker(self):
        cheap = candidate("cheap", estimate_usd=.01, roles=["economical"])
        strong = candidate("strong", model="model-b", model_revision="model-b-v1", estimate_usd=.10,
                           roles=["specialist"])
        base = packet(candidates=[cheap, strong])
        evidence = [outcome(cheap, group="cheap-generic"),
                    reviewed_outcome(strong, "reasoning", group="strong-reviewed")]
        prepared = core.prepare(base, self.policy(), evidence, NOW)
        decision = core.recommendation(base, prepared, demand_answers(2, reasoning=1), self.policy())
        self.assertEqual(decision["action"], "route")
        self.assertEqual(decision["configuration_id"], core.configuration_id(cheap))

    def test_matching_negative_outcomes_are_retained_for_demand_evidence(self):
        c = candidate()
        base = packet()
        evidence = [reviewed_outcome(c, "reasoning", group="passed"),
                    outcome(c, accepted=False, group="failed-without-demand-tag")]
        prepared = core.prepare(base, core.policy({}), evidence, NOW)
        decision = core.recommendation(base, prepared, demand_answers(reasoning=1),
                                       core.policy({}))
        self.assertEqual(decision["action"], "route")

    def test_failed_mandatory_demand_review_gate_vetoes_an_otherwise_accepted_outcome(self):
        c = candidate()
        base = packet()
        failed_review = reviewed_outcome(c, "reasoning", accepted=True, group="failed-review")
        failed_review["gates"][-1]["passed"] = False
        prepared = core.prepare(base, self.policy(), [failed_review], NOW)
        demand_evidence = prepared["rows"][0]["demand_evidence"]["reasoning"]
        self.assertEqual((demand_evidence["groups"], demand_evidence["passed_groups"]), (1, 0))
        decision = core.recommendation(base, prepared, demand_answers(reasoning=1), self.policy())
        self.assertEqual(decision["action"], "route")

    def test_uncertain_demands_need_reviewed_coverage_and_kind_conflict_is_diagnostic(self):
        c = candidate()
        base = packet()
        prepared = core.prepare(base, self.policy(), [outcome(c)], NOW)
        uncertain = core.recommendation(base, prepared, demand_answers(code=.5), self.policy())
        self.assertEqual(uncertain["demand_profile"]["code_interaction"], "uncertain")
        self.assertEqual(uncertain["action"], "route")

        no_demand = core.recommendation(base, prepared, demand_answers(kind="writing"), self.policy())
        self.assertEqual(no_demand["action"], "route")
        self.assertIn("work-kind-disagreement", no_demand["diagnostics"])

    def test_reviewed_demand_requires_its_mandatory_review_gate(self):
        c = candidate()
        decision = {"id": "decision-a", "task_id": "task-a", "group_id": "group-current",
                    "scope_id": "parser", "operation": "repair-parser", "risk": "low",
                    "work_kind": "coding", "complexity": "routine", "synthetic": False,
                    "acceptance_gates": ["tests-pass"],
                    "candidates": [{"configuration_id": core.configuration_id(c), "eligible": True}]}
        raw = {"decision_id": "decision-a", "configuration_id": core.configuration_id(c),
               "artifact_hash": "a" * 64, "reviewer_id": "reviewer-a", "reviewer_kind": "human",
               "review_accepted": True, "reviewed_demands": ["reasoning"],
               "gates": [{"id": "tests-pass", "mandatory": True, "passed": True},
                         {"id": "review-reasoning", "mandatory": False, "passed": True}],
               "scores": {key: 90 for key in ("coverage", "correctness", "maintainability", "clarity")},
               "costs": {key: {"usd": .01, "kind": "measured"}
                         for key in ("preparation", "worker", "review", "retry", "fallback")}, "latency_ms": 10}
        with self.assertRaisesRegex(core.PilotError, "missing-demand-review-gates"):
            core.assess_outcome(raw, decision, self.policy())

        valid = copy.deepcopy(raw)
        valid["gates"][1]["mandatory"] = True
        self.assertEqual(core.assess_outcome(valid, decision, self.policy())["reviewed_demands"], ["reasoning"])


class PilotOutcomeAdmissionTests(unittest.TestCase):
    def policy(self):
        return core.policy({})

    def decision(self, first, second, *, mode, action, selected=None, nominees=()):
        return {"id": "decision-a", "task_id": "task-a", "group_id": "history-group",
                "scope_id": "parser", "operation": "repair-parser", "risk": "low",
                "work_kind": "coding", "complexity": "routine", "synthetic": False,
                "mode": mode, "action": action, "selected_configuration_id": selected,
                "nominated_configuration_ids": list(nominees), "acceptance_gates": ["tests-pass"],
                "candidates": [{"configuration_id": core.configuration_id(first), "eligible": True},
                               {"configuration_id": core.configuration_id(second), "eligible": True}]}

    def raw(self, candidate_value, *, reviewed=(), mandatory_review=True):
        gates = [{"id": "tests-pass", "mandatory": True, "passed": True}]
        for demand in reviewed:
            gates.append({"id": "review-" + demand.replace("_", "-"),
                          "mandatory": mandatory_review, "passed": True})
        return {"decision_id": "decision-a", "configuration_id": core.configuration_id(candidate_value),
                "artifact_hash": "b" * 64, "reviewer_id": "reviewer-a", "reviewer_kind": "human",
                "review_accepted": True, "reviewed_demands": list(reviewed), "gates": gates,
                "scores": {key: 90 for key in ("coverage", "correctness", "maintainability", "clarity")},
                "costs": {key: {"usd": .01, "kind": "measured"}
                          for key in ("preparation", "worker", "review", "retry", "fallback")}, "latency_ms": 10}

    def test_active_blocked_actions_and_nonselected_candidates_cannot_admit_outcomes(self):
        first = candidate("first")
        second = candidate("second", model="model-b", model_revision="model-b-v1")
        for action in ("clarify", "repackage", "coordinator"):
            decision = self.decision(first, second, mode="active", action=action)
            with self.assertRaisesRegex(core.PilotError, "outcome-outside-decision"):
                core.assess_outcome(self.raw(first), decision, self.policy())

        route = self.decision(first, second, mode="active", action="route",
                              selected=core.configuration_id(first))
        self.assertEqual(core.assess_outcome(self.raw(first), route, self.policy())["observation_role"], "selected-route")
        with self.assertRaisesRegex(core.PilotError, "outcome-outside-decision"):
            core.assess_outcome(self.raw(second), route, self.policy())

    def test_active_experiment_admits_only_nominated_candidates(self):
        first = candidate("first")
        second = candidate("second", model="model-b", model_revision="model-b-v1")
        experiment = self.decision(first, second, mode="active", action="experiment",
                                   nominees=[core.configuration_id(first)])
        self.assertEqual(core.assess_outcome(self.raw(first), experiment, self.policy())["observation_role"], "nominated-trial")
        with self.assertRaisesRegex(core.PilotError, "outcome-outside-decision"):
            core.assess_outcome(self.raw(second), experiment, self.policy())

    def test_shadow_manual_comparisons_need_explicit_mandatory_demand_review_for_coverage(self):
        first = candidate("first")
        second = candidate("second", model="model-b", model_revision="model-b-v1")
        shadow = self.decision(first, second, mode="shadow", action="route",
                               selected=core.configuration_id(first))
        generic = core.assess_outcome(self.raw(second), shadow, self.policy())
        reviewed = core.assess_outcome(self.raw(second, reviewed=["reasoning"]), shadow, self.policy())
        self.assertEqual(generic["observation_role"], "coordinator-reviewed-comparison")
        self.assertEqual(reviewed["observation_role"], "coordinator-reviewed-comparison")
        # The historical packet's fixed clock keeps this test independent of wall-clock date.
        generic["created_at"] = reviewed["created_at"] = NOW.isoformat()

        base = packet(candidates=[second])
        generic_evidence = core.prepare(base, self.policy(), [generic], NOW)["rows"][0]["demand_evidence"]["reasoning"]
        reviewed_evidence = core.prepare(base, self.policy(), [reviewed], NOW)["rows"][0]["demand_evidence"]["reasoning"]
        self.assertEqual(generic_evidence["groups"], 0)
        self.assertEqual((reviewed_evidence["groups"], reviewed_evidence["passed_groups"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
