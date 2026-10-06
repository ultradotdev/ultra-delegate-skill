import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/ultra-delegation/scripts'
sys.path.insert(0, str(SCRIPTS))
import capability_index
import pilot
import pilot_core as core
import pilot_fixtures as fixtures


class FixtureTests(unittest.TestCase):
    def test_frozen_matrix_and_materialization_keep_references_outside_worker(self):
        cases = fixtures.fixtures()['cases']
        self.assertEqual(len(cases), 12)
        for split in ('development', 'test'):
            subset = [c for c in cases if c['split'] == split]
            self.assertEqual(len(subset), 6)
            self.assertEqual({c['language'] for c in subset}, fixtures.LANGUAGES)
            self.assertEqual({c['family'] for c in subset}, fixtures.FAMILIES)
        with tempfile.TemporaryDirectory() as directory:
            result = fixtures.materialize('python-ranges', Path(directory) / 'fixture')
            worker = Path(result['worker'])
            self.assertEqual({p.name for p in worker.iterdir()}, {'task.py', 'TASK.md'})
            self.assertTrue((Path(result['evaluator']) / 'reference/check.py').is_file())
            with self.assertRaisesRegex(core.PilotError, 'fixture-directory-exists'):
                fixtures.materialize('python-ranges', Path(directory) / 'fixture')

    def score_input(self, case):
        return {'fixture_id': case['id'], 'artifact_hash': 'a'*64, 'worker_id': 'worker', 'reviewer_id': 'reviewer',
                'reviewer_kind': 'frontier', 'review_accepted': True, 'scope_passed': True, 'critical_defects': 0,
                'executions': [], 'findings': []}

    def test_review_precision_recall_missing_duplicate_and_unsupported(self):
        case = fixtures.fixture('python-transfer-review'); raw = self.score_input(case)
        raw['findings'] = [{'id': str(i), 'reference_id': f['id']} for i, f in enumerate(case['reference_findings'])]
        self.assertTrue(fixtures.score(raw)['accepted'])
        raw['findings'].append({'id': 'spurious', 'reference_id': None})
        result = fixtures.score(raw)
        self.assertFalse(result['accepted']); self.assertEqual(result['review_precision'], .75)
        raw['findings'][-1]['reference_id'] = raw['findings'][0]['reference_id']
        self.assertFalse(fixtures.score(raw)['accepted'])
        raw['findings'] = raw['findings'][:1]
        self.assertEqual(fixtures.score(raw)['false_negatives'], 2)
        raw['reviewer_id'] = raw['worker_id']
        with self.assertRaisesRegex(core.PilotError, 'independent-review-required'): fixtures.score(raw)

    def test_mutation_rejects_compile_failure_missing_results_and_failed_baseline(self):
        case = fixtures.fixture('python-clamp-tests'); raw = self.score_input(case)
        raw['executions'] = [{'id': 'baseline', 'compiled': True, 'exit_code': 0}] + [
            {'id': name, 'compiled': True, 'exit_code': 1} for name in case['mutants']]
        self.assertTrue(fixtures.score(raw)['accepted'])
        raw['executions'][1]['compiled'] = False
        result = fixtures.score(raw)
        self.assertFalse(result['accepted']); self.assertIsNone(result['mutation_detection'])
        raw['executions'][1]['compiled'] = True; raw['executions'][0]['exit_code'] = 1
        self.assertFalse(fixtures.score(raw)['accepted'])
        raw['executions'][0]['exit_code'] = 0; raw['critical_defects'] = 1
        self.assertFalse(fixtures.score(raw)['accepted'])

    def _run(self, case, files, directory):
        root = Path(directory)
        for name, contents in files.items(): (root / name).write_text(contents, encoding='utf-8')
        tests = case['family'] == 'tests'
        command = case['worker_test_command'] if tests else case['commands']
        env = dict(os.environ, GOPROXY='off', GOSUMDB='off', GOCACHE=str(root / '.gocache'))
        done = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=120, env=env)
        if case['language'] == 'rust':
            self.assertEqual(done.returncode, 0, done.stderr)
            done = subprocess.run([str(root / ('tests-bin' if tests else 'check-bin'))], cwd=root, capture_output=True, text=True, timeout=20)
        return done

    def test_executable_references_and_seeded_defects(self):
        available = {'python': shutil.which('python3'), 'typescript': shutil.which('node'), 'go': shutil.which('go'), 'rust': shutil.which('rustc')}
        if available['typescript']:
            major = int(subprocess.check_output(['node','--version'], text=True).lstrip('v').split('.')[0])
            if major < 23: available['typescript'] = None
        tested = set()
        for case in fixtures.fixtures()['cases']:
            if case['family'] == 'review' or not available[case['language']]: continue
            with self.subTest(case=case['id']), tempfile.TemporaryDirectory() as directory:
                tested.add(case['language'])
                files = {**case['files'], **case['reference_solution'], **case['checks']}
                done = self._run(case, files, directory)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                if case['family'] == 'implementation':
                    done = self._run(case, {**case['files'], **case['checks']}, directory)
                    self.assertNotEqual(done.returncode, 0, case['id'] + ' starter unexpectedly passed')
                else:
                    for name, changes in case['mutants'].items():
                        with self.subTest(mutant=name):
                            done = self._run(case, {**case['files'], **case['reference_solution'], **changes}, directory)
                            self.assertNotEqual(done.returncode, 0, name + ' survived reference tests')
        self.assertIn('python', tested)


