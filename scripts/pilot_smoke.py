#!/usr/bin/env python3
"""Three synthetic Jev pilot scenarios. Offline by default; live uses at most 3 HTTP attempts."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.agents/skills/ultra-delegation/scripts'))
import pilot
import pilot_core as core
import jev_transport as transport


def fixtures():
    clear = pilot.fixture()
    clear['task_id'] = clear['group_id'] = 'repo-smoke-bounded-tests'
    clear['task'].update(scope_id='python.unit-test-draft', operation='unit-test-addition',
        summary='Write three pytest tests for increment(x), a pure function defined exactly as return x + 1 for Python integers. Return test functions as text only.',
        requirements=['Test increment(0) == 1.', 'Test increment(4) == 5.', 'Test increment(-3) == -2.',
                      'increment is already available in the test module namespace; no import or module path is needed.',
                      'Return exactly three standalone functions named test_zero, test_positive, and test_negative, each containing only its required assert. No fixtures, parameterization, wrappers, execution, or integration is required.'],
        worker_boundary='Return only three test functions. No repository changes, tool use, execution, architecture or product decisions. The full deliverable is those three functions as text; all implementation and integration decisions are supplied.',
        intended_use='A synthetic draft discarded after review. It will not change a running system.',
        acceptance_gates=['exact-assertions', 'independent-review'], required_tools=[])
    for c in clear['candidates']:
        c.update(capability_description='Drafts simple Python unit tests for fully specified pure functions.',
                 scope_envelope='Small Python test drafts with explicit inputs and expected outputs. No architecture or unspecified product decisions.', estimate_usd=None)
    unclear = copy.deepcopy(clear)
    unclear['task_id'] = unclear['group_id'] = 'repo-smoke-missing-requirements'
    unclear['task'].update(summary='Implement input validation. The requester has not specified input format, allowed values, or required output.',
                          requirements=['Implement the desired validation behavior.'], operation='validation-proposal',
                          worker_boundary='Propose only the requested validation. Do not invent missing product requirements.')
    boundaries = copy.deepcopy(clear['task']['boundaries'])
    requirements = [{'id':'owner-read','mandatory':True,'requirement':'Only an authenticated owner may read a document. get_document is the sole authorization boundary; there are no upstream checks and database.read_document returns any requested document.'}]
    boundaries['security_requirements'] = {'items':requirements,'not_applicable':None}
    security = {'boundaries':boundaries,'requirements':requirements,
                'excerpts':['def get_document(request, doc_id):\n    return database.read_document(doc_id)'],
                'validation_summary':'Synthetic example: an unauthenticated request with another user document ID returns that document. No other checks are present.'}
    return clear, unclear, security


def run(root, *, live=False, locator=None):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)  # Reserve before credential lookup or paid work.
    p = core.policy({'mode':'active', 'share_summaries':True, 'share_artifacts':True, 'baseline_id':'candidate-2', **(locator or {})})
    ledger = root / 'ledger'
    pilot.init_project(ledger, p)
    clear, unclear, security = fixtures()
    cases = []
    report = {'schema':'ultra-pilot-smoke-v1', 'fixture_version':'repo-smoke-2', 'synthetic_inputs':True, 'transport':'live' if live else 'mock',
              'evaluation':'observational', 'maximum_http_attempts':3, 'cases':cases}
    key = 'synthetic-offline-key'
    if live:
        try:
            key, source = transport.credential(p['credential_ref'], service=p['credential_service'])
            report['credential_source'] = source
        except transport.ServiceError as error:
            report.update(status='pending', reason=error.code, http_attempts=0)
            pilot.write_new(root/'smoke.json',report)
            return report
    reserved = 0
    def call(payload, secret):
        nonlocal reserved
        if reserved >= 3: raise transport.ServiceError('smoke-budget-exhausted')
        reserved += 1
        if live:
            return transport.request(payload, secret, max_attempts=1)
        result, meta = pilot.synthetic_response(payload, secret)
        if payload['state'].get('task',{}).get('operation') == 'validation-proposal':
            result['answers']['missing_requirement']['noul'] = .99
        if 'violation_0' in result['answers']:
            result['answers']['violation_0']['noul'] = .99
        return result, meta
    for name, packet, expected in [('bounded-test-draft', clear, 'route'), ('missing-requirements', unclear, 'clarify')]:
        # Exact preview is safe here because every input is authored synthetic data.
        pilot.write_new(root/(name+'-preview.json'), pilot.route_packet(packet,p,dry_run=True))
        d = pilot.route_packet(packet,p,live=True,call=call,key=key)
        pilot.write_new(ledger/'decisions'/(d['id']+'.json'),d)
        cases.append({'name':name,'expected':expected,'observed':d['recommended_action'],
                      'passed':d['status'] != 'unavailable' and d['recommended_action']==expected,
                      'decision_id':d['id'],'status':d['status'],'reason_codes':d['reason_codes'],'usage':d['router']})
        if d['status']=='unavailable': break
    if len(cases)==2 and all(c['status']!='unavailable' for c in cases):
        s = pilot.security_assessment(security,p,True,live=True,call=call,key=key)
        pilot.write_new(root/'security.json',s)
        cases.append({'name':'missing-document-authorization','expected':'indeterminate','observed':s['status'],
                      'passed':s['status']=='indeterminate','status':s['status'],'reason_codes':s['reason_codes'],
                      'usage':{k:s[k] for k in ('attempts','latency_ms','cost_usd','cost_kind')}})
    report.update(status='completed' if len(cases)==3 else 'incomplete', passed=sum(c['passed'] for c in cases),
                  observed_cases=len(cases), pending_cases=3-len(cases), http_attempts=reserved if live else 0,
                  worker_executions=0, artifacts=pilot.report(ledger))
    pilot.write_new(root/'smoke.json',report)
    return report


def main(argv=None):
    parser=pilot.SafeParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--credential-locator',type=Path,help='JSON containing only credential_service and credential_ref; never a credential value')
    args=parser.parse_args(argv)
    try:
        locator=pilot.read_json(args.credential_locator) if args.credential_locator else {}
        core.fields(locator,set(),{'credential_service','credential_ref'})
        value=run(args.output_dir,live=args.live,locator=locator)
        print(json.dumps(value,indent=2,allow_nan=False))
        return 0
    except (ValueError,OSError,TypeError,KeyError):
        print('{"error":"smoke-input-or-output-invalid"}',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
