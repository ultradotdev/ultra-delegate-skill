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
        self.assertIn("Synthetic telemetry", page)
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

    def test_explicit_local_descriptions_are_copied_bounded_and_escaped(self):
        request = {"schema":"ultra-pilot-request-v1", "id":"req_1", "task_id":"yarn-consolidation", "decision_id":"d1",
                   "state":"in-progress", "attempts":[]}
        report = p.build_report([decision()], [], [request])
        self.assertNotIn("local_task_descriptions", report)
        local = p.with_task_descriptions(report, {"yarn-consolidation": "Fix <script>alert(1)</script> & verify output."})
        self.assertNotIn("local_task_descriptions", report)
        self.assertEqual(local["local_task_descriptions"]["mode"], "explicit-local-only")
        page = p.render_html(local)
        self.assertEqual(page.count("Local-only description:"), 2)
        self.assertIn("Fix &lt;script&gt;alert(1)&lt;/script&gt; &amp; verify output.", page)
        self.assertNotIn("Fix <script>", page)
        for invalid in ({"unknown-task": "description"}, {"yarn-consolidation": " "},
                        {"yarn-consolidation": "x" * (p.LOCAL_DESCRIPTION_MAX_CHARS + 1)}, []):
            with self.subTest(invalid=type(invalid).__name__), self.assertRaisesRegex(ValueError, "invalid-local-task-descriptions"):
                p.with_task_descriptions(report, invalid)

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
        self.assertIn("frontier", page); self.assertIn("Effective selected route", page)
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

    def test_demand_contract_is_allowlisted_and_shadow_repackage_stays_honest(self):
        d = decision(mode="shadow", action="route", selected_configuration_id="small", baseline_configuration_id="small",
                     recommended_action="repackage", recommended_configuration_id=None,
                     decision_policy_version="pilot-selection-v3",
                     demand_profile={"reasoning":"required", "code_interaction":"uncertain", "context_synthesis":"absent", "raw":"leak"},
                     required_demands=["reasoning", "code_interaction", "not-a-demand"],
                     review_requirements=["review-reasoning", "review-code-interaction", "unknown-review"],
                     diagnostics=["work-kind-disagreement", "untrusted"],
                     candidate_assessments=[{"configuration_id":"small", "status":"trial-required", "reason_codes":["needs-review", "<script>"],
                                             "evidence":{"groups":2,"passed_groups":1,"failed_groups":1,"lower_bound":.2,"qualified":False,"observed_mean_cost_usd":.04,"cost_observations":2,"raw":"drop"}, "raw":"drop"}])
        o = outcome(reviewed_demands=["reasoning", "invalid-demand"], private_review="drop")
        report = p.build_report([d], [o]); clean = report["decisions"][0]; page = p.render_html(report)
        self.assertEqual(clean["demand_profile"], {})  # exact demand shape is required
        self.assertEqual(clean["required_demands"], [])
        self.assertEqual(clean["review_requirements"], ["review-reasoning", "review-code-interaction"])
        self.assertEqual(clean["diagnostics"], ["work-kind-disagreement"])
        self.assertEqual(clean["candidate_assessments"][0]["status"], "trial-required")
        self.assertNotIn("raw", json.dumps(clean)); self.assertNotIn("private_review", json.dumps(report))
        self.assertEqual(report["outcomes"][0]["reviewed_demands"], [])
        self.assertEqual(report["summary"]["routing"]["action_disagreements"], 1)
        self.assertEqual(report["summary"]["routing"]["baseline_disagreements"], 0)
        self.assertIn("Shadow mode retained the baseline", page)
        self.assertIn("Nonblocking diagnostic", page)

    def test_demand_based_experiment_shows_unrun_nominees(self):
        d = decision(action="experiment", selected_configuration_id=None, recommended_action="experiment", recommended_configuration_id=None,
                     nominated_configuration_ids=["small"], decision_policy_version="pilot-selection-v3",
                     demand_profile={"reasoning":"required", "code_interaction":"absent", "context_synthesis":"not-applicable"},
                     required_demands=["reasoning"], review_requirements=["review-reasoning"],
                     candidate_assessments=[{"configuration_id":"small", "status":"trial-required", "reason_codes":["demand-review-required"],
                                             "evidence":{"groups":0,"passed_groups":0,"failed_groups":0,"lower_bound":0,"qualified":False,"observed_mean_cost_usd":None,"cost_observations":0}}])
        report = p.build_report([d], []); page = p.render_html(report)
        self.assertEqual(report["summary"]["pending_experiments"], 1)
        self.assertIn("Experiment pending", page); self.assertIn("trial-required", page)
        self.assertIn("Experiment proposal; No outcome recorded for: worker / low", page)
        self.assertIn("No worker selected", page)

    def test_shadow_baseline_copy_only_appears_when_effective_route_is_baseline(self):
        explicit_choice = decision(mode="shadow", action="route", selected_configuration_id="small", baseline_configuration_id="frontier")
        page = p.render_html(p.build_report([explicit_choice], []))
        self.assertNotIn("Shadow mode retained the baseline", page)
        retained = decision(mode="shadow", action="route", selected_configuration_id="small", baseline_configuration_id="small")
        self.assertIn("Shadow mode retained the baseline", p.render_html(p.build_report([retained], [])))

    def test_shadow_experiment_recommendation_uses_recorded_nominee_outcomes(self):
        d = decision(mode="shadow", action="route", selected_configuration_id="small", baseline_configuration_id="small",
                     recommended_action="experiment", recommended_configuration_id=None, nominated_configuration_ids=["small"])
        page = p.render_html(p.build_report([d], [outcome(configuration_id="small")]))
        self.assertIn("Experiment proposal; all nominated outcomes recorded", page)
        self.assertNotIn("No outcome recorded for", page)

    def test_observation_role_is_an_optional_allowlisted_enum(self):
        report = p.build_report([decision()], [outcome(observation_role="nominated-trial", ignored_role="leak")])
        self.assertEqual(report["outcomes"][0]["observation_role"], "nominated-trial")
        self.assertIn("nominated-trial", p.render_html(report))
        invalid = p.build_report([decision()], [outcome(observation_role="arbitrary prose")])
        self.assertIsNone(invalid["outcomes"][0]["observation_role"])

    def test_request_metrics_keep_first_failure_separate_from_repaired_success(self):
        first = outcome(id="out-initial", accepted=False, request_id="req_1", attempt_id="attempt-1", attempt_kind="initial")
        repaired = outcome(id="out-repair", accepted=True, request_id="req_1", attempt_id="attempt-2", attempt_kind="repair")
        request = {"schema":"ultra-pilot-request-v1", "id":"req_1", "task_id":"safe-task", "decision_id":"d1",
                   "state":"accepted", "accepted_attempt_id":"attempt-2", "raw_repository":"DO-NOT-SHARE",
                   "attempts":[
                       {"id":"attempt-1", "configuration_id":"small", "kind":"initial", "state":"rejected", "outcome_id":"out-initial", "artifact_hash":"a"*64},
                       {"id":"attempt-2", "configuration_id":"small", "kind":"repair", "state":"accepted", "parent_attempt_id":"attempt-1", "outcome_id":"out-repair", "artifact_hash":"b"*64, "reason_code":"test-failure"},
                   ]}
        report = p.build_report([decision(decision_policy_version="pilot-selection-v4", alternative_configuration_ids=["frontier", "raw prose"])], [first, repaired], [request])
        metrics = report["request_metrics"]
        self.assertEqual(metrics["first_attempt_success"], {"passed": 0, "total": 1, "pending": 0})
        self.assertEqual(metrics["request_success"], {"passed": 1, "total": 1})
        self.assertEqual(report["summary"]["routing"]["recommended_outcomes_accepted"], 0)
        self.assertEqual(metrics["recovery_overhead"]["attempts"], 1)
        self.assertEqual(metrics["recovery_overhead"]["cost"]["coverage"], "7/7")
        self.assertAlmostEqual(metrics["recovery_overhead"]["cost"]["usd"], .052)
        self.assertEqual(report["decisions"][0]["alternative_configuration_ids"], ["frontier"])
        self.assertNotIn("qualified", json.dumps(report["decisions"][0]))
        page = p.render_html(report)
        self.assertIn("First attempt: Not accepted", page)
        self.assertIn("<b>Accepted</b>", page)
        self.assertNotIn("DO-NOT-SHARE", json.dumps(report))

    def test_unobserved_and_canceled_attempts_remain_unknown_not_failures(self):
        request = {"schema":"ultra-pilot-request-v1", "id":"req_2", "task_id":"safe-task", "decision_id":"d1",
                   "state":"canceled", "attempts":[
                       {"id":"attempt-1", "configuration_id":"small", "kind":"initial", "state":"canceled", "reason_code":"accepted-result-available"},
                       {"id":"attempt-2", "configuration_id":"frontier", "kind":"comparison", "state":"planned"},
                   ]}
        report = p.build_report([decision()], [], [request])
        self.assertEqual(report["request_metrics"]["states"]["canceled"], 1)
        self.assertEqual(report["request_metrics"]["attempt_states"]["failed"], 0)
        self.assertEqual(report["request_metrics"]["usage"]["unknown_attempts"], 2)
        self.assertFalse(report["summary"]["cost"]["complete"])

    def test_bakeoff_success_can_deliver_after_primary_failure(self):
        first = outcome(id="out-primary", accepted=False, request_id="req_3", attempt_id="attempt-1", attempt_kind="initial")
        comparison = outcome(id="out-comparison", accepted=True, request_id="req_3", attempt_id="attempt-2", attempt_kind="comparison", configuration_id="frontier")
        request = {"schema":"ultra-pilot-request-v1", "id":"req_3", "task_id":"safe-task", "decision_id":"d1", "state":"accepted",
                   "attempts":[
                       {"id":"attempt-1", "configuration_id":"small", "kind":"initial", "state":"rejected", "outcome_id":"out-primary"},
                       {"id":"attempt-2", "configuration_id":"frontier", "kind":"comparison", "state":"accepted", "outcome_id":"out-comparison"},
                   ]}
        report = p.build_report([decision()], [first, comparison], [request])
        self.assertEqual(report["request_metrics"]["first_attempt_success"]["passed"], 0)
        self.assertEqual(report["request_metrics"]["initial_bakeoff_success"], {"passed": 1, "total": 1, "pending": 0})
        self.assertEqual(report["request_metrics"]["request_success"]["passed"], 1)

    def test_judge_and_defects_are_allowlisted_advisory_telemetry(self):
        judged = outcome(accepted=True, critical_defects=["authorization-bypass", "raw prose leak"],
                         judge={"mode":"advisory", "status":"scored", "rubric_version":"pilot-quality-judge-v1",
                                "model":"jev-1", "scores":{"coverage":90, "scope":80, "evidence":70, "clarity":60, "hidden":100},
                                "cost_usd":.004, "cost_kind":"estimated", "latency_ms":8, "attempts":1,
                                "reason_codes":["advisory-only", "PRIVATE_EXCERPT"], "excerpts":["PRIVATE_EXCERPT"], "accepted":True})
        report = p.build_report([decision()], [judged])
        clean = report["outcomes"][0]
        self.assertEqual(clean["critical_defects"], ["authorization-bypass"])
        self.assertEqual(clean["judge"]["scores"], {"coverage":90, "scope":80, "evidence":70, "clarity":60})
        self.assertNotIn("accepted", clean["judge"])
        encoded = json.dumps(report)
        self.assertNotIn("PRIVATE_EXCERPT", encoded)
        self.assertNotIn("raw prose leak", encoded)
        self.assertIn("quality advisory scored", p.render_html(report))

    def test_overview_distinguishes_efficiency_from_money_and_preserves_v5_fit(self):
        d = decision(decision_policy_version="pilot-selection-v5", selection_basis={
            "preference":"efficiency_hints", "method":"dated-efficiency-hints",
            "tie_breakers":["recent-comparable-failure", "efficiency-rank", "assessed-fit", "PRIVATE"], "private":"DROP"},
            candidate_assessments=[{"configuration_id":"small", "status":"suitable", "evidence":{},
                                   "applicable_fits":["reasoning"], "assessed_fit":.88,
                                   "fit_probabilities":{"reasoning":.88,"code_interaction":.91,"context_synthesis":.99}}])
        d["candidates"][0]["efficiency_hint"] = {"rank":1,"basis":"provider-price-tier","checked_on":"2026-09-21", "status":"current", "source_url":"SECRET"}
        report = p.build_report([d], [outcome(costs={})])
        item = report["overview"][0]
        self.assertEqual(item["selection_basis"]["preference"], "efficiency_hints")
        self.assertEqual(item["efficiency_hint"]["rank"], 1)
        self.assertIsNone(item["cost"]["usd"])
        self.assertEqual(report["decisions"][0]["candidate_assessments"][0]["assessed_fit"], .88)
        self.assertNotIn("qualified", json.dumps(report["decisions"][0]))
        self.assertNotIn("SECRET", json.dumps(report))
        self.assertNotIn("PRIVATE", json.dumps(report))
        page = p.render_html(report)
        self.assertIn("not measured cost", page)
        self.assertIn("not a dollar estimate", page)
        self.assertLess(page.index('id="overview"'), page.index('<details class="audit">'))
        self.assertNotIn('<details class="audit" open', page)

    def test_overview_preserves_pending_and_security_states(self):
        request = {"schema":"ultra-pilot-request-v1", "id":"req", "task_id":"safe-task", "decision_id":"d1",
                   "state":"in-progress", "attempts":[
                       {"id":"a1", "configuration_id":"small", "kind":"initial", "state":"running"},
                       {"id":"a2", "configuration_id":"frontier", "kind":"comparison", "state":"accepted", "outcome_id":"o2"}]}
        report = p.build_report([decision()], [outcome(id="o2", configuration_id="frontier", security={"mode":"off"})], [request])
        item = report["overview"][0]
        self.assertEqual(item["first_attempt"], "running")
        self.assertEqual(item["final_result"], "in-progress")
        self.assertIsNone(item["cost"]["usd"])
        self.assertFalse(item["worker_time_complete"])
        self.assertEqual([a["security"] for a in item["attempts"]], ["unavailable", "off"])
        for status, expected in (("pass", "completed"), ("fail", "completed"), ("indeterminate", "completed"), ("unavailable", "unavailable")):
            with self.subTest(status=status):
                report = p.build_report([decision()], [outcome(security={"mode":"advisory", "status":status})])
                self.assertEqual(report["overview"][0]["attempts"][0]["security"], expected)
                self.assertTrue(report["outcomes"][0]["accepted"])

    def test_overview_replan_includes_all_router_costs_without_duplicate_tasks(self):
        request = {"schema":"ultra-pilot-request-v1", "id":"req", "task_id":"safe-task", "decision_id":"d2",
                   "decision_history":["d1", "d2"], "state":"accepted", "attempts":[
                       {"id":"a1", "configuration_id":"small", "kind":"initial", "state":"rejected", "outcome_id":"o1"},
                       {"id":"a2", "configuration_id":"small", "kind":"fallback", "state":"accepted", "outcome_id":"o2"}]}
        report = p.build_report([decision(), decision(id="d2")],
                                [outcome(accepted=False, attempt_kind="initial"),
                                 outcome(id="o2",decision_id="d2", attempt_kind="fallback")], [request])
        self.assertEqual(len(report["overview"]), 1)
        row = report["overview"][0]
        self.assertEqual(row["first_attempt"], "rejected")
        self.assertEqual(row["final_result"], "accepted")
        self.assertEqual(row["router_time_ms"], 8)
        self.assertAlmostEqual(row["cost"]["usd"], .106)
        self.assertEqual(row["recovery_attempts"], 1)
        self.assertAlmostEqual(report["summary"]["whole_workload_cost"]["usd"], .106)
        self.assertEqual(row["known_cost_components_usd"], {"measured":.1, "estimated":.006})


if __name__ == '__main__': unittest.main()
