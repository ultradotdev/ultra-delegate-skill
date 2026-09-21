"""Offline candidate-pool qualification, with synthetic worker evidence only."""
import copy
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/ultra-delegation/scripts'
sys.path.insert(0, str(SCRIPTS))
import shortlist
import ultra_delegation as ud
import jev


def packet():
    return {
        'task': {'task_family': 'review', 'operation': 'patch_proposal', 'language': 'python',
                 'risk': 'low', 'coupling': 'low', 'validation': 'unit-tests', 'tools': 'read-only'},
        'context': {'host': 'codex', 'provider': 'openai',
                    'available_models': ['gpt-5.6-luna', 'gpt-5.6-terra'],
                    'thinking_settings': {m: ['medium'] for m in ['gpt-5.6-luna', 'gpt-5.6-terra']}},
        'seed_profile': {'prompt_profile': 'review-v1', 'tool_policy': 'read-only-v1'},
        'candidates': [], 'records': []}


def profile(model='gpt-5.6-terra'):
    return {'task_family': 'review', 'provider': 'openai', 'host': 'codex', 'model': model,
            'model_revision': model, 'execution_location': 'remote',
            'thinking': {'normalized': 'medium', 'native': 'medium'},
            'prompt_profile': 'review-v1', 'tool_policy': 'read-only-v1'}


def outcomes(p, task, n=3):
    return [{'id': f'{ud.profile_id(p)}-{i}', 'profile': p, 'task_signature': task,
             'accepted': True, 'created_at': (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=n-i)).isoformat(),
             'gates': [{'id': 'tests', 'mandatory': True, 'passed': True}],
             'metrics': {'quality_score': 92, 'cost_usd': 0.02}, 'cost_kind': 'measured'} for i in range(n)]


