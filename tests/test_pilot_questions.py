import copy
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".agents/skills/ultra-delegation/scripts"
sys.path.insert(0, str(SCRIPT))
import jev_transport
import pilot_questions as p


def task():
    return {"summary": "Fix parser.", "requirements": ["Keep API."], "worker_boundary": "Patch and tests.", "intended_use": "Internal review.", "scope_id": "parser", "risk": "medium", "work_kind": "coding", "operation": "repair parser", "complexity": "routine", "acceptance_gates": ["tests-pass"], "required_tools": ["tests"], "required_modalities": [], "input_tokens": 10, "output_tokens": 20}


def answer(payload):
    answers = {}
    for key, q in payload["questions"].items():
        if q["type"] == "noul": answers[key] = {"type": "noul", "noul": 0.5}
        elif q["type"] == "choice":
            options = list(q["criteria"]); answers[key] = {"type": "choice", "choice": options[0], "confidence": 1, "probabilities": {x: 1 if x == options[0] else 0 for x in options}}
        else:
            n = len(q["criteria"]); probabilities = {str(i): 1 if i == 0 else 0 for i in range(n)}
            answers[key] = {"type": "score", "score": 0, "confidence": 1, "probabilities": probabilities, "legend": {str(i): x for i, x in enumerate(q["criteria"])}}
    return {"model": payload["model"], "usage": {"input_tokens": 1, "output_tokens": 1}, "answers": answers}


class PilotQuestionTests(unittest.TestCase):
    def candidates(self):
        return [{"id": "opaque-b", "capability_description": "Parser repair.", "scope_envelope": "Single module.", "evidence_cohorts": [{"task_description": "Fix parser."}, {"task_description": "Repair lexer."}]}, {"id": "opaque-a", "capability_description": "Documentation.", "scope_envelope": "Docs only.", "evidence_cohorts": []}]

    def test_routing_coverage_wire_types_and_response_validation(self):
        payload = p.route_payload(task(), self.candidates(), "jev-1.13.0")
        expected = {"work_kind", "missing_requirement", "coordinator_coupling", "reasoning_depth", "failure_impact", "code_interaction", "context_synthesis", "external_information", "operation_match_0", "scope_exceeded_0", "operation_match_1", "scope_exceeded_1", "evidence_comparable_0_0", "evidence_comparable_0_1"}
        expected |= {f"{tag}_fit_{i}" for tag in ("reasoning", "code_interaction", "context_synthesis") for i in range(2)}
        self.assertEqual(set(payload["questions"]), expected)
        self.assertEqual(payload["questions"]["work_kind"]["type"], "choice")
        self.assertEqual(payload["questions"]["reasoning_depth"]["type"], "score")
        self.assertEqual(payload["questions"]["scope_exceeded_0"]["type"], "noul")
        clean, usage = jev_transport.validate_response(payload, answer(payload))
        self.assertEqual(set(clean), expected); self.assertEqual(usage["input_tokens"], 1)

    def test_candidate_indices_follow_supplied_order_and_projection_is_unchanged(self):
        candidates = self.candidates(); before = copy.deepcopy(candidates)
        payload = p.route_payload(task(), candidates[::-1], "jev-1.13.0")
        self.assertIn("candidates[0].capability_description", payload["questions"]["operation_match_0"]["instructions"])
        self.assertNotIn("evidence_comparable_0_0", payload["questions"])
        for dimension in ("reasoning", "code_interaction", "context_synthesis"):
            question = payload["questions"][dimension + "_fit_0"]
            self.assertIn("`candidates[0].capability_description`", question["instructions"])
            self.assertEqual(set(question["criteria"]), {"true", "false"})
        self.assertEqual(candidates, before)

    def test_dependency_question_is_single_batch_and_excludes_later_coordinator_work(self):
        payload = p.route_payload(task(), self.candidates(), "jev-1.13.0")
        question = payload["questions"]["coordinator_coupling"]
        entry = next(entry for entry in p.ROUTING_REGISTRY if entry["id_template"] == "coordinator_coupling")
        self.assertEqual(p.ROUTING_VERSION, "pilot-routing-v8")
        self.assertEqual(p.ROUTING_THRESHOLDS["coordinator_coupling"], .40)
        self.assertEqual(p.ROUTING_THRESHOLDS["missing_requirement"], .20)
        self.assertIn("Later review, acceptance, integration or deployment", question["instructions"])
        self.assertIn("unless its decision is needed to produce the deliverable", question["instructions"])
        self.assertNotIn("answer", question["instructions"].lower())
        self.assertNotIn("answer", " ".join(entry["state_deps"]).lower())

    def test_security_payload_is_all_noul_and_is_advisory(self):
        payload = p.security_payload({"requirements": ["Auth", "Audit"], "excerpts": ["x"], "validation_summary": "tests"}, "jev-1.13.0")
        self.assertEqual(set(payload["questions"]), {"enough", "requirement_0", "requirement_1", "material_vulnerability"})
        self.assertTrue(all(q["type"] == "noul" for q in payload["questions"].values()))
        jev_transport.validate_response(payload, answer(payload))
        self.assertIn("do not accept", p.manifest()["security_note"])

    def test_bounds_and_docs_freshness(self):
        candidate = self.candidates()[0]
        pool = [{**candidate, "id": "opaque-" + str(i)} for i in range(12)]
        self.assertEqual(len(p.route_payload(task(), pool, "jev-1.13.0")["state"]["candidates"]), 12)
        with self.assertRaises(ValueError): p.route_payload(task(), pool + [{**candidate, "id": "opaque-13"}], "jev-1.13.0")
        invalid = task(); invalid["acceptance_gates"] = ["bad gate"]
        with self.assertRaises(ValueError): p.route_payload(invalid, self.candidates(), "jev-1.13.0")
        invalid = task(); invalid["complexity"] = "unknown"
        with self.assertRaises(ValueError): p.route_payload(invalid, self.candidates(), "jev-1.13.0")
        self.assertEqual(p.main(["--check"]), 0)


if __name__ == "__main__": unittest.main()
