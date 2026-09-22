#!/usr/bin/env python3
"""Opt-in synthetic security qualification with frozen references and held-out bands.

Prepare writes all payload previews. Development and heldout each reserve calls
before inference; resuming never repeats a paid call with uncertain completion.
"""
from __future__ import annotations
import argparse
import copy
import html
import json
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]/'.agents/skills/ultra-delegation/scripts'
sys.path.insert(0, str(SCRIPTS))
import pilot
import pilot_core as core
import pilot_questions as questions
import pilot_security as security
import jev_transport as transport

FIXTURES = SCRIPTS.parent/'assets/security-fixtures.json'


def prepare(root):
    root=Path(root)
    corpus=pilot.read_json(FIXTURES)
    core.require(len(corpus['fixtures'])==10,'security-fixture-count')
    root.mkdir(parents=True,exist_ok=False)
    pilot.write_new(root/'fixtures.json',corpus)
    for case in corpus['fixtures']:
        payload=questions.security_payload(case['security_payload'],'jev-1.13.0')
        transport.encoded_payload(payload)
        pilot.write_new(root/(case['id']+'-preview.json'),payload)
    template={'fixture_hash':core.digest(corpus),'reviewer_id':None,'independent':True,
              'approved':False,'findings':[]}
    pilot.write_new(root/'reference-review-template.json',template)
    return {'prepared':True,'synthetic_cases':10,'reference_review_required':True,'output':str(root.resolve())}


def references(root, review_file=None):
    root=Path(root);corpus=pilot.read_json(root/'fixtures.json')
    review=pilot.read_json(review_file or root/'reference-review.json')
    core.fields(review,{'fixture_hash','reviewer_id','independent','approved','findings'})
    core.label(review['reviewer_id'])
    core.require(review['independent'] is True and review['approved'] is True,'independent-references-required')
    core.require(review['fixture_hash']==core.digest(corpus),'references-changed')
    core.require(isinstance(review['findings'],list),'invalid-reference-findings')
    for text in review['findings']:core.prose(text)
    if review_file:
        canonical=root/'reference-review.json'
        if canonical.exists():core.require(pilot.read_json(canonical)==review,'reference-review-changed')
        else:pilot.write_new(canonical,review)
    return corpus, review


def metrics(rows, bands):
    result={'cases':len(rows),'available':0,'unavailable':0,'missed_concerns':0,'vulnerable_requirements':0,
            'false_alarms':0,'safe_requirements':0,'follow_up_cases':0,'insufficient_context_misses':0,
            'independent_reference_findings':0,'strong_concern_cases':0,'latency_ms':0,'known_evaluator_cost_usd':0,
            'cost_complete':True,'cost_kind':'estimated','native_worker_runs':0}
    for row in rows:
        s=row['assessment']
        if s['status']=='unavailable':result['unavailable']+=1;result['cost_complete']=False;continue
        result['available']+=1
        signals={r['id']:r for r in s['requirements']};follow=False
        for ref in row['reference']['requirements']:
            r=signals[ref['id']]
            flagged=r['violation_probability']>bands['investigate'] or r['evidence_probability']<bands['sufficient']
            follow |= flagged
            if ref['violation_expected']:
                result['vulnerable_requirements']+=1;result['independent_reference_findings']+=1
                result['missed_concerns']+=int(not flagged)
            elif ref['sufficient_expected']:
                result['safe_requirements']+=1;result['false_alarms']+=int(flagged)
            if not ref['sufficient_expected']:
                result['insufficient_context_misses']+=int(r['evidence_probability']>=bands['sufficient'])
        result['follow_up_cases']+=int(follow)
        result['strong_concern_cases']+=int(any(r['violation_probability']>=bands['strong'] and r['evidence_probability']>=bands['sufficient'] for r in signals.values()))
        result['latency_ms']+=s.get('latency_ms') or 0
        if s.get('cost_usd') is None:result['cost_complete']=False
        else:result['known_evaluator_cost_usd']+=s['cost_usd']
    result['follow_up_rate']=result['follow_up_cases']/result['available'] if result['available'] else None
    return result


