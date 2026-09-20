import json
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/ultra-delegation/scripts'
sys.path.insert(0, str(SCRIPTS))
import pilot_report as p


def decision(**more):
    item = {"schema":"ultra-pilot-decision-v1","id":"d1","created_at":"2026-09-20T00:00:00Z","task_id":"yarn-consolidation","scope_id":"repo","synthetic":False,"mode":"active","status":"ok","action":"route","selected_configuration_id":"small","baseline_configuration_id":"frontier","recommended_action":"route","recommended_configuration_id":"small","nominated_configuration_ids":[],"reason_codes":["evidence"],"question_version":"v1","model":"jev-1","policy_hash":"p","input_hash":"i","question_hash":"q","signals":{"fit_0":{"type":"noul","noul":0.91,"raw":"SECRET"}},"router":{"attempts":1,"latency_ms":4,"cost_usd":0.001,"cost_kind":"estimated","input_tokens":3,"output_tokens":2},"candidates":[{"id":"a","configuration_id":"small","model":"worker","effort":"low","eligible":True,"reasons":[],"shortlisted":True,"estimate_usd":0.02,"evidence":{"groups":2,"passed_groups":2,"failed_groups":0,"lower_bound":0.8,"qualified":True}}],"untrusted":"<script>alert(1)</script>"}
    item.update(more); return item

def outcome(**more):
    item = {"schema":"ultra-pilot-outcome-v1","id":"o1","decision_id":"d1","task_id":"yarn-consolidation","group_id":"g1","scope_id":"repo","configuration_id":"small","created_at":"now","synthetic":False,"artifact_hash":"h","reviewer_kind":"human","reviewer_id":"reviewer","accepted":True,"gates":[{"id":"tests","mandatory":True,"passed":True}],"scores":{"coverage":90,"correctness":91,"maintainability":88,"clarity":89},"costs":{k:{"usd":0.01,"kind":"measured"} for k in ("preparation","worker","review","retry","fallback")},"latency_ms":8,"security":{"mode":"advisory","status":"fail","reason_codes":["rule"],"latency_ms":1,"cost_usd":0.002,"cost_kind":"estimated","attempts":1},"private_prompt":"steal me"}
    item.update(more); return item


