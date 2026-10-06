#!/usr/bin/env python3
"""ud: route a bounded task through Jev, run it on the cheapest adequate worker,
check it, and escalate on failure. One command for the coordinator.

  ud.py delegate task.json [--host codex|claude] [--rule jev_noul] [--repo DIR]
  ud.py escalate RUN_ID --findings "what was wrong"

Prints one JSON result. Exit 0 when a worker passed or needs review; 3 when the
task is handed back to the coordinator. Python 3.10+, standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jev  # noqa: E402
import ladder  # noqa: E402
import workers  # noqa: E402


def load_config(path=None):
    return json.loads(Path(path or HERE.parent / 'assets' / 'tiers.json').read_text())


def state_dir(repo):
    root = Path(os.environ.get('UD_STATE') or Path.home() / '.local' / 'state' / 'ultra-delegation')
    d = root / f'{repo.name}-{hashlib.sha256(str(repo).encode()).hexdigest()[:8]}'
    d.mkdir(parents=True, exist_ok=True)
    return d


def detect_host():
    if os.environ.get('CLAUDECODE'):
        return 'claude'
    if any(k.startswith('CODEX_') for k in os.environ):
        return 'codex'
    return None


def load_task(path):
    task = json.loads(Path(path).read_text())
    if not isinstance(task.get('goal'), str) or not task['goal'].strip():
        raise SystemExit('task.json needs a non-empty "goal"')
    if not isinstance(task.get('acceptance'), list) or not task['acceptance']:
        raise SystemExit('task.json needs a non-empty "acceptance" list')
    return task


def outcomes(state):
    path = state / 'outcomes.jsonl'
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def track_records(rows):
    """Coarse first-attempt record per rung and difficulty, from verified outcomes only."""
    tally = {}
    for r in rows:
        if r.get('first_attempt') and r.get('verified_by') and r.get('difficulty') is not None:
            t = tally.setdefault(r['rung'], {}).setdefault(round(r['difficulty']), [0, 0])
            t[0] += bool(r['passed'])
            t[1] += 1
    return {rung: '; '.join(f'difficulty {d}: {p}/{n} first-attempt passes' for d, (p, n) in sorted(levels.items()))
            for rung, levels in tally.items()}


def log(state, row):
    with open(state / 'outcomes.jsonl', 'a') as f:
        f.write(json.dumps(row) + '\n')


def findings_from(result):
    if result['status'] != 'completed':
        return f"Worker {result['status']}: {result.get('error', '')}"
    return f"The check `{result.get('check')}` failed:\n{result.get('check_output', '')}"


def run_ladder(run, start_index, findings=None):
    """Try rungs from start_index upward until one passes, needs review, or all fail."""
    cfg, task, rungs, state = run['cfg'], run['task'], run['rungs'], run['state']
    out = state / 'runs' / run['id']
    for i in range(start_index, len(rungs)):
        n = len(run['attempts']) + 1
        result = workers.attempt(run['repo'], run['base'], rungs[i], task, out / f'a{n}', cfg, findings)
        if result['status'] == 'infra_error':  # one retry; infrastructure is not the model's fault
            result = workers.attempt(run['repo'], run['base'], rungs[i], task, out / f'a{n}-retry', cfg, findings)
        result.update(index=i, check=task.get('check'))
        run['attempts'].append(result)
        log(state, {'ts': now(), 'run': run['id'], 'host': run['host'], 'rule': run['rule'],
                    'route': run['routing']['route'], 'difficulty': run['routing'].get('difficulty'),
                    'rung': rungs[i]['id'], 'index': i, 'start_index': run['start_index'],
                    'first_attempt': n == 1, 'status': result['status'], 'passed': result['passed'],
                    'verified_by': 'check' if result['status'] == 'completed' and task.get('check') else None,
                    'cost_usd': result['cost_usd'], 'seconds': result['seconds']})
        if result['passed'] is None:
            return finish(run, 'needs_review', result)
        if result['passed']:
            return finish(run, 'passed', result)
        findings = findings_from(result)
    log(state, {'ts': now(), 'run': run['id'], 'event': 'escalated_to_coordinator', 'host': run['host']})
    return finish(run, 'escalate_to_coordinator', None, findings)


def finish(run, status, final, findings=None):
    costs = [a['cost_usd'] for a in run['attempts']]
    known = [c for c in costs if c is not None]
    summary = {
        'run': run['id'], 'status': status,
        'rung': final['rung'] if final else None,
        'patch': final['patch'] if final and final.get('patch_bytes') else None,
        'apply': f"git apply --3way {final['patch']}" if final and final.get('patch_bytes') else None,
        'route': {k: run['routing'].get(k) for k in ('route', 'difficulty', 'passes', 'start', 'error')},
        'start_rung': run['rungs'][run['start_index']]['id'],
        'attempts': [{k: a.get(k) for k in ('rung', 'status', 'passed', 'cost_usd', 'seconds', 'summary')}
                     for a in run['attempts']],
        'worker_cost_usd': round(sum(known), 6) if known else None,
        'cost_complete': len(known) == len(costs),
        'routing_cost_usd': run['routing'].get('cost_usd'),
        'findings': findings,
    }
    if status == 'needs_review':
        summary['next'] = f"Review the patch. If it is wrong: ud.py escalate {run['id']} --findings '...'"
    elif status == 'escalate_to_coordinator':
        summary['next'] = 'Every worker rung failed. Do the task yourself using the findings.'
    saved = {k: v for k, v in run.items() if k not in ('cfg', 'state')}
    saved.update(repo=str(run['repo']), result=summary)
    (run['state'] / 'runs' / run['id'] / 'run.json').write_text(json.dumps(saved, indent=1, default=str))
    return summary


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def delegate(args):
    cfg = load_config(args.tiers)
    task = load_task(args.task)
    repo = Path(workers.git(args.repo, 'rev-parse', '--show-toplevel').strip())
    host = args.host or detect_host()
    if host not in cfg['ladders']:
        raise SystemExit('pass --host codex or --host claude')
    rungs, state = cfg['ladders'][host], state_dir(repo)
    rule = args.rule or cfg.get('default_rule', 'jev_noul')
    routing = {'route': 'default', 'error': 'rule does not use Jev'} if rule == 'cheapest_first' else \
        jev.route(task, rungs, track_records(outcomes(state)), repo, cfg.get('share_code', True))
    start = ladder.pick(rule, routing, cfg.get('cutoff', 0.5))
    run_id = dt.datetime.now().strftime('%Y%m%d-%H%M%S-') + secrets.token_hex(2)
    (state / 'runs' / run_id).mkdir(parents=True)
    run = {'id': run_id, 'cfg': cfg, 'task': task, 'repo': repo, 'host': host, 'rule': rule, 'rungs': rungs,
           'state': state, 'routing': routing, 'start_index': start, 'base': workers.base_commit(repo), 'attempts': []}
    return run_ladder(run, start)


def escalate(args):
    repo = Path(workers.git(args.repo, 'rev-parse', '--show-toplevel').strip())
    state = state_dir(repo)
    path = state / 'runs' / args.run / 'run.json'
    if not path.exists():
        raise SystemExit(f'unknown run {args.run}')
    run = json.loads(path.read_text())
    run.update(cfg=load_config(args.tiers), state=state, repo=Path(run['repo']))
    last = run['attempts'][-1]
    log(state, {'ts': now(), 'run': run['id'], 'host': run['host'], 'rule': run['rule'], 'route': run['routing']['route'],
                'difficulty': run['routing'].get('difficulty'), 'rung': last['rung'], 'index': last['index'],
                'start_index': run['start_index'], 'first_attempt': len(run['attempts']) == 1,
                'status': 'rejected', 'passed': False, 'verified_by': 'review'})
    return run_ladder(run, last['index'] + 1, 'The coordinator rejected the previous patch:\n' + args.findings)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--tiers', help='alternate tiers.json')
    sub = p.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('delegate', help='route, run, check and escalate one task')
    d.add_argument('task')
    d.add_argument('--host', choices=['codex', 'claude'])
    d.add_argument('--rule', choices=sorted(ladder.RULES))
    d.add_argument('--repo', default='.')
    e = sub.add_parser('escalate', help='reject a reviewed patch and try the next rung')
    e.add_argument('run')
    e.add_argument('--findings', required=True)
    e.add_argument('--repo', default='.')
    args = p.parse_args(argv)
    result = delegate(args) if args.cmd == 'delegate' else escalate(args)
    print(json.dumps(result, indent=1))
    return 3 if result['status'] == 'escalate_to_coordinator' else 0


if __name__ == '__main__':
    sys.exit(main())