class ShortlistTests(unittest.TestCase):
    def test_seed_availability_and_unknown_cost(self):
        p = packet()
        result = shortlist.build_shortlist(p)
        self.assertEqual(len(result['candidates']), 2)
        self.assertTrue(all(r['tier'] == 1 and r['cost_usd'] is None for r in result['ranked']))
        self.assertFalse(result['dispatch_authorized'])
        self.assertIsNone(result['evidence_baseline_profile_id'])
        p['context']['available_models'] = []
        self.assertEqual(shortlist.build_shortlist(p)['candidates'], [])
        p['context']['available_models'] = ['gpt-5.6-terra']
        p['context']['thinking_settings'] = {}
        self.assertEqual(shortlist.build_shortlist(p)['candidates'], [])

    def test_seed_instantiation_requires_explicit_prompt_tool_identity(self):
        p = packet(); del p['seed_profile']
        self.assertEqual(shortlist.build_shortlist(p)['candidates'], [])
        p['seed_profile'] = {'prompt_profile': 'x'}
        with self.assertRaises(ValueError): shortlist.build_shortlist(p)

    def test_locality_exclusions_and_quarantine(self):
        for change in ({'host': 'claude-code'}, {'provider': 'anthropic'}):
            p = packet(); p['context'].update(change)
            self.assertEqual(shortlist.build_shortlist(p)['candidates'], [])
        p = packet(); p['policy'] = {'exclusions': ['gpt-5.6-luna'], 'quarantined_imports': [ud.profile_id(profile())]}
        self.assertEqual(shortlist.build_shortlist(p)['candidates'], [])

    def test_learns_exact_task_and_does_not_mutate_inputs(self):
        p = packet(); p['records'] = outcomes(profile(), p['task']); p['limit'] = 1
        before = copy.deepcopy(p)
        r = shortlist.build_shortlist(p)
        self.assertEqual(r['candidates'][0]['profile'], profile())
        self.assertEqual(r['evidence_baseline_profile_id'], ud.profile_id(profile()))
        self.assertEqual(p, before)
        for o in p['records']: o['task_signature'] = {**p['task'], 'language': 'javascript'}
        r = shortlist.build_shortlist(p)
        self.assertIsNone(r['evidence_baseline_profile_id'])
        self.assertEqual(len(r['ignored_records']), 3)

    def test_supplied_success_adds_exact_nonseed_model(self):
        p = packet(); new = profile('project-discovered-worker')
        p['context']['available_models'].append(new['model'])
        p['context']['thinking_settings'][new['model']] = ['medium']
        p['records'] = outcomes(new, p['task']); p['limit'] = 1
        r = shortlist.build_shortlist(p)
        self.assertEqual(r['candidates'][0]['profile'], new)
        self.assertEqual(r['ranked'][0]['origins'], ['local-worker-evidence'])

    def test_latest_failure_demotes_even_when_records_reordered(self):
        p = packet(); p['records'] = outcomes(profile(), p['task']); p['limit'] = 1
        failure = copy.deepcopy(p['records'][-1]); failure.update(id='failure', accepted=False, created_at=ud.now())
        failure['gates'][0]['passed'] = False; failure['metrics']['quality_score'] = 20
        p['records'].insert(0, failure)
        r = shortlist.build_shortlist(p)
        self.assertIsNone(r['evidence_baseline_profile_id'])
        self.assertEqual(r['candidates'][0]['profile']['model'], 'gpt-5.6-luna')
        self.assertEqual(next(x for x in r['ranked'] if x['profile_id'] == ud.profile_id(profile()))['status'], 'retest-required')

    def test_stale_and_local_quarantine(self):
        p = packet(); p['records'] = outcomes(profile(), p['task'])
        for r in p['records']: r['created_at'] = '2000-01-01T00:00:00+00:00'
        self.assertIsNone(shortlist.build_shortlist(p)['evidence_baseline_profile_id'])
        for r in p['records']: r['status'] = 'quarantined'
        self.assertNotIn(profile(), [c['profile'] for c in shortlist.build_shortlist(p)['candidates']])

    def test_pins_user_choices_and_protected_overflow(self):
        p = packet(); p['limit'] = 1; p['policy'] = {'pins': ['gpt-5.6-terra']}
        self.assertEqual(shortlist.build_shortlist(p)['candidates'][0]['profile'], profile())
        p['candidates'] = [{'profile': profile('gpt-5.6-luna'), 'description': 'Explicit choice.', 'user_selected': True}]
        r = shortlist.build_shortlist(p)
        self.assertEqual(r['status'], 'coordinator'); self.assertEqual(r['candidates'], [])
        p['policy']['exclusions'] = ['gpt-5.6-terra']
        self.assertEqual(shortlist.build_shortlist(p)['candidates'][0]['profile']['model'], 'gpt-5.6-luna')

    def test_entire_highest_evidence_tier_protected(self):
        p = packet(); p['limit'] = 1
        p['records'] = outcomes(profile(), p['task']) + outcomes(profile('gpt-5.6-luna'), p['task'])
        r = shortlist.build_shortlist(p)
        self.assertEqual(r['reason'], 'protected-pool-exceeds-limit'); self.assertEqual(r['candidates'], [])

    def test_identity_record_and_duplicate_validation(self):
        p = packet(); p['records'] = outcomes(profile(), p['task'])
        p['records'][0]['profile_id'] = 'wrong'
        with self.assertRaises(ValueError): shortlist.build_shortlist(p)
        del p['records'][0]['profile_id']; p['records'].append(p['records'][0])
        with self.assertRaises(ValueError): shortlist.build_shortlist(p)
        p = packet(); p['candidates'] = [{'profile': profile(), 'description': 'Explicit.'}]
        p['candidates'][0]['profile']['execution_location'] = 'local'
        p['records'] = outcomes(profile(), p['task'])
        with self.assertRaises(ValueError): shortlist.build_shortlist(p)

    def test_seed_does_not_override_supplied_configuration(self):
        p = packet(); supplied = profile(); del supplied['model_revision']
        supplied['prompt_profile_hash'] = 'observed-prompt-hash'
        p['candidates'] = [{'profile': supplied, 'description': 'Explicit.'}]
        r = shortlist.build_shortlist(p)
        self.assertIn(supplied, [c['profile'] for c in r['candidates']])

    def test_cli_and_offline_stability(self):
        p = packet()
        result = subprocess.run([sys.executable, '-S', str(SCRIPTS/'shortlist.py'), '--input', '-'], input=json.dumps(p), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), shortlist.build_shortlist(p))
        p['candidates'] = [{'profile': profile(m), 'description': 'Explicit.'} for m in p['context']['available_models']]
        first = shortlist.build_shortlist(p); p['candidates'].reverse()
        second = shortlist.build_shortlist(p)
        self.assertEqual(first['candidates'], second['candidates'])

    def test_shadow_judging_is_not_worker_evidence(self):
        p = packet(); p['records'] = [{'schema': 'ultra-delegation-jev-v1', 'shadow_scores': {'candidate_0': 100}}]
        with self.assertRaises(ValueError): shortlist.build_shortlist(p)

    def test_composed_route_keeps_latest_failure_and_never_reads_credentials(self):
        p = packet(); p['records'] = outcomes(profile(), p['task'])
        failure = copy.deepcopy(p['records'][-1]); failure.update(id='latest-failure', accepted=False, created_at=ud.now())
        failure['gates'][0]['passed'] = False; failure['metrics']['quality_score'] = 20
        p['records'].insert(0, failure)
        with patch.object(jev.transport, 'credential', side_effect=AssertionError('credentials accessed')):
            result = shortlist.build_shortlist(p)
            self.assertEqual(result['records'][-1]['id'], 'latest-failure')
            routed = jev.route({'run_id': 'shortlist-test', 'summary': 'Review a small function.',
                                'requirements': ['Find correctness defects.'], 'task': p['task'], 'context': p['context'],
                                'snapshot': {'telemetry': {'availability': 'unavailable'}},
                                'candidates': result['candidates'], 'records': result['records']}, copy.deepcopy(ud.DEFAULT_POLICY))
        failed = next(r for r in routed['ranking'] if r['profile_id'] == ud.profile_id(profile()))
        self.assertEqual(failed['status'], 'retest-required'); self.assertEqual(failed['tier'], 1)
        self.assertEqual(routed['action'], 'coordinator')


if __name__ == '__main__': unittest.main()