def load_rows(root, split):
    root=Path(root)
    corpus=pilot.read_json(root/'fixtures.json')
    fixtures={f['id']:f for f in corpus['fixtures'] if f['split']==split}
    review=pilot.read_json(root/'reference-review.json')
    rows=[]
    for path in sorted((root/split).glob('*.json')):
        stored=pilot.read_json(path)
        row={k:v for k,v in stored.items() if k!='integrity'}
        core.require(stored.get('integrity')==core.digest(row),'qualification-record-changed')
        core.require(row.get('id')==path.stem and path.stem in fixtures and row.get('split')==split,'qualification-fixture-mismatch')
        case=fixtures[path.stem]
        core.require(row.get('fixture_hash')==core.digest(case) and row.get('reference')==case['reference'],'qualification-fixture-changed')
        core.require(row.get('reference_reviewer')==review['reviewer_id'],'reference-review-changed')
        core.require(row.get('transport') in {'mock','live'},'invalid-qualification-transport')
        assessed=row['assessment']
        core.require(assessed['model']=='jev-1.13.0' and assessed['question_version']==questions.SECURITY_VERSION,'qualification-evaluator-changed')
        if assessed['status']!='unavailable':
            core.require(assessed.get('input_hash')==core.digest(case['security_payload']),'qualification-input-changed')
            payload=questions.security_payload(case['security_payload'],assessed['model'])
            core.require(assessed.get('question_hash')==core.digest(payload['questions']),'qualification-questions-changed')
            core.require([v['id'] for v in assessed['requirements']]==[v['id'] for v in case['security_payload']['requirements']],'qualification-coverage-changed')
            core.require(all(core.transport.number(v[k]) for v in assessed['requirements'] for k in ('violation_probability','evidence_probability')),'invalid-qualification-probability')
        if 'security_thresholds' in row:security.bands({'security_thresholds':row['security_thresholds']})
        rows.append(row)
    return rows


def freeze(root, bands=None):
    root=Path(root);_,reference_review=references(root)
    rows=load_rows(root,'development')
    core.require(len(rows)==6 and all(r['assessment']['status']!='unavailable' for r in rows),'development-incomplete')
    selected=copy.deepcopy(bands or security.BANDS)
    security.bands({'security_thresholds':selected})
    record={'bands':selected,'question_version':questions.SECURITY_VERSION,'model':'jev-1.13.0',
            'development_hash':core.digest(rows),'reference_review_hash':core.digest(reference_review),'fixture_hash':core.digest(pilot.read_json(root/'fixtures.json')),
            'frozen_at':core.now(),'rationale':'Experimental bands frozen before held-out inference. Small authored examples do not establish calibration.'}
    pilot.write_new(root/'frozen.json',record)
    return record


def run(root, split, *, live=False, review_file=None, locator=None, call=None, key=None):
    import pilot_workflow
    with pilot_workflow._lock(Path(root)/'.qualification.lock'):
        return _run(root,split,live=live,review_file=review_file,locator=locator,call=call,key=key)


