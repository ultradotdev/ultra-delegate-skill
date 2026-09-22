"""Selection choices are transparent, provisional, and never worker qualification."""
import copy
import unittest

from test_pilot_core import NOW, candidate, outcome, packet
from test_pilot_demands import demand_answers
import pilot_core as core
import pilot_questions as questions


def hint(rank, **overrides):
    return {"rank": rank, "basis": "provider-relative-price-v1",
            "source_url": "https://provider.example/pricing", "checked_on": "2026-09-01", **overrides}


class PilotSelectionTests(unittest.TestCase):
    def candidates(self):
        return [candidate("baseline", estimate_usd=None),
                candidate("challenger", model="model-b", model_revision="model-b-v1", estimate_usd=None)]

    def recommend(self, candidates=None, *, policy=None, records=(), values=None, reverse=False):
        candidates = candidates or self.candidates()
        task = packet(candidates=candidates[::-1] if reverse else candidates)
        p = core.policy({"baseline_id": "baseline", **(policy or {})})
        prep = core.prepare(task, p, records, NOW)
        a = demand_answers(len(candidates), reasoning=1, code=1, context=1)
        for i, row in enumerate(prep["shortlist"]):
            for key, value in (values or {}).get(row["id"], {}).items():
                a[f"{key}_{i}"] = {"noul": value}
        return core.recommendation(task, prep, a, p)

    def test_defaults_and_invalid_preferences(self):
        self.assertEqual(core.policy()["selection_preference"], "efficiency_hints")
        self.assertEqual(core.policy()["bakeoff"], "auto")
        for name, value in (("selection_preference", "cheapest-guaranteed"), ("bakeoff", "maybe")):
            with self.assertRaises(core.PilotError): core.policy({name: value})
        for name in ("reasoning_fit", "code_interaction_fit", "context_synthesis_fit"):
            self.assertEqual(core.policy()["thresholds"][name], .85)

    def test_unknown_cost_prefers_fit_not_baseline(self):
        result = self.recommend(values={"baseline": {"reasoning_fit": .86}, "challenger": {"reasoning_fit": .99}})
        self.assertEqual(result["configuration_id"], core.configuration_id(self.candidates()[1]))
        self.assertEqual(result["selection_basis"]["method"], "reviewed-outcomes-and-fit")
        self.assertNotIn("baseline", str(result["selection_basis"]))

    def test_each_applicable_fit_has_inclusive_threshold(self):
        for tag in core.DEMAND_GATES:
            name = tag + "_fit"
            at = self.recommend([candidate()], values={"candidate-a": {name: .85}})
            below = self.recommend([candidate()], values={"candidate-a": {name: .849}})
            self.assertEqual(at["action"], "route")
            self.assertEqual(below["action"], "coordinator")
            self.assertEqual(below["candidate_assessments"][0]["reason_codes"], [tag.replace("_", "-") + "-fit-insufficient"])

    def test_absent_and_noncode_dimensions_cannot_exclude(self):
        task = packet(); task["task"]["work_kind"] = "writing"
        p = core.policy(); prep = core.prepare(task, p, clock=NOW)
        a = demand_answers(code=1, kind="writing")
        for tag in core.DEMAND_GATES: a[tag + "_fit_0"] = {"noul": 0}
        result = core.recommendation(task, prep, a, p)
        self.assertEqual(result["action"], "route")
        self.assertEqual(result["candidate_assessments"][0]["applicable_fits"], [])

    def test_uncertain_demand_requires_review_without_prequalifying_capability(self):
        task = packet(); p = core.policy(); prep = core.prepare(task, p, clock=NOW)
        answers = demand_answers(reasoning=.5, code=.5, context=.5)
        for tag in core.DEMAND_GATES: answers[tag + "_fit_0"] = {"noul": .5}
        result = core.recommendation(task, prep, answers, p)
        self.assertEqual(result["action"], "route")
        self.assertEqual(result["candidate_assessments"][0]["applicable_fits"], [])
        self.assertEqual(set(result["review_requirements"]), set(core.DEMAND_GATES.values()))

    def test_comparable_estimates_precede_hints(self):
        cs = self.candidates()
        cs[0].update(estimate_usd=.02, efficiency_hint=hint(5))
        cs[1].update(estimate_usd=.03, efficiency_hint=hint(0))
        result = self.recommend(cs)
        self.assertEqual(result["configuration_id"], core.configuration_id(cs[0]))
        self.assertEqual(result["selection_basis"]["method"], "comparable-cost-estimates")

    def test_current_same_basis_hints_guide_without_inventing_cost(self):
        cs = self.candidates()
        cs[0]["efficiency_hint"] = hint(4); cs[1]["efficiency_hint"] = hint(1)
        result = self.recommend(cs)
        self.assertEqual(result["configuration_id"], core.configuration_id(cs[1]))
        self.assertEqual(result["selection_basis"]["method"], "dated-efficiency-hints")
        rows = core.prepare(packet(candidates=cs), core.policy(), clock=NOW)["rows"]
        self.assertTrue(all(r["estimate_usd"] is None for r in rows))
        self.assertNotIn("source_url", str(rows))

    def test_missing_stale_future_and_incomparable_hints_fall_back_to_fit(self):
        for invalid in (None, hint(0, checked_on="2025-01-01"), hint(0, checked_on="2027-01-01"), hint(0, basis="other-scale")):
            cs = self.candidates(); cs[0]["efficiency_hint"] = hint(2)
            cs[1]["efficiency_hint"] = invalid
            result = self.recommend(cs, values={"baseline": {"reasoning_fit": .86}})
            self.assertEqual(result["configuration_id"], core.configuration_id(cs[1]))
            self.assertEqual(result["selection_basis"]["method"], "reviewed-outcomes-and-fit")

    def test_strongest_fit_uses_local_review_immediately_and_ignores_economy(self):
        cs = self.candidates(); cs[0]["estimate_usd"] = .001; cs[1]["estimate_usd"] = .1
        observed = outcome(cs[1]); observed["reviewed_demands"] = list(core.DEMAND_GATES)
        observed["gates"] += [{"id": gate, "mandatory": True, "passed": True} for gate in core.DEMAND_GATES.values()]
        result = self.recommend(cs, records=[observed], policy={"selection_preference": "strongest_fit"},
                                values={"challenger": {"reasoning_fit": .86}})
        self.assertEqual(result["configuration_id"], core.configuration_id(cs[1]))
        self.assertEqual(result["selection_basis"]["method"], "reviewed-outcomes-and-fit")

    def test_comparable_failure_demotes_economical_candidate(self):
        cs = self.candidates(); cs[0]["estimate_usd"] = .001; cs[1]["estimate_usd"] = .1
        result = self.recommend(cs, records=[outcome(cs[0], accepted=False)])
        self.assertEqual(result["configuration_id"], core.configuration_id(cs[1]))
        # Incomparable history must not punish the candidate.
        other = self.recommend(cs, records=[outcome(cs[0], accepted=False)], values={"baseline": {"evidence_comparable_0": 0}})
        self.assertEqual(other["configuration_id"], core.configuration_id(cs[0]))

    def test_candidate_order_does_not_change_ties_or_identity(self):
        first = self.recommend(); second = self.recommend(reverse=True)
        self.assertEqual(first["configuration_id"], second["configuration_id"])
        cs = self.candidates(); before = core.configuration_id(cs[0]); cs[0]["efficiency_hint"] = hint(1)
        self.assertEqual(before, core.configuration_id(cs[0]))
        self.assertNotEqual(core.digest(packet(candidates=self.candidates())), core.digest(packet(candidates=cs)))

    def test_hints_validate_provenance_and_date(self):
        for change in ({"rank": -1}, {"rank": True}, {"checked_on": "2026-09-99"}, {"checked_on": "20260901"},
                       {"source_url": "http://example.org"}, {"source_url": "https://user:secret@example.org"},
                       {"source_url": "https://example.org?api_key=secret"}, {"source_url": "https://["}, {"source_url": "https://invalid host.example"}):
            cs = self.candidates(); cs[0]["efficiency_hint"] = {**hint(0), **change}
            with self.assertRaises(core.PilotError): core.validate_packet(packet(candidates=cs))

    def test_atomic_fit_questions_use_original_state_not_other_answers(self):
        registry = {entry["id_template"]: entry for entry in questions.ROUTING_REGISTRY}
        for tag in core.DEMAND_GATES:
            entry = registry[tag + "_fit_{i}"]
            self.assertEqual(entry["primitive"], "noul")
            self.assertEqual(entry["state_deps"][0], "task")
            self.assertIn("capability_description", " ".join(entry["state_deps"]))
            self.assertFalse(any("answer" in dep for dep in entry["state_deps"]))
            self.assertIn("prior", entry["criteria"]["true"])


if __name__ == "__main__": unittest.main()
