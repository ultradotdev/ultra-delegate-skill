import copy
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'.agents/skills/ultra-delegation/scripts'))
import pilot
import pilot_core as core
import pilot_workflow as workflow


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.policy = pilot.init_project(self.root, {'mode': 'active', 'share_summaries': True, 'baseline_id': 'candidate-2'})
        self.packet = pilot.fixture(); self.packet['synthetic'] = False
        self.decision = pilot.route_packet(self.packet, self.policy, live=True, call=pilot.synthetic_response, key='fixture')
        pilot.write_new(self.root/'decisions'/(self.decision['id']+'.json'), self.decision)
        self.counter = 0

    def start(self, mode='on'):
        return workflow.start(self.root, self.decision, self.packet, self.policy, mode)

    def event(self, r, kind, attempt, **extra):
        self.counter += 1
        return workflow.event(self.root, r['id'], {'id': 'event-'+str(self.counter), 'type': kind, 'attempt_id': attempt, **extra}, packet=self.packet)

    def complete(self, r, index=0):
        a = r['attempts'][index]
        r = self.event(r, 'launching', a['id'])
        r = self.event(r, 'dispatched', a['id'], run_id='native-'+a['id'], configuration_id=a['configuration_id'], checkout_hash='a'*64, base_revision='base')
        return self.event(r, 'completed', a['id'], artifact_hash='b'*64)

    def review(self, r, index, accepted, repair=False, defects=()):
        a = r['attempts'][index]
        raw = pilot.outcome_fixture(self.decision, a['configuration_id'], accepted)
        raw.update(artifact_hash=a['artifact_hash'], request_id=r['id'], attempt_id=a['id'], attempt_kind=a['kind'],
                   worker_id=a['run_id'], reviewer_id='independent-frontier', reviewer_kind='frontier', critical_defects=list(defects))
        o = pilot.observe(self.root, raw)
        return self.event(r, 'reviewed', a['id'], outcome_id=o['id'], repairable=repair, **({'findings_hash':'c'*64} if repair else {}))

    def test_primary_fails_comparison_passes_request_succeeds(self):
        r = self.start(); self.assertEqual(len(r['attempts']), 2)
        r = self.review(self.complete(r), 0, False)
        self.assertEqual(len(r['attempts']), 2)  # no extra spend while comparison pending
        r = self.review(self.complete(r, 1), 1, True)
        summary = workflow.report(r)
        self.assertFalse(summary['first_attempt_success'])
        self.assertTrue(summary['bakeoff_success']); self.assertTrue(summary['request_success'])
        self.assertEqual(workflow.next_actions(r), [])
        paths = pilot.report(self.root)
        self.assertIn('What happened', Path(paths['html']).read_text())

    def test_both_fail_then_fallback_and_one_repair(self):
        r = self.start()
        r = self.review(self.complete(r), 0, False)
        r = self.review(self.complete(r, 1), 1, False)
        self.assertEqual(r['attempts'][2]['kind'], 'fallback')
        r = self.review(self.complete(r, 2), 2, False, repair=True)
        self.assertEqual(r['attempts'][3]['kind'], 'repair')
        self.assertEqual(r['attempts'][3]['configuration_id'], r['attempts'][2]['configuration_id'])
        r = self.review(self.complete(r, 3), 3, False, repair=True)
        self.assertEqual(r['attempts'][4]['kind'], 'fallback')
        r = self.review(self.complete(r, 4), 4, True)
        self.assertTrue(workflow.report(r)['request_success'])
        self.assertEqual(workflow.report(r)['recovery_attempts'], 3)

    def test_targeted_repair_success_does_not_erase_first_attempt_failure(self):
        r = self.start('off'); r = self.review(self.complete(r), 0, False, repair=True)
        r = self.review(self.complete(r, 1), 1, True)
        summary = workflow.report(r)
        self.assertFalse(summary['first_attempt_success']); self.assertFalse(summary['bakeoff_success'])
        self.assertTrue(summary['request_success'])
        records = pilot.load_records(self.root, 'outcomes')
        next_packet = copy.deepcopy(self.packet); next_packet.update(group_id='future', task_id='future')
        row = next(r for r in core.prepare(next_packet, self.policy, records)['rows'] if r['configuration_id'] == self.decision['selected_configuration_id'])
        self.assertEqual(row['evidence']['failed_groups'], 1)
        self.assertEqual(row['evidence']['passed_groups'], 0)

    def test_critical_defect_blocks_otherwise_good_output(self):
        r = self.start('off'); r = self.review(self.complete(r), 0, True, defects=['authorization-bypass'])
        self.assertEqual(r['attempts'][0]['state'], 'rejected'); self.assertNotEqual(r['state'], 'accepted')

    def test_resume_never_blindly_launches_twice(self):
        r = self.start('off')
        e = {'id':'launch', 'type':'launching', 'attempt_id':'attempt-1'}
        r = workflow.event(self.root, r['id'], e, packet=self.packet)
        self.assertEqual(workflow.next_actions(workflow.get(self.root, r['id'])), [])
        self.assertEqual(r, workflow.event(self.root, r['id'], e, packet=self.packet))
        with self.assertRaises(core.PilotError): workflow.event(self.root, r['id'], {**e, 'type':'cancel', 'reason_code':'cancel'})
        r = self.event(r, 'launch-not-started', 'attempt-1', reason_code='host-confirmed-absent')
        self.assertEqual(len(workflow.next_actions(r)), 1)

    def test_launch_reconciliation_is_bounded(self):
        r = self.start('off')
        r = self.event(r, 'launching', 'attempt-1')
        r = self.event(r, 'launch-not-started', 'attempt-1', reason_code='host-confirmed-absent')
        r = self.event(r, 'launching', 'attempt-1')
        with self.assertRaisesRegex(core.PilotError, 'launch-reconciliation-exhausted'):
            self.event(r, 'launch-not-started', 'attempt-1', reason_code='host-confirmed-absent')

    def test_stale_lock_file_does_not_block_a_resumed_event(self):
        r = self.start('off')
        workflow._path(self.root, r['id']).with_suffix('.lock').write_text('stale')
        r = self.event(r, 'launching', 'attempt-1')
        self.assertEqual(r['attempts'][0]['state'], 'launching')

    def test_elapsed_limit_persists_coordinator_handoff(self):
        policy = pilot.init_project(self.root/'elapsed', {'mode': 'active', 'share_summaries': True,
                                                           'baseline_id': 'candidate-2',
                                                           'workflow': {'max_elapsed_seconds': 1}})
        decision = pilot.route_packet(self.packet, policy, live=True, call=pilot.synthetic_response, key='fixture')
        pilot.write_new(self.root/'elapsed'/'decisions'/(decision['id']+'.json'), decision)
        r = workflow.start(self.root/'elapsed', decision, self.packet, policy, 'off')
        r['created_at'] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=2)).isoformat()
        workflow._write(workflow._path(self.root/'elapsed', r['id']), r)
        resumed = workflow.get(self.root/'elapsed', r['id'])
        self.assertEqual((resumed['state'], resumed['reason_code']), ('coordinator-required', 'elapsed-limit'))
        self.assertEqual(workflow.get(self.root/'elapsed', r['id'])['state'], 'coordinator-required')

    def test_elapsed_request_records_owned_completion_and_review_without_recovery(self):
        r = self.start('off')
        r = self.event(r, 'launching', 'attempt-1')
        r = self.event(r, 'dispatched', 'attempt-1', run_id='native-expired',
                       configuration_id=r['attempts'][0]['configuration_id'], checkout_hash='f'*64, base_revision='base')
        r['limits']['max_elapsed_seconds'] = 1
        r['created_at'] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).isoformat()
        workflow._write(workflow._path(self.root, r['id']), r)
        r = self.event(r, 'completed', 'attempt-1', artifact_hash='e'*64)
        self.assertEqual((r['state'], r['reason_code'], r['attempts'][0]['state']),
                         ('coordinator-required', 'elapsed-limit', 'completed'))
        self.assertEqual(workflow.next_actions(r), [])
        raw = pilot.outcome_fixture(self.decision, r['attempts'][0]['configuration_id'], True)
        raw.update(artifact_hash='e'*64, request_id=r['id'], attempt_id='attempt-1', attempt_kind='initial',
                   worker_id='native-expired', reviewer_id='independent-frontier', reviewer_kind='frontier')
        outcome = pilot.observe(self.root, raw)
        r = self.event(r, 'reviewed', 'attempt-1', outcome_id=outcome['id'])
        self.assertEqual((r['state'], r['accepted_attempt_id'], len(r['attempts'])), ('accepted', 'attempt-1', 1))

    def test_elapsed_request_can_cancel_running_attempt_without_recovery(self):
        r = self.start('off')
        r = self.event(r, 'launching', 'attempt-1')
        r = self.event(r, 'dispatched', 'attempt-1', run_id='native-cancel',
                       configuration_id=r['attempts'][0]['configuration_id'], checkout_hash='f'*64, base_revision='base')
        r['limits']['max_elapsed_seconds'] = 1
        r['created_at'] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).isoformat()
        workflow._write(workflow._path(self.root, r['id']), r)
        r = self.event(r, 'cancel', 'attempt-1', reason_code='native-run-canceled')
        self.assertEqual((r['state'], r['reason_code'], r['attempts'][0]['state'], len(r['attempts'])),
                         ('coordinator-required', 'elapsed-limit', 'canceled', 1))
        self.assertEqual(workflow.next_actions(r), [])

    def test_start_is_idempotent_after_completion_and_concurrent(self):
        r = self.start('off')
        r = self.review(self.complete(r), 0, True)
        stale = copy.deepcopy(self.packet)
        stale['context']['observed_at'] = '2020-01-01T00:00:00+00:00'
        self.assertEqual(workflow.start(self.root, self.decision, stale, self.policy, 'off')['id'], r['id'])
        root = self.root/'concurrent'; policy = pilot.init_project(root, {'mode': 'active', 'share_summaries': True,
                                                                            'baseline_id': 'candidate-2'})
        decision = pilot.route_packet(self.packet, policy, live=True, call=pilot.synthetic_response, key='fixture')
        pilot.write_new(root/'decisions'/(decision['id']+'.json'), decision)
        with ThreadPoolExecutor(max_workers=2) as pool:
            requests = list(pool.map(lambda _: workflow.start(root, decision, self.packet, policy, 'off'), range(2)))
        self.assertEqual({request['id'] for request in requests}, {requests[0]['id']})
        self.assertEqual(len(list((root/'workflows').glob('req_*.json'))), 1)

    def test_equal_quality_prefers_lower_complete_cost(self):
        r = self.start('on')
        r = self.complete(r, 0); r = self.complete(r, 1)
        for index, worker_cost in ((0, 2.0), (1, 1.0)):
            a = r['attempts'][index]
            raw = pilot.outcome_fixture(self.decision, a['configuration_id'], True)
            raw.update(artifact_hash=a['artifact_hash'], request_id=r['id'], attempt_id=a['id'], attempt_kind=a['kind'],
                       worker_id=a['run_id'], reviewer_id='independent-frontier', reviewer_kind='frontier')
            raw['costs'] = {key: {'usd': worker_cost if key == 'worker' else 0.0, 'kind': 'measured'}
                            for key in core.COST_COMPONENTS}
            outcome = pilot.observe(self.root, raw)
            r = self.event(r, 'reviewed', a['id'], outcome_id=outcome['id'])
        self.assertEqual(r['accepted_attempt_id'], 'attempt-2')

    def test_replan_preserves_request_contract_attempts_and_limits(self):
        r = self.start('off')
        r['pool'] = [r['attempts'][0]['configuration_id']]
        r['attempts'][0].update(state='failed', reason_code='material-validation-failure')
        r.update(state='coordinator-required', reason_code='viable-alternatives-exhausted')
        workflow._write(workflow._path(self.root, r['id']), r)
        fresh_packet = copy.deepcopy(self.packet)
        discovered = copy.deepcopy(fresh_packet['candidates'][1])
        discovered.update(id='candidate-new', model='new-model', model_revision='new-revision', effort='ultra')
        fresh_packet['candidates'].append(discovered)
        fresh = pilot.route_packet(fresh_packet, self.policy, live=True, call=pilot.synthetic_response, key='fixture')
        pilot.write_new(self.root/'decisions'/(fresh['id']+'.json'), fresh)
        replanned = workflow.replan(self.root, r['id'], fresh, fresh_packet, self.policy)
        self.assertEqual(replanned['decision_history'], [self.decision['id'], fresh['id']])
        self.assertEqual(replanned['acceptance_gates'], self.decision['acceptance_gates'])
        self.assertEqual(replanned['attempts'][0]['state'], 'failed')
        self.assertEqual(replanned['attempts'][0]['decision_id'], self.decision['id'])
        self.assertEqual(replanned['attempts'][-1]['kind'], 'fallback')
        self.assertEqual(replanned['attempts'][-1]['decision_id'], fresh['id'])
        self.assertEqual(replanned['state'], 'in-progress')
        self.assertEqual(workflow.replan(self.root, r['id'], fresh, fresh_packet, self.policy), replanned)
        a = replanned['attempts'][-1]
        replanned = workflow.event(self.root, replanned['id'],
            {'id': 'replan-launch', 'type': 'launching', 'attempt_id': a['id']}, packet=fresh_packet)
        replanned = workflow.event(self.root, replanned['id'],
            {'id': 'replan-dispatch', 'type': 'dispatched', 'attempt_id': a['id'], 'run_id': 'native-replan',
             'configuration_id': a['configuration_id'], 'checkout_hash': 'd'*64, 'base_revision': 'base'}, packet=fresh_packet)
        replanned = workflow.event(self.root, replanned['id'],
            {'id': 'replan-complete', 'type': 'completed', 'attempt_id': a['id'], 'artifact_hash': 'e'*64}, packet=fresh_packet)
        a = replanned['attempts'][-1]
        raw = pilot.outcome_fixture(fresh, a['configuration_id'], True)
        raw.update(artifact_hash=a['artifact_hash'], request_id=replanned['id'], attempt_id=a['id'], attempt_kind=a['kind'],
                   worker_id=a['run_id'], reviewer_id='independent-frontier', reviewer_kind='frontier')
        outcome = pilot.observe(self.root, raw)
        replanned = workflow.event(self.root, replanned['id'],
            {'id': 'replan-review', 'type': 'reviewed', 'attempt_id': a['id'], 'outcome_id': outcome['id']}, packet=fresh_packet)
        self.assertEqual((replanned['state'], replanned['accepted_attempt_id']), ('accepted', a['id']))

    def test_recheck_catches_permissions_changes_and_foreign_evidence(self):
        r = self.start()
        changed = copy.deepcopy(self.packet); changed['task']['required_tools'].append('deploy')
        with self.assertRaisesRegex(core.PilotError, 'execution-inputs-changed'):
            workflow.recheck(self.root, r['id'], 'attempt-1', changed)
        self.packet['context']['observed_at'] = '2020-01-01T00:00:00+00:00'
        with self.assertRaisesRegex(core.PilotError, 'candidate-no-longer-eligible'):
            workflow.recheck(self.root, r['id'], 'attempt-1', self.packet)

    def test_cancel_is_not_failed_and_success_does_not_wait(self):
        r = self.start(); r = self.review(self.complete(r), 0, True)
        r = self.event(r, 'cancel', 'attempt-2', reason_code='accepted-result-available')
        self.assertEqual(r['state'], 'accepted'); self.assertEqual(r['attempts'][1]['state'], 'canceled')

    def test_future_same_request_outcome_blocks_comparison_until_clock_is_valid(self):
        r = self.start()
        r = self.review(self.complete(r), 0, False)
        outcome = pilot.load_records(self.root, 'outcomes')[0]
        path = self.root/'outcomes'/(outcome['id']+'.json')
        original = path.read_text()
        outcome['created_at'] = '2999-01-01T00:00:00+00:00'
        path.write_text(json.dumps(outcome))
        with self.assertRaisesRegex(core.PilotError, 'decision-evidence-changed'):
            workflow.recheck(self.root, r['id'], 'attempt-2', self.packet)
        self.assertEqual(workflow.get(self.root, r['id'])['attempts'][1]['state'], 'planned')
        path.write_text(original)
        self.assertEqual(workflow.recheck(self.root, r['id'], 'attempt-2', self.packet)['recheck'], 'passed')

    def test_cancel_does_not_create_a_fallback(self):
        r = self.start('off')
        r = self.event(r, 'cancel', 'attempt-1', reason_code='user-canceled')
        self.assertEqual((r['state'], len(r['attempts'])), ('canceled', 1))
        self.assertEqual(workflow.next_actions(r), [])

    def test_explicit_choice_has_no_unapproved_model_fallback(self):
        self.packet['user_choice_id'] = 'candidate-0'
        self.decision = pilot.route_packet(self.packet, self.policy)
        pilot.write_new(self.root/'decisions'/(self.decision['id']+'.json'), self.decision)
        r = self.start(); self.assertEqual(len(r['pool']), 1)
        r = self.review(self.complete(r), 0, False)
        self.assertEqual(r['state'], 'coordinator-required')


if __name__ == '__main__': unittest.main()