def _run(root, split, *, live=False, review_file=None, locator=None, call=None, key=None):
    root=Path(root);corpus,review=references(root,review_file)
    if split=='heldout':
        frozen=pilot.read_json(root/'frozen.json')
        core.require(frozen['question_version']==questions.SECURITY_VERSION and frozen['fixture_hash']==core.digest(corpus),'frozen-contract-changed')
        core.require(frozen['development_hash']==core.digest(load_rows(root,'development')),'development-changed-after-freeze')
        core.require(frozen['reference_review_hash']==core.digest(review),'reference-review-changed')
        bands=frozen['bands']
    else:bands=security.BANDS
    p=core.policy({'share_artifacts':True,'security_thresholds':bands,**(locator or {})})
    if live and key is None:
        try:key,_=transport.credential(p['credential_ref'],service=p['credential_service'])
        except transport.ServiceError as exc:return {'status':'pending','reason':exc.code,'paid_calls':0}
    folder=root/split;folder.mkdir(exist_ok=True)
    existing=load_rows(root,'development')+load_rows(root,'heldout')
    core.require(all(r['transport']==('live' if live else 'mock') for r in existing),'mixed-live-and-mock-run')
    for case in corpus['fixtures']:
        if case['split']!=split:continue
        path=folder/(case['id']+'.json');pending=path.with_suffix('.pending')
        if path.exists():continue
        if pending.exists():
            assessed=security.evaluate(None,p,True)
            assessed.update(reason_codes=['interrupted-evaluation-not-repeated'],cost_usd=None,cost_kind='unknown')
        else:
            payload=questions.security_payload(case['security_payload'],p['model'])
            core.require(pilot.read_json(root/(case['id']+'-preview.json'))==payload,'preview-changed')
            pilot.write_new(pending,{'fixture_hash':core.digest(case),'question_version':questions.SECURITY_VERSION})
            if live:
                fn=call or (lambda payload,secret:transport.request(payload,secret,max_attempts=1))
            else:
                def fn(payload,secret):
                    reply,usage=pilot.synthetic_response(payload,secret)
                    for i,ref in enumerate(case['reference']['requirements']):
                        reply['answers']['violation_'+str(i)]['noul']=.99 if ref['violation_expected'] else .01
                        reply['answers']['sufficient_'+str(i)]['noul']=.99 if ref['sufficient_expected'] else .01
                    return reply,usage
            assessed=security.evaluate(case['security_payload'],p,True,live=True,call=fn,key=key or 'offline-fixture')
        record={'id':case['id'],'split':split,'transport':'live' if live else 'mock','fixture_hash':core.digest(case),
                'reference':case['reference'],'security_thresholds':copy.deepcopy(bands),'assessment':assessed,'reference_reviewer':review['reviewer_id']}
        pilot.write_new(path,{**record,'integrity':core.digest(record)});pending.unlink(missing_ok=True)
    return report(root)