class PilotReportTests(unittest.TestCase):
    def test_empty_and_pending_are_honest(self):
        self.assertEqual(p.build_report([], [])["summary"]["decisions"], 0)
        report = p.build_report([decision()], [])
        self.assertEqual(report["summary"]["pending_decisions"], 1)
        self.assertIn("Pending - no outcome recorded", p.render_html(report))

    def test_synthetic_unknown_cost_and_advisory_security(self):
        d = decision(synthetic=True, router={"attempts":0,"latency_ms":0,"cost_usd":None,"cost_kind":"unknown"})
        o = outcome(costs={k:{"usd":None,"kind":"unknown"} for k in ("preparation","worker","review","retry","fallback")})
        report = p.build_report([d], [o]); page = p.render_html(report)
        self.assertFalse(report["summary"]["cost"]["complete"])
        self.assertIn("pending qualification", page)
        self.assertIn("advisory fail", page)
        self.assertIn("prep unknown; worker unknown", page)
        self.assertIn("$0.0020 (estimated)", page)
        self.assertIn("accepted", page)  # advisory failure does not alter acceptance

    def test_escapes_xss_and_drops_unknown_values(self):
        d = decision(task_id='<img src=x onerror=alert(1)>', signals={"fit_0":{"type":"noul","noul":.9,"reasoning":"leak"}, "bad":{"type":"unknown","text":"leak"}})
        report = p.build_report([d], [outcome()]); encoded = json.dumps(report); page = p.render_html(report)
        self.assertNotIn("SECRET", encoded); self.assertNotIn("untrusted", encoded); self.assertNotIn("private_prompt", encoded)
        self.assertNotIn("onerror=alert(1)>", page); self.assertIn("&lt;img", page)
        self.assertNotIn("reasoning", page); self.assertNotIn("bad", page)

    def test_projects_all_typed_question_uncertainty_without_legends(self):
        signals = {
            "fit_0": {"type": "noul", "noul": .91, "provider_note": "discard"},
            "work_kind": {"type": "choice", "choice": "coding", "confidence": .8,
                          "probabilities": {k: .0 for k in ("coding", "research", "writing", "data", "planning", "mixed", "other")}},
            "reasoning_depth": {"type": "score", "score": 2, "confidence": .7,
                                "probabilities": {"0": .1, "1": .2, "2": .6, "3": .1}, "legend": {"2": "untrusted"}},
        }
        signals["work_kind"]["probabilities"]["coding"] = 1
        report = p.build_report([decision(signals=signals)], [])
        clean = report["decisions"][0]["signals"]
        self.assertEqual(clean["fit_0"], {"type": "noul", "yes": .91})
        self.assertEqual(clean["work_kind"]["choice"], "coding")
        self.assertEqual(clean["reasoning_depth"]["probabilities"]["2"], .6)
        self.assertNotIn("legend", json.dumps(clean)); self.assertNotIn("provider_note", json.dumps(clean))

    def test_comparator_is_observed_not_recommendation(self):
        d = decision(selected_configuration_id="small", recommended_configuration_id="small")
        comparator = outcome(id="o2", configuration_id="frontier", accepted=False)
        report = p.build_report([d], [outcome(), comparator]); page = p.render_html(report)
        self.assertIn("frontier", page); self.assertIn("selected small", page)
        self.assertIn("no realized-savings claim", page)
        self.assertEqual(report["summary"]["acceptance"], {"passed": 1, "total": 1})

    def test_selected_pending_is_not_hidden_by_a_comparator(self):
        d = decision(selected_configuration_id="small", action="route")
        report = p.build_report([d], [outcome(configuration_id="frontier")])
        self.assertEqual(report["summary"]["pending_selected_outcomes"], 1)
        self.assertFalse(report["summary"]["whole_workload_cost"]["complete"])
        self.assertIsNone(report["summary"]["whole_workload_cost"]["usd"])
        self.assertIn("Selected worker outcome pending", p.render_html(report))

    def test_recommendation_feedback_requires_real_observations_and_inference(self):
        d = decision(mode="shadow", selected_configuration_id="frontier")
        result = p.build_report([d], [outcome(accepted=False), outcome(id="o2", configuration_id="frontier")])
        r = result["summary"]["routing"]
        self.assertEqual(r["paired_comparisons"], {"baseline_only_accepted": 1})
        self.assertEqual(r["recommended_outcomes_accepted"], 0)
        self.assertEqual(r["baseline_disagreements"], 1)
        result = p.build_report([decision(status="skipped")], [outcome()])
        self.assertEqual(result["summary"]["routing"]["inference_decisions"], 0)
        result = p.build_report([d], [outcome(configuration_id="frontier")])
        self.assertEqual(result["summary"]["routing"]["paired_comparisons_total"], 0)
        self.assertEqual(result["summary"]["routing"]["recommended_outcomes_pending"], 1)

    def test_metadata_projection_restricts_identity_and_fields(self):
        d = decision(configuration_metadata={"small": {"provider": "openai", "prompt_version": "unsafe prose", "adapter": "sk-" + "a"*40, "other": "drop"}, "unrelated": {"provider": "drop"}})
        result = p.build_report([d], [])
        self.assertEqual(result["decisions"][0]["configuration_metadata"], {"small": {"provider": "openai"}})

    def test_route_without_selection_keeps_workload_unknown(self):
        result = p.build_report([decision(selected_configuration_id=None)], [outcome()])
        self.assertIsNone(result["summary"]["whole_workload_cost"]["usd"])
        self.assertEqual(result["summary"]["pending_selected_outcomes"], 1)

    def test_whole_workload_includes_comparisons_and_unresolved_trials(self):
        result = p.build_report([decision()], [outcome(), outcome(id="other", configuration_id="frontier")])
        self.assertAlmostEqual(result["summary"]["whole_workload_cost"]["usd"], .105)
        self.assertTrue(result["summary"]["whole_workload_cost"]["complete"])
        trial = decision(action="experiment", selected_configuration_id=None)
        result = p.build_report([trial], [outcome()])
        self.assertIsNone(result["summary"]["whole_workload_cost"]["usd"])
        self.assertFalse(result["summary"]["whole_workload_cost"]["complete"])
        self.assertAlmostEqual(result["summary"]["cost"]["usd"], .053)


if __name__ == '__main__': unittest.main()
