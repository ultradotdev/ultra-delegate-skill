"""Generated documentation follows the production payloads, including field privacy."""
import copy
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/ultra-delegation/scripts'
sys.path.insert(0, str(SCRIPTS))
import jev
import jev_docs
import jev_qualification as fixtures


class JevDocsTests(unittest.TestCase):
    def test_generated_contract_matches_outbound_preview(self):
        packet = fixtures.route_fixture()
        preview = jev.route(packet, fixtures.policy(), dry_run=True)
        doc = jev_docs.manifest()
        self.assertEqual(preview['payload']['questions'], doc['routing']['questions'])
        self.assertEqual(sorted(preview['payload']['state']), doc['routing']['state_fields'])
        self.assertNotIn('reference_score', doc['judging']['candidate_fields'])
        self.assertNotIn('reference_acceptable', doc['judging']['candidate_fields'])
        for field in ('profile', 'cost_usd'):
            self.assertNotIn(field, doc['judging']['candidate_fields'])

    def test_reference_generation_has_no_network_or_credentials(self):
        with patch.object(jev.transport, 'credential', side_effect=AssertionError('credential lookup')):
            with patch.object(jev.transport, 'request', side_effect=AssertionError('network')):
                self.assertEqual(0, jev_docs.main(['--check']))

    def test_payload_change_propagates_to_manifest(self):
        original = jev.route_questions
        def changed(count):
            questions = copy.deepcopy(original(count))
            questions['ambiguous']['instructions'] = 'Changed semantic question.'
            return questions
        before = jev_docs.manifest()['routing']
        with patch.object(jev, 'route_questions', side_effect=changed):
            after = jev_docs.manifest()['routing']
        self.assertNotEqual(before['question_hash'], after['question_hash'])
        self.assertEqual('Changed semantic question.', after['questions']['ambiguous']['instructions'])


if __name__ == '__main__':
    unittest.main()