class CampaignTests(unittest.TestCase):
    def campaign(self, ids=('python-ranges', 'typescript-latest')):
        base = pilot.fixture(); base['synthetic'] = False
        for c in base['candidates']: c['effort'] = 'medium'
        cfg = core.configuration_id(base['candidates'][0])
        cases = []
        for identifier in ids:
            case = fixtures.fixture(identifier); packet = copy.deepcopy(base)
            packet.update(task_id=identifier, group_id=identifier)
            packet['task'].update(summary=case['summary'], requirements=case['requirements'])
            cases.append({'fixture_id': identifier, 'prepared_packet': packet, 'evidence': []})
        manifest = {'policy': core.policy({'mode':'active','share_summaries':True}), 'reference_configuration_id':cfg, 'cases':cases}
        index = capability_index.load(SCRIPTS.parent / 'assets/capability-index.json')
        return fixtures.prepare_campaign(manifest, index)

    def route(self, campaign, identifier):
        for arm in fixtures.ARMS:
            inputs = fixtures.route_input(campaign, identifier, arm)
            decision = pilot.route_packet(inputs['prepared_packet'], inputs['policy'], inputs['evidence'], live=True, call=pilot.synthetic_response, key='synthetic')
            fixtures.record_decision(campaign, identifier, arm, decision)

    def record(self, campaign, identifier, cfg, attempt='one', accepted=True, cost=None):
        case = fixtures.fixture(identifier)
        raw = FixtureTests().score_input(case)
        raw['executions'] = [{'id':'contract','compiled':True,'exit_code':0 if accepted else 1}]
        obs = {'fixture_id':identifier,'configuration_id':cfg,'attempt_id':attempt,'attempt_kind':'initial','score':raw,
               'latency_ms':10,'costs':{k:{'usd':cost,'kind':'unknown' if cost is None else 'measured'} for k in core.COST_COMPONENTS}}
        fixtures.record_observation(campaign, obs)
        return obs

    def test_pair_changes_descriptions_only_and_blocks_heldout_before_freeze(self):
        campaign = self.campaign(); case = campaign['frozen']['cases'][0]
        original, treated = [copy.deepcopy(case['packets'][a]) for a in fixtures.ARMS]
        for a,b in zip(original['candidates'], treated['candidates']):
            self.assertNotEqual(a.pop('capability_description'), b.pop('capability_description'))
        self.assertEqual(original, treated)
        with self.assertRaisesRegex(core.PilotError,'freeze-threshold-before-heldout'):
            fixtures.route_input(campaign,'typescript-latest','with_epoch')
        campaign['frozen']['cases'][0]['evidence'].append({})
        with self.assertRaisesRegex(core.PilotError,'campaign-freeze-mismatch'): fixtures.campaign_report(campaign)

    def test_shared_runs_are_explicit_and_observations_idempotent(self):
        campaign=self.campaign(); self.route(campaign,'python-ranges')
        plan=fixtures.execution_plan(campaign,'python-ranges')
        self.assertGreaterEqual(len(plan['runs']),2)
        selected=next(r for r in plan['runs'] if 'with_epoch' in r['roles'])
        self.assertTrue(selected['shared_observation'])
        obs=self.record(campaign,'python-ranges',selected['configuration_id'])
        fixtures.record_observation(campaign,obs)
        self.assertEqual(len(campaign['observations']),1)
        changed=copy.deepcopy(obs);changed['latency_ms']=12
        with self.assertRaisesRegex(core.PilotError,'attempt-already-recorded'): fixtures.record_observation(campaign,changed)
        report=fixtures.campaign_report(campaign)
        self.assertIsNone(report['summary']['total_workload_usd'])
        self.assertEqual(report['summary']['actual_worker_attempts'],1)
        self.assertTrue(report['cases'][0]['shared_selected_observation'])

    def test_sweep_requires_observed_outcomes_and_freezes_before_heldout(self):
        campaign=self.campaign(); self.route(campaign,'python-ranges')
        rows=fixtures.threshold_sweep(campaign)['rows']
        self.assertEqual([r['threshold'] for r in rows],list(fixtures.THRESHOLDS))
        self.assertTrue(all(r['worker_outcomes_known']==0 for r in rows))
        with self.assertRaisesRegex(core.PilotError,'development-outcomes-incomplete'): fixtures.freeze_threshold(campaign,.85)
        selected=next(r for r in fixtures.execution_plan(campaign,'python-ranges')['runs'] if 'with_epoch' in r['roles'])
        self.record(campaign,'python-ranges',selected['configuration_id'])
        fixtures.freeze_threshold(campaign,.85)
        self.route(campaign,'typescript-latest')
        with self.assertRaisesRegex(core.PilotError,'threshold-already-frozen'): fixtures.freeze_threshold(campaign,.9)
        with tempfile.TemporaryDirectory() as directory:
            paths=fixtures.write_report(campaign,Path(directory)/'report')
            self.assertTrue(Path(paths['html']).is_file());self.assertTrue(Path(paths['json']).is_file())
            self.assertIn('Savings: not established',Path(paths['html']).read_text())

    def test_wrong_decision_binding_and_synthetic_decisions_rejected(self):
        campaign=self.campaign(); inputs=fixtures.route_input(campaign,'python-ranges','without_epoch')
        decision=pilot.route_packet(inputs['prepared_packet'],inputs['policy'],live=True,call=pilot.synthetic_response,key='synthetic')
        wrong=copy.deepcopy(decision);wrong['input_hash']='a'*64
        with self.assertRaisesRegex(core.PilotError,'decision-freeze-mismatch'):fixtures.record_decision(campaign,'python-ranges','without_epoch',wrong)
        decision['synthetic']=True
        with self.assertRaisesRegex(core.PilotError,'inference-observation-required'):fixtures.record_decision(campaign,'python-ranges','without_epoch',decision)

    def test_cost_totals_wait_for_all_planned_workers_and_pair_deltas_are_counterfactual(self):
        campaign=self.campaign(ids=('python-ranges',));self.route(campaign,'python-ranges')
        runs=fixtures.execution_plan(campaign,'python-ranges')['runs']
        self.record(campaign,'python-ranges',runs[0]['configuration_id'],attempt='first',cost=.1)
        report=fixtures.campaign_report(campaign)
        self.assertFalse(report['summary']['workload_complete'])
        self.assertIsNone(report['summary']['total_workload_usd'])
        self.assertIsNotNone(report['summary']['observed_workload_subtotal_usd'])
        for i,run in enumerate(runs[1:]):
            self.record(campaign,'python-ranges',run['configuration_id'],attempt='other-'+str(i),cost=.2)
        report=fixtures.campaign_report(campaign)
        self.assertTrue(report['summary']['workload_complete'])
        self.assertIsNotNone(report['summary']['total_workload_usd'])
        self.assertEqual(report['summary']['cost_kind'],'estimated')
        self.assertIsNone(report['summary']['savings_usd'])
        for pair in report['paired_cost_comparisons']:
            self.assertEqual(pair['status'],'observed-comparison')
            self.assertIsNotNone(pair['counterfactual_difference_usd'])
            self.assertIn('not realized savings',pair['note'])

    def test_freeze_tampering_and_new_development_observations_rejected(self):
        campaign=self.campaign();self.route(campaign,'python-ranges')
        plan=fixtures.execution_plan(campaign,'python-ranges')
        selected=next(r for r in plan['runs'] if 'with_epoch' in r['roles'])
        self.record(campaign,'python-ranges',selected['configuration_id'])
        fixtures.freeze_threshold(campaign,.85)
        changed=copy.deepcopy(campaign);changed['threshold_freeze']['threshold']=.90
        with self.assertRaisesRegex(core.PilotError,'threshold-freeze-mismatch'):fixtures.campaign_report(changed)
        alternative=next(r for r in plan['runs'] if r!=selected)
        with self.assertRaisesRegex(core.PilotError,'development-already-frozen'):
            self.record(campaign,'python-ranges',alternative['configuration_id'],attempt='late')

    def test_recovery_observation_cannot_bypass_frozen_exclusion(self):
        campaign=self.campaign();packet=campaign['frozen']['cases'][0]['packets']['without_epoch']
        excluded=packet['candidates'][-1]
        campaign['frozen']['policy']['excluded_models']=[excluded['model']]
        campaign['campaign_hash']=core.digest(campaign['frozen'])
        self.route(campaign,'python-ranges')
        raw=FixtureTests().score_input(fixtures.fixture('python-ranges'))
        raw['executions']=[{'id':'contract','compiled':True,'exit_code':0}]
        observation={'fixture_id':'python-ranges','configuration_id':core.configuration_id(excluded),'attempt_id':'bad-fallback',
                     'attempt_kind':'fallback','score':raw,'latency_ms':1,
                     'costs':{k:{'usd':None,'kind':'unknown'} for k in core.COST_COMPONENTS}}
        with self.assertRaisesRegex(core.PilotError,'unknown-outcome-configuration'):
            fixtures.record_observation(campaign,observation)


if __name__ == '__main__': unittest.main()
