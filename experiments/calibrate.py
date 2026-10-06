#!/usr/bin/env python3
"""Run worker rungs on fixtures and record a ground-truth outcome per cell.

Only run deliberately; every cell is a paid model run. Results resume by cell.

  calibrate.py jev    --host codex [--repeat 3] [--fixtures ...]      # cold Jev answers (cheap)
  calibrate.py probe  --host codex --max-usd 10 [--fixtures ...]      # cheapest + top worker rung, 1 run
  calibrate.py matrix --host codex --max-usd 60 [--runs 2] [--rungs ...] [--fixtures ...]
  calibrate.py summary --host codex

Workers run in a fresh repo outside this checkout under their host's own sandbox.
Afterwards each run's logs are scanned for any reference to a checkout of this
repository or a hidden test file; such cells are flagged and excluded from
analysis. Public pass drives escalation in replay; hidden pass is the quality
score. Infrastructure errors retry once and are kept apart from model failures.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / '.agents/skills/ultra-delegation/scripts'))
import fx  # noqa: E402
import jev  # noqa: E402
import workers  # noqa: E402

CONFIG = json.loads((REPO / '.agents/skills/ultra-delegation/assets/tiers.json').read_text())
RESULTS = HERE / 'results'
RAW = Path.home() / '.local' / 'state' / 'ultra-delegation' / 'calibration'  # outside the protected checkout
BAND_ORDER = ('easy', 'medium', 'hard')


def protected_roots():
    """Every checkout of this repository; each one holds the hidden tests and references."""
    out = subprocess.run(['git', 'worktree', 'list', '--porcelain'], cwd=REPO, capture_output=True, text=True).stdout
    return sorted({line[len('worktree '):] for line in out.splitlines() if line.startswith('worktree ')} | {str(REPO)})


def leaks(f, out_dir):
    """Markers of a worker looking outside its checkout: repo paths, the fixtures tree, hidden test names."""
    markers = [*protected_roots(), 'experiments/fixtures',
               *sorted({p.name for p in (f['dir'] / 'hidden').rglob('*') if p.is_file()})]
    text = ''.join(p.read_text(errors='replace') for p in Path(out_dir).parent.glob(Path(out_dir).name + '*/*')
                   if p.is_file() and p.name != 'patch.diff')
    return sorted({m for m in markers if m in text})


def scrub(text):
    """Strip machine-specific paths before anything is written to results/ (which is committed)."""
    text = str(text or '')
    for path, label in ((str(RAW), '<raw>'), (tempfile.gettempdir(), '<tmp>'), ('/private/var/folders', '<tmp>'),
                        (str(Path.home()), '~')):
        text = text.replace(path, label)
    return text


def interleave(fixtures):
    """easy, medium, hard, easy, ... so a run stopped by the budget still covers every band."""
    by_band = {b: [f for f in fixtures if f['band'] == b] for b in BAND_ORDER}
    out = []
    while any(by_band.values()):
        for b in BAND_ORDER:
            if by_band[b]:
                out.append(by_band[b].pop(0))
    return out


def rungs_for(host, include_proxy=False):
    ladder = list(CONFIG['ladders'][host])
    return ladder + [CONFIG['coordinator_proxy'][host]] if include_proxy else ladder


def cells_path(host):
    RESULTS.mkdir(exist_ok=True)
    return RESULTS / f'{host}-cells.jsonl'


def load_cells(host):
    p = cells_path(host)
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()] if p.exists() else []


def run_cell(f, rung, host, run):
    """One worker run on one fixture; returns the cell record."""
    root = Path(tempfile.gettempdir()) / 'ud-cal' / uuid.uuid4().hex[:10]
    repo = fx.materialize(f, root / 'repo')
    out = RAW / host / f['id'] / rung['id'] / f'run{run}-{int(time.time())}'
    cfg = dict(CONFIG, worker_timeout_seconds=1800)
    after = lambda wd: dict(zip(('hidden_pass', 'hidden_output'), fx.evaluate(f, wd, 'hidden')))
    kw = dict(clean=(rung['launcher'] == 'claude'), after=after, env=workers.cache_env(root))
    r = workers.attempt(repo, workers.base_commit(repo), rung, fx.task(f), out, cfg, **kw)
    if r['status'] == 'infra_error':
        r = workers.attempt(repo, workers.base_commit(repo), rung, fx.task(f), out.with_name(out.name + '-retry'), cfg, **kw)
    return {'fixture': f['id'], 'band': f['band'], 'language': f['language'], 'host': host, 'rung': rung['id'],
            'model': rung['model'], 'effort': rung.get('effort'), 'run': run, 'status': r['status'],
            'public_pass': bool(r['passed']), 'hidden_pass': bool(r.get('hidden_pass')) if r['status'] == 'completed' else False,
            'cost_usd': r['cost_usd'], 'seconds': r['seconds'], 'usage': r['usage'], 'error': scrub(r.get('error')),
            'patch_bytes': r.get('patch_bytes'), 'raw': scrub(out), 'hidden_tail': scrub((r.get('hidden_output') or '')[-400:]),
            'leak': [scrub(m) for m in leaks(f, out)]}


def execute(host, plan, max_usd):
    """plan: list of (fixture, rungs, run) groups. Skips finished cells. Before each group,
    stops if its estimated cost (the priciest run seen so far per rung) would cross the cap."""
    done = {(c['fixture'], c['rung'], c['run']) for c in load_cells(host) if c['status'] != 'infra_error'}
    spent, priciest = 0.0, {}
    for f, rungs, run in plan:
        todo = [r for r in rungs if (f['id'], r['id'], run) not in done]
        estimate = sum(priciest.get(r['id'], 0) for r in todo)
        if todo and spent + estimate > max_usd:
            print(f"stopping before {f['id']}: spent ${spent:.2f}, next group estimated ${estimate:.2f}, cap ${max_usd:.2f}")
            break
        for rung in todo:
            cell = run_cell(f, rung, host, run)
            spent += cell['cost_usd'] or 0
            priciest[rung['id']] = max(priciest.get(rung['id'], 0), cell['cost_usd'] or 0)
            with open(cells_path(host), 'a') as out:
                out.write(json.dumps(cell) + '\n')
            print(f"{f['id']:<28} {rung['id']:<14} run{run} {cell['status']:<11} public={cell['public_pass']!s:<5} "
                  f"hidden={cell['hidden_pass']!s:<5} ${cell['cost_usd'] or 0:.4f} {cell['seconds']:.0f}s  total ${spent:.2f}"
                  + (f"  LEAK {cell['leak']}" if cell['leak'] else ''), flush=True)
    return spent


def jev_answers(host, fixtures, repeat):
    path = RESULTS / f'{host}-jev-cold.json'
    cache = json.loads(path.read_text()) if path.exists() else {}
    ladder = rungs_for(host)
    for f in fixtures:
        have = cache.setdefault(f['id'], [])
        while len(have) < repeat:
            r = jev.route(fx.task(f), ladder, {}, f['dir'] / 'starter', CONFIG.get('share_code', True))
            if r['route'] != 'jev':
                raise SystemExit(f"Jev failed on {f['id']}: {r.get('error')}")
            have.append(r)
            print(f"{f['id']:<28} difficulty={r['difficulty']:<5} passes={r['passes']} start={ladder[r['start']]['id']}")
    RESULTS.mkdir(exist_ok=True)
    path.write_text(json.dumps(cache, indent=1))
    return cache


def summary(host):
    cells = [c for c in load_cells(host) if c['status'] != 'infra_error']
    flagged = [c for c in cells if c.get('leak')]
    cells = [c for c in cells if not c.get('leak')]
    table = {}
    for c in cells:
        t = table.setdefault(c['fixture'], {}).setdefault(c['rung'], [])
        t.append(('H' if c['hidden_pass'] else ('p' if c['public_pass'] else '-')))
    rungs = [r['id'] for r in rungs_for(host, True)]
    print('fixture'.ljust(28) + ''.join(r[:13].ljust(14) for r in rungs))
    for fid in sorted(table):
        print(fid.ljust(28) + ''.join(''.join(table[fid].get(r, ['.'])).ljust(14) for r in rungs))
    spent = sum(c['cost_usd'] or 0 for c in load_cells(host))
    print(f'\nH = hidden pass, p = public pass only, - = fail, . = not run.  Spent ${spent:.2f} over {len(load_cells(host))} cells.')
    for c in flagged:
        print(f"excluded (looked outside its checkout): {c['fixture']} {c['rung']} run{c['run']}: {c['leak']}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('cmd', choices=['jev', 'probe', 'matrix', 'summary'])
    p.add_argument('--host', required=True, choices=sorted(CONFIG['ladders']))
    p.add_argument('--fixtures', nargs='*')
    p.add_argument('--rungs', nargs='*', help='rung ids (default: all worker rungs)')
    p.add_argument('--runs', type=int, default=2)
    p.add_argument('--repeat', type=int, default=1)
    p.add_argument('--max-usd', type=float, default=5.0)
    a = p.parse_args(argv)
    fixtures = [fx.load(i) for i in (a.fixtures or fx.all_ids())]
    if a.cmd == 'summary':
        return summary(a.host)
    if a.cmd == 'jev':
        return jev_answers(a.host, fixtures, a.repeat) and None
    ladder = rungs_for(a.host, include_proxy=True)
    by_id = {r['id']: r for r in ladder}
    if a.cmd == 'probe':
        chosen, runs = [ladder[0], ladder[-2]], 1
    else:
        chosen, runs = [by_id[r] for r in (a.rungs or [r['id'] for r in ladder[:-1]])], a.runs
    plan = [(f, chosen, n) for n in range(1, runs + 1) for f in interleave(fixtures)]
    execute(a.host, plan, a.max_usd)
    summary(a.host)


if __name__ == '__main__':
    main()
