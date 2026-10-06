"""Optional blinded artifact review. Scores are advisory, never acceptance evidence."""
from __future__ import annotations

import copy
import pilot_core as core
import pilot_questions as questions

VERSION = 'pilot-quality-judge-v1'
LEVELS = ['Absent or contradicted by the supplied evidence.',
          'Substantial gaps or defects remain.',
          'Mostly supported with bounded gaps.',
          'Fully supported by the supplied requirements and observed validation.']
DIMENSIONS = {
    'coverage': 'How completely does the artifact satisfy the stated requirements?',
    'scope': 'How well does the artifact stay within the stated requirements without unrelated changes?',
    'evidence': 'How well do the supplied excerpts and observed validation support the artifact claims?',
    'clarity': 'How clearly does the artifact communicate its result and limitations?',
}


def payload(packet, model):
    core.fields(packet, {'requirements', 'excerpts', 'validation_summary'})
    for name in ('requirements', 'excerpts'):
        core.require(isinstance(packet[name], list) and 0 < len(packet[name]) <= 24, 'invalid-judge-input')
        for text in packet[name]: core.prose(text)
    core.prose(packet['validation_summary'])
    q = {'enough': {'type': 'noul', 'instructions': questions.DATA_NOTICE +
                    'Is there enough supplied evidence to assess requirement coverage, scope, evidence support, and clarity?'}}
    q.update({key: {'type': 'score', 'instructions': questions.DATA_NOTICE + question, 'criteria': LEVELS}
              for key, question in DIMENSIONS.items()})
    return {'model': model, 'state': copy.deepcopy(packet), 'questions': q}


def assess(packet, policy, *, live=False, call=None, key=None):
    import pilot
    result = {'mode': 'advisory', 'status': 'unavailable', 'rubric_version': VERSION,
              'model': policy['model'], 'reason_codes': [], **pilot.empty_usage()}
    if not policy['share_artifacts']:
        result['reason_codes'] = ['artifact-sharing-disabled']
        return result
    if not live:
        result['reason_codes'] = ['live-not-requested']
        return result
    try:
        request = payload(packet, policy['model'])
        result.update(input_hash=core.digest(packet), question_hash=core.digest(request['questions']))
        answers, usage, error = pilot.ask(request, policy, call=call, key=key)
        result.update(usage)
        if error:
            result['reason_codes'] = [error]
        elif answers['enough']['noul'] < 0.90:
            result.update(status='insufficient-evidence', reason_codes=['insufficient-selected-evidence'])
        else:
            scores = {dimension: answers[dimension]['score'] / 3 * 100 for dimension in DIMENSIONS}
            result.update(status='scored', scores=scores, mean_score=sum(scores.values())/len(scores))
    except (ValueError, TypeError, KeyError):
        result['reason_codes'] = ['invalid-judge-input']
    return result
