"""Independently reviewed native-trial regressions for public pilot contracts."""
import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.agents/skills/ultra-delegation/scripts'))
import pilot
import pilot_core as core
import pilot_workflow as workflow
import pilot_judge as judge
import pilot_learning as learning

class NativeLaunchEventRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.policy = pilot.init_project(
            self.root,
            {"mode": "active", "share_summaries": True, "baseline_id": "candidate-2"},
        )
        self.packet = pilot.fixture()
        self.packet["synthetic"] = False
        self.decision = pilot.route_packet(
            self.packet,
            self.policy,
            live=True,
            call=pilot.synthetic_response,
            key="local-fixture",
        )
        pilot.write_new(
            self.root / "decisions" / f"{self.decision['id']}.json",
            self.decision,
        )

    def _request_at_launch_boundary(self):
        request = workflow.start(
            self.root, self.decision, self.packet, self.policy, bakeoff="off"
        )
        launching = {
            "id": "launching-once",
            "type": "launching",
            "attempt_id": "attempt-1",
        }
        return workflow.event(
            self.root, request["id"], launching, packet=self.packet
        )

    def test_replayed_dispatched_event_is_idempotent(self):
        request = self._request_at_launch_boundary()
        dispatched = {
            "id": "native-dispatch-once",
            "type": "dispatched",
            "attempt_id": "attempt-1",
            "run_id": "native-run-1",
            "configuration_id": request["attempts"][0]["configuration_id"],
            "checkout_hash": "a" * 64,
            "base_revision": "base-revision",
        }

        first = workflow.event(self.root, request["id"], dispatched, packet=self.packet)
        replay = workflow.event(self.root, request["id"], dispatched, packet=self.packet)

        self.assertEqual(replay, first)
        self.assertEqual(len(replay["events"]), 2)
        self.assertEqual(replay["attempts"][0]["state"], "running")
        self.assertEqual(replay["attempts"][0]["run_id"], "native-run-1")

    def test_observed_configuration_must_match_planned_configuration(self):
        request = self._request_at_launch_boundary()
        expected = request["attempts"][0]["configuration_id"]
        unsupported = "cfg_" + "0" * 24
        self.assertNotEqual(unsupported, expected)

        with self.assertRaisesRegex(core.PilotError, "observed-configuration-mismatch"):
            workflow.event(
                self.root,
                request["id"],
                {
                    "id": "wrong-native-configuration",
                    "type": "dispatched",
                    "attempt_id": "attempt-1",
                    "run_id": "native-run-wrong",
                    "configuration_id": unsupported,
                    "checkout_hash": "b" * 64,
                    "base_revision": "base-revision",
                },
                packet=self.packet,
            )

        persisted = workflow.get(self.root, request["id"])
        self.assertEqual(persisted["attempts"][0]["state"], "launching")
        self.assertNotIn("run_id", persisted["attempts"][0])

class EmptyHistoryAndToolEligibilityRegressionTests(unittest.TestCase):
    def setUp(self):
        self.packet = pilot.fixture()
        self.policy = {
            "mode": "active",
            "share_summaries": True,
            "baseline_id": "candidate-2",
        }

    def test_empty_history_can_still_route_a_semantically_suitable_candidate(self):
        decision = pilot.route_packet(
            self.packet,
            self.policy,
            outcomes=(),
            live=True,
            call=pilot.synthetic_response,
            key="local-fixture",
        )

        self.assertEqual(decision["status"], "ok")
        self.assertEqual(decision["action"], "route")
        self.assertIsNotNone(decision["selected_configuration_id"])
        selected = next(
            assessment
            for assessment in decision["candidate_assessments"]
            if assessment["configuration_id"] == decision["selected_configuration_id"]
        )
        self.assertEqual(selected["evidence"]["groups"], 0)
        self.assertEqual(selected["reason_codes"], ["semantic-match-without-history"])

    def test_missing_required_tool_prevents_dispatch_authorization(self):
        packet = copy.deepcopy(self.packet)
        packet["task"]["required_tools"].append("forbidden-deployment-tool")

        decision = pilot.route_packet(packet, self.policy, outcomes=())

        self.assertEqual(decision["action"], "coordinator")
        self.assertEqual(decision["reason_codes"], ["no-eligible-candidates"])
        self.assertIsNone(decision["selected_configuration_id"])
        self.assertFalse(decision["dispatch_authorized"])
        self.assertTrue(decision["candidates"])
        self.assertTrue(
            all("missing-tools" in candidate["reasons"] for candidate in decision["candidates"])
        )

