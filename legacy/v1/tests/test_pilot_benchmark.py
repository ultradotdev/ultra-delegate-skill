import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/skills/ultra-delegation/scripts"))
import pilot
import pilot_benchmark as benchmark
import pilot_core as core


class BenchmarkTests(unittest.TestCase):
    def test_offline_never_calls_credentials_and_missing_workers_pending(self):
        with patch("pilot.transport.credential", side_effect=AssertionError("credential")):
            report = benchmark.run(benchmark.example())
        self.assertEqual(report["benchmark"]["independent_groups"], 12)
        self.assertEqual(report["benchmark"]["worker_results_pending"], 12)
        self.assertEqual(report["benchmark"]["qualification"], "not-a-certification")
        self.assertEqual(report["benchmark"]["status"], "synthetic-template")

    def test_current_choice_score_noul_and_svg_artifacts(self):
        manifest = benchmark.example(); manifest["policy"]["share_summaries"] = True
        routed = Mock(side_effect=pilot.route_packet)
        report = benchmark.run(manifest, simulate=True, route_callable=routed)
        self.assertEqual(routed.call_count, 12)
        self.assertTrue(all(decision["action"] == "route" for decision in report["decisions"]))
        self.assertEqual({answer["type"] for answer in report["decisions"][0]["signals"].values()}, {"noul", "choice", "score"})
        with tempfile.TemporaryDirectory() as root:
            paths = benchmark.write_report(Path(root) / "report", report)
            self.assertTrue(all(Path(path).exists() for path in paths.values()))
            svg = Path(paths["svg"]).read_text()
            self.assertIn("Pending", svg)
            self.assertIn("no reviewed selected-worker", svg)

    def test_cross_split_and_future_or_evaluation_leakage_rejected_before_call(self):
        manifest = benchmark.example()
        manifest["cases"][2]["group_id"] = manifest["cases"][0]["group_id"]
        manifest["cases"][2]["prepared_packet"]["group_id"] = manifest["cases"][0]["group_id"]
        with self.assertRaisesRegex(core.PilotError, "group-crosses-splits"):
            benchmark.run(manifest, live=True, route_callable=Mock())
        manifest = benchmark.example()
        manifest["cases"][0]["evidence"] = [{"group_id": manifest["cases"][1]["group_id"], "created_at": "2000-01-01T00:00:00+00:00"}]
        with self.assertRaisesRegex(core.PilotError, "evaluation-outcome-leakage"):
            benchmark.run(manifest)
        manifest = benchmark.example()
        manifest["cases"][0]["evidence"] = [{"group_id": "past-group", "created_at": "2999-01-01T00:00:00+00:00"}]
        with self.assertRaisesRegex(core.PilotError, "future-evidence"):
            benchmark.run(manifest)

    def test_live_refuses_synthetic_and_reference_provenance_is_required(self):
        manifest = benchmark.example(); manifest["policy"]["share_summaries"] = True
        route = Mock()
        with self.assertRaisesRegex(core.PilotError, "live-requires-prepared-real-packets"):
            benchmark.run(manifest, live=True, route_callable=route)
        route.assert_not_called()
        manifest = benchmark.example()
        manifest["cases"][0]["reference"] = {"action": "route", "reviewer": {"id": "r", "kind": "human", "independent": True, "provenance": "review-v1"},
                                                  "candidate_order_blinded": False, "recorded_at": "2026-01-01T00:00:00+00:00", "judge_action": "route"}
        with self.assertRaisesRegex(core.PilotError, "judge-needs-independent-reference"):
            benchmark.run(manifest)

    def test_real_observations_cannot_use_synthetic_review_or_history(self):
        manifest = benchmark.example()
        manifest["cases"][0]["prepared_packet"]["synthetic"] = False
        manifest["cases"][0]["evidence"] = [{"group_id": "old-group", "created_at": "2000-01-01T00:00:00+00:00", "synthetic": True}]
        with self.assertRaisesRegex(core.PilotError, "synthetic-evidence"):
            benchmark.run(manifest)
        manifest["cases"][0]["evidence"] = []
        manifest["cases"][0]["outcomes"] = [{"input_hash": core.digest(manifest["cases"][0]["prepared_packet"]),
                                                  "review": {"reviewer_kind": "synthetic", "reviewer_id": "reviewer"}}]
        with self.assertRaisesRegex(core.PilotError, "real-outcome-needs-independent-review"):
            benchmark.run(manifest)

    def test_input_freeze_and_partial_progress_preserve_prior_case(self):
        manifest = benchmark.example(); manifest["policy"]["share_summaries"] = True
        calls, progress = [], []
        def route(packet, policy, evidence, **kwargs):
            calls.append(packet["task_id"])
            if len(calls) == 2:
                raise RuntimeError("provider returned secret and prompt content")
            return pilot.route_packet(packet, policy, evidence, **kwargs)
        report = benchmark.run(manifest, simulate=True, route_callable=route,
                               case_progress=lambda _index, value: progress.append(value))
        self.assertEqual(len(progress), 12)
        self.assertEqual(progress[0]["benchmark"]["status"], "partial")
        self.assertEqual(progress[0]["summary"]["decisions"], 1)
        self.assertEqual(report["benchmark"]["cases"][1]["route_error"], "routing-failed")
        self.assertNotIn("secret", json.dumps(report))
        self.assertEqual(manifest["cases"][0]["prepared_packet"]["task_id"], "review-0")

    def test_failed_initial_attempt_remains_visible_after_repair(self):
        manifest = benchmark.example(); manifest["policy"]["share_summaries"] = True
        packet = manifest["cases"][0]["prepared_packet"]
        decision = pilot.route_packet(packet, manifest["policy"], [], live=True, call=pilot.synthetic_response, key="synthetic")
        configuration = decision["selected_configuration_id"]
        failed = pilot.outcome_fixture(decision, configuration, accepted=False)
        failed.update(request_id="req-0", attempt_id="attempt-initial", attempt_kind="initial")
        repaired = pilot.outcome_fixture(decision, configuration, accepted=True)
        repaired.update(request_id="req-0", attempt_id="attempt-repair", attempt_kind="repair")
        manifest["cases"][0]["outcomes"] = [{"input_hash": core.digest(packet), "review": failed}, {"input_hash": core.digest(packet), "review": repaired}]
        report = benchmark.run(manifest, simulate=True)
        row = report["benchmark"]["cases"][0]
        self.assertFalse(row["first_attempt_outcome"])
        self.assertTrue(row["final_request_outcome"])
        self.assertEqual(row["failed_attempts"], 1)
        self.assertEqual(report["benchmark"]["metrics"]["first_attempt_success"]["passed"], 0)
        self.assertEqual(report["benchmark"]["metrics"]["final_request_success"]["passed"], 1)

    def test_accepted_alternate_completes_request_without_masking_primary_failure(self):
        manifest = benchmark.example(); manifest["policy"]["share_summaries"] = True
        packet = manifest["cases"][0]["prepared_packet"]
        prepared = pilot.route_packet(packet, manifest["policy"], [], live=True, call=pilot.synthetic_response, key="synthetic")
        primary = prepared["selected_configuration_id"]
        alternate = next(core.configuration_id(candidate) for candidate in packet["candidates"]
                         if core.configuration_id(candidate) != primary)
        initial = pilot.outcome_fixture(prepared, primary, accepted=False)
        initial.update(request_id="req-0", attempt_id="attempt-initial", attempt_kind="initial")
        fallback = pilot.outcome_fixture(prepared, alternate, accepted=True)
        fallback.update(request_id="req-0", attempt_id="attempt-fallback", attempt_kind="fallback")
        manifest["cases"][0]["outcomes"] = [{"input_hash": core.digest(packet), "review": initial},
                                                {"input_hash": core.digest(packet), "review": fallback}]
        def route_with_alternate(current_packet, policy, evidence, **kwargs):
            decision = pilot.route_packet(current_packet, policy, evidence, **kwargs)
            decision["alternative_configuration_ids"] = [alternate]
            return decision
        report = benchmark.run(manifest, simulate=True, route_callable=route_with_alternate)
        row = report["benchmark"]["cases"][0]
        self.assertFalse(row["first_attempt_outcome"])
        self.assertTrue(row["final_request_outcome"])
        self.assertEqual(row["failed_attempts"], 1)
        self.assertEqual(row["observed_outcomes"], 2)
        self.assertEqual(report["summary"]["outcomes"], 2)

    def test_manifest_generated_fixture_has_twelve_templates_and_safe_perturbations(self):
        manifest = benchmark.example()
        self.assertEqual(len(manifest["cases"]), 12)
        self.assertEqual({case["family"] for case in manifest["cases"]}, {"review", "tests", "implementation"})
        self.assertTrue(all(case["prepared_packet"]["synthetic"] for case in manifest["cases"]))
        self.assertEqual({item["kind"] for item in manifest["perturbations"]}, {"ambiguity", "embedded-instruction", "candidate-order-swap"})


if __name__ == "__main__":
    unittest.main()
