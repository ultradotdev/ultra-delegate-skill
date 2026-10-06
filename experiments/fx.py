#!/usr/bin/env python3
"""Calibration fixtures: load, materialize, evaluate and validate. Never packaged.

Layout of experiments/fixtures/<id>/:
  fixture.json  id, language, band (easy|medium|hard), summary, goal, files,
                public_check, public_check_files, hidden_check, timeout
  starter/      the repository a worker receives, with SPEC.md and the public tests
  hidden/       hidden tests, copied over a finished tree only at evaluation time
  reference/    overlay files that turn the starter into a correct solution

SPEC.md numbers every requirement (R1., R2., ...). Every hidden test names the
requirement it checks (R<n>) and every requirement is covered by a hidden test,
so no hidden assertion can test something the spec does not state.

  python3 experiments/fx.py validate [ids...]
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'fixtures'
KEYS = {'id', 'language', 'band', 'summary', 'goal', 'files', 'public_check', 'public_check_files', 'hidden_check'}
REQ = re.compile(r'^\s*(?:[-*]\s*)?\**(R\d+)\**[.:)]', re.M)
TAG = re.compile(r'(?<![A-Za-z0-9])R\d+(?!\d)')


def load(fid):
    d = ROOT / fid
    f = json.loads((d / 'fixture.json').read_text())
    f['dir'] = d
    return f


def all_ids():
    return sorted(p.name for p in ROOT.iterdir() if (p / 'fixture.json').exists())


def task(f):
    """The task.json a coordinator would write for this fixture."""
    return {'goal': f['goal'],
            'acceptance': ['Every numbered requirement in SPEC.md holds',
                           f"`{f['public_check']}` passes", 'The public tests are not modified'],
            'files': f['files'], 'check': f['public_check'], 'check_files': f['public_check_files']}


def copy_tree(src, dest):
    shutil.copytree(src, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', 'node_modules', 'target'))


def materialize(f, dest):
    """A fresh git repository holding only the starter."""
    dest = Path(dest)
    copy_tree(f['dir'] / 'starter', dest)
    for cmd in (['init', '-q'], ['add', '-A'],
                ['-c', 'user.name=fixture', '-c', 'user.email=fixture@localhost', 'commit', '-qm', 'starter']):
        subprocess.run(['git', *cmd], cwd=dest, check=True, capture_output=True)
    return dest


def run(cmd, cwd, timeout):
    try:
        p = subprocess.run(['/bin/sh', '-c', cmd], cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode == 0, (p.stdout + p.stderr)[-3000:]
    except subprocess.TimeoutExpired:
        return False, f'timed out after {timeout}s'


def evaluate(f, tree, which='hidden'):
    """Run the public or hidden check on a copy of a finished tree."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / 'eval'
        copy_tree(tree, work)
        shutil.rmtree(work / '.git', ignore_errors=True)
        if which == 'hidden':
            copy_tree(f['dir'] / 'hidden', work)
        else:
            copy_tree(f['dir'] / 'starter', work / '.public')  # restore public tests the worker might have edited
            for rel in f['public_check_files']:
                shutil.copy2(work / '.public' / rel, work / rel)
            shutil.rmtree(work / '.public')
        return run(f[f'{which}_check'], work, f.get('timeout', 120))


def requirements(f):
    return REQ.findall((f['dir'] / 'starter' / 'SPEC.md').read_text())


def validate(fid):
    f, problems = load(fid), []
    missing = KEYS - set(f)
    if missing:
        return {'id': fid, 'ok': False, 'problems': [f'fixture.json missing {sorted(missing)}']}
    if f['band'] not in ('easy', 'medium', 'hard'):
        problems.append('band must be easy, medium or hard')
    for sub in ('starter', 'hidden', 'reference'):
        if not (f['dir'] / sub).is_dir():
            problems.append(f'missing {sub}/')
    if problems:
        return {'id': fid, 'ok': False, 'problems': problems}
    reqs = requirements(f)
    if not reqs or len(set(reqs)) != len(reqs):
        problems.append('SPEC.md needs uniquely numbered requirements (R1., R2., ...)')
    tags = set()
    for p in (f['dir'] / 'hidden').rglob('*'):
        if p.is_file():
            tags |= set(TAG.findall(p.read_text(errors='replace')))
    if tags - set(reqs):
        problems.append(f'hidden tests cite requirements not in SPEC.md: {sorted(tags - set(reqs))}')
    if set(reqs) - tags:
        problems.append(f'requirements with no hidden test: {sorted(set(reqs) - tags, key=lambda r: int(r[1:]))}')
    for rel in [*f['files'], *f['public_check_files']]:
        if not (f['dir'] / 'starter' / rel).exists():
            problems.append(f'{rel} is not in starter/')
    lines = sum(len(p.read_text(errors='replace').splitlines()) for p in (f['dir'] / 'starter').rglob('*') if p.is_file())
    with tempfile.TemporaryDirectory() as tmp:
        starter = materialize(f, Path(tmp) / 'starter')
        solved = Path(tmp) / 'solved'
        copy_tree(starter, solved)
        copy_tree(f['dir'] / 'reference', solved)
        result = {'starter_public': evaluate(f, starter, 'public')[0], 'starter_hidden': evaluate(f, starter, 'hidden')[0]}
        ok_pub, out_pub = evaluate(f, solved, 'public')
        ok_hid, out_hid = evaluate(f, solved, 'hidden')
        result.update(reference_public=ok_pub, reference_hidden=ok_hid)
    if result['starter_public']:
        problems.append('starter already passes the public check')
    if result['starter_hidden']:
        problems.append('starter already passes the hidden check')
    if not ok_pub:
        problems.append('reference fails the public check: ' + out_pub[-600:])
    if not ok_hid:
        problems.append('reference fails the hidden check: ' + out_hid[-600:])
    return {'id': fid, 'band': f['band'], 'language': f['language'], 'requirements': len(reqs),
            'starter_lines': lines, 'ok': not problems, 'problems': problems, **result}


def main(argv):
    if not argv or argv[0] != 'validate':
        raise SystemExit(__doc__)
    results = [validate(i) for i in (argv[1:] or all_ids())]
    for r in results:
        mark = 'ok ' if r['ok'] else 'BAD'
        print(f"{mark} {r['id']:<28} {r.get('band', ''):<7} {r.get('language', ''):<11} "
              f"reqs={r.get('requirements', 0):<3} lines={r.get('starter_lines', 0)}")
        for p in r['problems']:
            print('    - ' + p)
    return 0 if all(r['ok'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