class ArtifactJudgePermissionAndEvidenceRegressionTests(unittest.TestCase):
    def setUp(self):
        self.packet = {
            "requirements": ["Preserve documented behavior."],
            "excerpts": ["The local regression suite completed."],
            "validation_summary": "A deterministic local test was observed.",
        }

    def test_summary_routing_permission_does_not_grant_artifact_sharing(self):
        external_call = Mock(side_effect=AssertionError("judge must not be called"))
        policy = core.policy({"share_summaries": True, "share_artifacts": False})

        result = judge.assess(
            self.packet,
            policy,
            live=True,
            call=external_call,
            key="unused-local-key",
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason_codes"], ["artifact-sharing-disabled"])
        external_call.assert_not_called()

    def test_insufficient_evidence_never_produces_acceptance_like_scores(self):
        def uncertain_response(payload, key):
            response, metadata = pilot.synthetic_response(payload, key)
            response["answers"]["enough"]["noul"] = 0.89
            return response, metadata

        result = judge.assess(
            self.packet,
            core.policy({"share_artifacts": True}),
            live=True,
            call=uncertain_response,
            key="local-fixture",
        )

        self.assertEqual(result["status"], "insufficient-evidence")
        self.assertEqual(
            result["reason_codes"], ["insufficient-selected-evidence"]
        )
        self.assertNotIn("scores", result)
        self.assertNotIn("mean_score", result)
        self.assertNotIn("accepted", result)

class StartIdempotencyRegression(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.policy = pilot.init_project(
            self.root, {'mode': 'active', 'share_summaries': True, 'baseline_id': 'candidate-2'})
        self.packet = pilot.fixture()
        self.packet['synthetic'] = False
        self.decision = pilot.route_packet(
            self.packet, self.policy, live=True, call=pilot.synthetic_response, key='fixture')
        pilot.write_new(self.root / 'decisions' / (self.decision['id'] + '.json'), self.decision)

    def test_existing_request_is_returned_after_evidence_changes(self):
        original = workflow.start(self.root, self.decision, self.packet, self.policy, 'off')
        raw = pilot.outcome_fixture(self.decision, self.decision['selected_configuration_id'])
        raw.update(reviewer_id='independent-reviewer', reviewer_kind='frontier',
                   worker_id='native-worker')
        pilot.observe(self.root, raw)

        repeated = workflow.start(self.root, self.decision, self.packet, self.policy, 'off')

        self.assertEqual(repeated, original)
        self.assertEqual(len(list((self.root / 'workflows').glob('req_*.json'))), 1)

    def test_new_request_still_validates_packet_and_stored_decision(self):
        stale = copy.deepcopy(self.packet)
        stale['context']['observed_at'] = '2020-01-01T00:00:00+00:00'
        with self.assertRaises(core.PilotError):
            workflow.start(self.root, self.decision, stale, self.policy, 'on')

        changed = copy.deepcopy(self.decision)
        changed['reason_codes'] = ['tampered']
        with self.assertRaisesRegex(core.PilotError, 'decision-changed'):
            workflow.start(self.root, changed, self.packet, self.policy, 'on')

class AcceptedCandidateCostRegression(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.policy = pilot.init_project(
            self.root, {'mode': 'active', 'share_summaries': True, 'baseline_id': 'candidate-2'})
        self.packet = pilot.fixture()
        self.packet['synthetic'] = False
        self.decision = pilot.route_packet(
            self.packet, self.policy, live=True, call=pilot.synthetic_response, key='fixture')
        pilot.write_new(self.root / 'decisions' / (self.decision['id'] + '.json'), self.decision)
        self.request = workflow.start(self.root, self.decision, self.packet, self.policy, 'on')
        for index in range(2):
            attempt = self.request['attempts'][index]
            self.request = workflow.event(
                self.root, self.request['id'],
                {'id': f'launch-{index}', 'type': 'launching', 'attempt_id': attempt['id']},
                packet=self.packet)
            self.request = workflow.event(
                self.root, self.request['id'],
                {'id': f'dispatch-{index}', 'type': 'dispatched', 'attempt_id': attempt['id'],
                 'run_id': f'native-{index}', 'configuration_id': attempt['configuration_id'],
                 'checkout_hash': str(index + 1) * 64, 'base_revision': 'base'}, packet=self.packet)
            self.request = workflow.event(
                self.root, self.request['id'],
                {'id': f'complete-{index}', 'type': 'completed', 'attempt_id': attempt['id'],
                 'artifact_hash': chr(ord('a') + index) * 64}, packet=self.packet)

    def review(self, index, *, score, costs):
        attempt = self.request['attempts'][index]
        raw = pilot.outcome_fixture(self.decision, attempt['configuration_id'], True)
        raw.update(
            artifact_hash=attempt['artifact_hash'], request_id=self.request['id'],
            attempt_id=attempt['id'], attempt_kind=attempt['kind'], worker_id=attempt['run_id'],
            reviewer_id=f'reviewer-{index}', reviewer_kind='frontier',
            scores={key: score for key in core.DIMENSIONS}, costs=costs)
        outcome = pilot.observe(self.root, raw)
        self.request = workflow.event(
            self.root, self.request['id'],
            {'id': f'review-{index}', 'type': 'reviewed', 'attempt_id': attempt['id'],
             'outcome_id': outcome['id']}, packet=self.packet)

    @staticmethod
    def complete_cost(total):
        return {key: {'usd': total if key == 'worker' else 0.0, 'kind': 'measured'}
                for key in core.COST_COMPONENTS}

    def test_unknown_cost_is_not_treated_as_zero(self):
        self.review(0, score=90, costs=self.complete_cost(4.0))
        unknown = {key: {'usd': None, 'kind': 'unknown'} for key in core.COST_COMPONENTS}
        self.review(1, score=90, costs=unknown)
        self.assertEqual(self.request['accepted_attempt_id'], 'attempt-1')

    def test_quality_precedes_complete_cost(self):
        self.review(0, score=95, costs=self.complete_cost(9.0))
        self.review(1, score=90, costs=self.complete_cost(1.0))
        self.assertEqual(self.request['accepted_attempt_id'], 'attempt-1')

class ConcurrentStartRegression(unittest.TestCase):
    def test_simultaneous_starts_converge_on_one_atomic_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = pilot.init_project(
                root, {'mode': 'active', 'share_summaries': True, 'baseline_id': 'candidate-2'})
            packet = pilot.fixture()
            packet['synthetic'] = False
            decision = pilot.route_packet(
                packet, policy, live=True, call=pilot.synthetic_response, key='fixture')
            pilot.write_new(root / 'decisions' / (decision['id'] + '.json'), decision)
            ready = threading.Barrier(2)

            def start_together():
                ready.wait(timeout=5)
                return workflow.start(root, decision, packet, policy, 'off')

            with ThreadPoolExecutor(max_workers=2) as pool:
                requests = list(pool.map(lambda _: start_together(), range(2)))

            self.assertEqual(requests[0], requests[1])
            self.assertEqual(len(requests[0]['attempts']), 1)
            self.assertEqual(len(list((root / 'workflows').glob('req_*.json'))), 1)
            stored = workflow.get(root, requests[0]['id'])
            self.assertEqual(stored, requests[0])

class CriticalAcceptanceRegressions(unittest.TestCase):
    def setUp(self):
        self.configuration_id = "cfg_critical-regression"
        self.decision = {
            "id": "decision-critical-regression",
            "task_id": "task-critical-regression",
            "group_id": "group-critical-regression",
            "scope_id": "scope",
            "operation": "repair-parser",
            "risk": "low",
            "work_kind": "coding",
            "complexity": "routine",
            "synthetic": False,
            "decision_policy_version": core.DECISION_POLICY_VERSION,
            "acceptance_gates": ["tests-pass"],
            "candidates": [{"configuration_id": self.configuration_id, "eligible": True}],
        }

    def raw_outcome(self, **changes):
        raw = {
            "decision_id": self.decision["id"],
            "configuration_id": self.configuration_id,
            "artifact_hash": "a" * 64,
            "worker_id": "native-worker",
            "reviewer_id": "independent-reviewer",
            "reviewer_kind": "human",
            "review_accepted": True,
            "gates": [{"id": "tests-pass", "mandatory": True, "passed": True}],
            "scores": {name: 100 for name in core.DIMENSIONS},
            "costs": {name: {"usd": 0.01, "kind": "measured"} for name in core.COST_COMPONENTS},
            "latency_ms": 1,
        }
        raw.update(changes)
        return raw

    def test_critical_defect_vetoes_high_scoring_output(self):
        outcome = core.assess_outcome(
            self.raw_outcome(critical_defects=["authorization-bypass"]),
            self.decision,
            core.policy(),
        )
        self.assertFalse(outcome["accepted"])
        self.assertEqual(outcome["critical_defects"], ["authorization-bypass"])

    def test_worker_cannot_be_its_own_reviewer(self):
        with self.assertRaisesRegex(core.PilotError, "worker-cannot-review-self"):
            core.assess_outcome(
                self.raw_outcome(reviewer_id="native-worker"),
                self.decision,
                core.policy(),
            )

class PortableLearningRegression(unittest.TestCase):
    def _source_with_observation(self, root, *, accepted=False):
        policy = pilot.init_project(root)
        packet = pilot.fixture()
        decision = pilot.route_packet(packet, policy)
        pilot.write_new(root / 'decisions' / (decision['id'] + '.json'), decision)
        raw = pilot.outcome_fixture(decision, decision['selected_configuration_id'], accepted=accepted)
        return pilot.observe(root, raw)

    def test_return_to_original_project_deduplicates_native_id_and_preserves_local_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            relay = root / 'relay'
            original = self._source_with_observation(source, accepted=False)
            before = pilot.read_json(source / 'outcomes' / (original['id'] + '.json'))

            pilot.init_project(relay)
            self.assertEqual(learning.import_bundle(relay, learning.export(source))['imported'], 1)
            returning = learning.export(relay)
            result = learning.import_bundle(source, returning)

            self.assertEqual(result, {'imported': 0, 'already_present': 1,
                                      'provenance': 'imported-unverified'})
            self.assertEqual(pilot.read_json(source / 'outcomes' / (original['id'] + '.json')), before)
            self.assertEqual(len(pilot.load_records(source, 'outcomes', include_retracted=True)), 1)

    def test_return_to_original_project_deduplicates_retracted_local_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            relay = root / 'relay'
            original = self._source_with_observation(source, accepted=False)
            bundle = learning.export(source)
            learning.retract(source, original['id'], 'incorrect-review')

            pilot.init_project(relay)
            self.assertEqual(learning.import_bundle(relay, bundle)['imported'], 1)
            result = learning.import_bundle(source, learning.export(relay))

            self.assertEqual(result['imported'], 0)
            self.assertEqual(result['already_present'], 1)
            self.assertEqual(len(pilot.load_records(source, 'outcomes')), 0)
            self.assertEqual(len(pilot.load_records(source, 'outcomes', include_retracted=True)), 1)
            self.assertEqual(learning.retractions(source)[0]['outcome_id'], original['id'])

    def test_failed_observation_survives_two_hops_without_duplicate_cost(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            first_hop = root / 'first-hop'
            second_hop = root / 'second-hop'
            policy = pilot.init_project(source)
            packet = pilot.fixture()
            decision = pilot.route_packet(packet, policy)
            pilot.write_new(source / 'decisions' / (decision['id'] + '.json'), decision)
            candidate = decision['selected_configuration_id']
            raw = pilot.outcome_fixture(decision, candidate, accepted=False)
            original = pilot.observe(source, raw)

            pilot.init_project(first_hop)
            self.assertEqual(learning.import_bundle(first_hop, learning.export(source))['imported'], 1)
            first_export = learning.export(first_hop)
            pilot.init_project(second_hop)
            self.assertEqual(learning.import_bundle(second_hop, first_export)['imported'], 1)
            second_export = learning.export(second_hop)
            self.assertEqual(learning.import_bundle(second_hop, second_export)['already_present'], 1)

            records = pilot.load_records(second_hop, 'outcomes')
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertFalse(record['accepted'])
            self.assertEqual(record['provenance'], 'imported-unverified')
            self.assertEqual(record['observation_origin'], original['id'])
            self.assertEqual(record['costs'], original['costs'])
            self.assertEqual(second_export['outcomes'][0]['observation_hash'],
                             first_export['outcomes'][0]['observation_hash'])

if __name__ == '__main__':
    unittest.main()