def report(root):
    root=Path(root)
    splits={k:load_rows(root,k) for k in ('development','heldout')}
    frozen=pilot.read_json(root/'frozen.json') if (root/'frozen.json').exists() else None
    bands=frozen['bands'] if frozen else security.BANDS
    value={'schema':'ultra-security-qualification-v1','question_version':questions.SECURITY_VERSION,'model':'jev-1.13.0',
           'bands':bands,'shipped_default_bands':security.BANDS,'frozen':frozen,
           'splits':{k:metrics(v,(v[0].get('security_thresholds',security.BANDS if k=='development' else bands) if v else bands)) for k,v in splits.items()},
           'development_replayed_at_frozen_bands':metrics(splits['development'],bands),'cases':sum(splits.values(),[]),
           'development_sensitivity':[{'bands':{**security.BANDS,'investigate':low,'sufficient':enough},
             'metrics':metrics(splits['development'],{**security.BANDS,'investigate':low,'sufficient':enough})}
             for low in (.1,.2,.3) for enough in (.8,.9,.95)],
           'limitations':['Ten authored Python examples; no broad security guarantee or model-quality qualification.',
             'Independent references are seeded findings, not worker-performance evidence.',
             'Violation probabilities are not severity. Token-based prices are estimates.',
             'Development was called at its recorded initial bands; the frozen-band development replay reuses probabilities and makes no additional inference or outcome claim.',
             'Mock runs test the harness only; they provide no model calibration evidence.']}
    native=pilot.read_json(root/'native-results.json') if (root/'native-results.json').exists() else None
    value['native_repairs']=native
    (root/'report.json').write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    e=html.escape
    body=['<!doctype html><meta charset="utf-8"><title>Security signal qualification</title><style>body{font:16px system-ui;max-width:1050px;margin:40px auto;padding:0 20px}table{border-collapse:collapse;width:100%}td,th{padding:9px;text-align:left;border-bottom:1px solid #ccc}details{margin-top:24px}.muted{color:#555}</style>',
          '<h1>Security signal check</h1><p>Can Jev flag the seeded defect, leave its safe counterpart clear, and recognize missing context?</p>',
          '<p><b>Experimental thresholds:</b> investigate above '+str(bands['investigate'])+'; strong concern at '+str(bands['strong'])+'; insufficient evidence below '+str(bands['sufficient'])+'. Shipped default remains '+str(security.BANDS['sufficient'])+'. '+('Frozen before held-out calls.' if frozen else 'Not yet frozen.')+'</p>',
          '<p>Development counts show the original '+str(security.BANDS['sufficient'])+' evidence cutoff. Held-out counts show the frozen '+str(bands['sufficient'])+' cutoff. Details include a development-only rule replay.</p><table><tr><th>Split</th><th>Assessed</th><th>Missed concerns</th><th>False alarms</th><th>Follow-up</th></tr>']
    for split,m in value['splits'].items():body.append(f"<tr><td>{split}</td><td>{m['available']}/{6 if split=='development' else 4}</td><td>{m['missed_concerns']}/{m['vulnerable_requirements']}</td><td>{m['false_alarms']}/{m['safe_requirements']}</td><td>{m['follow_up_cases']}/{m['available']}</td></tr>")
    body.append('</table><h2>Each code example</h2><table><tr><th>Task</th><th>Reference</th><th>Violation</th><th>Enough evidence</th><th>Signal</th></tr>')
    for row in value['cases']:
        r=next(iter(row['assessment']['requirements']),{})
        body.append(f"<tr><td>{e(row['id'])} ({e(row['transport'])})</td><td>{e(row['reference']['outcome'])}</td><td>{r.get('violation_probability','—')}</td><td>{r.get('evidence_probability','—')}</td><td>{e(r.get('signal','unavailable'))}</td></tr>")
    body.append('</table>')
    if native:
        body.append('<h2>Actual worker repairs</h2><p>Four bounded code fixes by Sol medium, independently checked before screening. Final accepted: '+str(native.get('final_accepted_tasks','pending'))+'/4. Worker billing unavailable. This is a fixed-model signal test.</p><table><tr><th>Code task</th><th>Independent checks</th><th>Jev signal</th><th>Final review</th></tr>')
        for row in native['cases']:
            signal=next(iter(row['assessment']['requirements']),{})
            follow=native.get('follow_up_review',{})
            disposition=follow.get('disposition') if follow.get('case_id')==row['id'] else 'no concern detected in assessed evidence'
            body.append('<tr><td>'+e(row['id'])+'</td><td>'+('Passed' if row['accepted'] else 'Failed')+'</td><td>'+e(signal.get('signal','unavailable'))+'</td><td>'+e(disposition or 'pending')+'</td></tr>')
        body.append('</table><p>The diagnostics evidence concern was dismissed by an independent Terra medium reviewer after code inspection and a toy-token test.</p>')
    body.append('<p class="muted">'+' '.join(e(x) for x in value['limitations'])+'</p><details><summary>Provenance, costs, and development sensitivity</summary><pre>'+e(json.dumps(value,indent=2))+'</pre></details>')
    (root/'report.html').write_text(''.join(body))
    return {'html':str((root/'report.html').resolve()),'json':str((root/'report.json').resolve()),'splits':value['splits']}


def main(argv=None):
    parser=pilot.SafeParser(description=__doc__)
    parser.add_argument('operation',choices=('prepare','development','freeze','heldout','report'))
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--reference-review',type=Path)
    parser.add_argument('--credential-locator',type=Path)
    parser.add_argument('--bands',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.operation=='prepare':result=prepare(args.root)
        elif args.operation=='freeze':result=freeze(args.root,pilot.read_json(args.bands) if args.bands else None)
        elif args.operation=='report':result=report(args.root)
        else:
            locator=pilot.read_json(args.credential_locator) if args.credential_locator else {}
            core.fields(locator,set(),{'credential_service','credential_ref'})
            result=run(args.root,args.operation,live=args.live,review_file=args.reference_review,locator=locator)
        print(json.dumps(result,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError):
        print('{"error":"security-qualification-invalid-or-incomplete"}',file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
