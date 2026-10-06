"""Launch one headless worker in an isolated checkout, check it, and measure it.

Python 3.10+, standard library only. The helper owns the launch, so tokens and
cost come straight from the host CLI's own output.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

INFRA_MARKERS = ('at capacity', 'rate limit', 'rate_limit', '429', 'overloaded', '529',
                 'connection', 'network error', 'temporarily unavailable', 'internal server error')
CODEX_OFF = ('hooks', 'multi_agent', 'apps', 'plugins', 'browser_use', 'computer_use', 'image_generation')
CLAUDE_TOOLS = 'Bash,Read,Edit,Write,Glob,Grep'


def cache_env(root):
    """Toolchain caches inside `root`, so sandboxed workers and checks can build (calibration)."""
    root = Path(root)
    return {'GOCACHE': str(root / 'go-build'), 'GOMODCACHE': str(root / 'go-mod'), 'GOFLAGS': '-modcacherw',
            'CARGO_TARGET_DIR': str(root / 'cargo-target')}


def git(cwd, *args, env=None):
    p = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, env=env)
    if p.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def base_commit(repo):
    """Snapshot the working tree, untracked files included, as a commit.

    Uses a throwaway index, so the user's index, stash list and branches are untouched.
    """
    head = git(repo, 'rev-parse', 'HEAD').strip()
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / 'index'))
        git(repo, 'read-tree', head, env=env)
        git(repo, 'add', '-A', env=env)
        tree = git(repo, 'write-tree', env=env).strip()
    if tree == git(repo, 'rev-parse', head + '^{tree}').strip():
        return head
    return git(repo, '-c', 'user.name=ud', '-c', 'user.email=ud@localhost',
               'commit-tree', tree, '-p', head, '-m', 'ud base').strip()


def worker_prompt(task, findings=None):
    lines = ['You are a worker on one bounded task in this repository checkout.',
             '', 'Goal:', task['goal'], '', 'Acceptance criteria:']
    lines += ['- ' + a for a in task['acceptance']]
    if task.get('files'):
        lines += ['', 'Files in scope: ' + ', '.join(task['files'])]
    if task.get('context'):
        lines += ['', 'Context:', task['context'] if isinstance(task['context'], str) else json.dumps(task['context'])]
    if task.get('check'):
        lines += ['', f"Verify with `{task['check']}` before finishing; it must pass. Do not edit the test files it runs."]
    if findings:
        lines += ['', 'A previous attempt by another worker failed. Its findings:', findings[-6000:]]
    lines += ['', 'Rules: change only what the task needs. No network access. Do not delegate or start other agents.',
              'Finish with a two-line summary of what you changed.']
    return '\n'.join(lines)


def codex_cmd(rung, workdir, out):
    cmd = ['codex', 'exec', '--json', '--ephemeral', '--ignore-user-config', '--ignore-rules',
           '--skip-git-repo-check', '-m', rung['model'], '-s', 'workspace-write', '-C', str(workdir),
           '-o', str(out / 'last.txt'), '-c', 'approval_policy="never"']
    for feature in CODEX_OFF:
        cmd += ['--disable', feature]
    if rung.get('effort'):
        cmd += ['-c', f'model_reasoning_effort="{rung["effort"]}"']
    return cmd + ['-']


def claude_cmd(rung, workdir, out, clean=False):
    settings = {'sandbox': {'enabled': True, 'autoAllowBashIfSandboxed': True}, 'disableAllHooks': True}
    cmd = ['claude', '-p', '--strict-mcp-config', '--model', rung['model'], '--output-format', 'stream-json',
           '--verbose', '--permission-mode', 'acceptEdits', '--no-session-persistence', '--max-turns', '200',
           '--tools', CLAUDE_TOOLS, '--settings', json.dumps(settings)]
    if rung.get('effort'):
        cmd += ['--effort', rung['effort']]
    if clean:  # calibration: no CLAUDE.md, skills or plugins
        cmd.append('--safe-mode')
    return cmd


def parse_codex(events, out):
    usage = {'input': 0, 'cached_input': 0, 'cache_write': 0, 'output': 0, 'reasoning': 0}
    completed, errors = False, []
    for e in events:
        if e.get('type') == 'turn.completed':
            completed = True
            u = e.get('usage') or {}
            usage['input'] += u.get('input_tokens', 0)
            usage['cached_input'] += u.get('cached_input_tokens', 0)
            usage['cache_write'] += u.get('cache_write_input_tokens', 0)
            usage['output'] += u.get('output_tokens', 0)
            usage['reasoning'] += u.get('reasoning_output_tokens', 0)
        elif e.get('type') in ('error', 'turn.failed'):
            errors.append(str(e.get('message') or e.get('error', {}).get('message', '')))
    last = out / 'last.txt'
    text = last.read_text(errors='replace') if last.exists() else ''
    return completed, usage, None, text, '; '.join(errors)


def parse_claude(events):
    result = next((e for e in reversed(events) if e.get('type') == 'result'), None)
    if not result:
        return False, None, None, '', 'no result event'
    u = result.get('usage') or {}
    usage = {'input': u.get('input_tokens', 0) + u.get('cache_read_input_tokens', 0) + u.get('cache_creation_input_tokens', 0),
             'cached_input': u.get('cache_read_input_tokens', 0), 'cache_write': u.get('cache_creation_input_tokens', 0),
             'output': u.get('output_tokens', 0), 'reasoning': (u.get('output_tokens_details') or {}).get('thinking_tokens', 0)}
    ok = result.get('subtype') == 'success' and not result.get('is_error')
    return ok, usage, result.get('total_cost_usd'), str(result.get('result') or ''), '' if ok else str(result.get('subtype'))


def price(rung, usage, reported=None):
    """API-equivalent USD. Input counts include cached and cache-write tokens; output includes reasoning."""
    if reported is not None:
        return round(reported, 6)
    if not usage or not rung.get('price'):
        return None
    p = rung['price']
    fresh = usage['input'] - usage['cached_input'] - usage['cache_write']
    cost = (fresh * p['input'] + usage['cached_input'] * p.get('cached_input', p['input'])
            + usage['cache_write'] * p.get('cache_write', p['input']) + usage['output'] * p['output'])
    return round(cost / 1e6, 6)


def launch(rung, prompt, workdir, out, timeout, wrap=(), clean=False, env=None):
    """Run one worker to completion. Status: completed, failed, timeout or infra_error."""
    out.mkdir(parents=True, exist_ok=True)
    cmd = codex_cmd(rung, workdir, out) if rung['launcher'] == 'codex' else claude_cmd(rung, workdir, out, clean)
    started = time.time()
    with open(out / 'events.jsonl', 'w') as stdout, open(out / 'stderr.txt', 'w') as stderr:
        proc = subprocess.Popen([*wrap, *cmd], cwd=workdir, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, text=True,
                                env=dict(os.environ, **(env or {})))
        try:
            proc.communicate(prompt, timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            timed_out = True
    seconds = round(time.time() - started, 2)
    events = []
    for line in (out / 'events.jsonl').read_text(errors='replace').splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    if rung['launcher'] == 'codex':
        ok, usage, reported, text, error = parse_codex(events, out)
    else:
        ok, usage, reported, text, error = parse_claude(events)
    if timed_out:
        status = 'timeout'
    elif ok:
        status = 'completed'
    else:
        blob = (error + ' ' + (out / 'stderr.txt').read_text(errors='replace')[-2000:]).lower()
        status = 'infra_error' if any(m in blob for m in INFRA_MARKERS) else 'failed'
    return {'status': status, 'error': error[:500], 'usage': usage, 'cost_usd': price(rung, usage, reported),
            'seconds': seconds, 'summary': text[-1500:]}


def check_sandbox(workdir):
    """macOS: confine check writes to the checkout and temp dirs. Elsewhere: no wrapper."""
    if sys.platform != 'darwin' or not Path('/usr/bin/sandbox-exec').exists():
        return ()
    home = Path.home()
    caches = [home / 'Library' / 'Caches', home / '.cache', home / 'go', home / '.cargo', home / '.npm']
    allowed = [Path(workdir).resolve(), Path(tempfile.gettempdir()).resolve(), Path('/private/tmp'), Path('/dev'), *caches]
    rules = ''.join(f'(allow file-write* (subpath {json.dumps(str(p))}))' for p in allowed)
    return ('/usr/bin/sandbox-exec', '-p', '(version 1)(allow default)(deny file-write*)' + rules)


def run_check(task, workdir, base, timeout, env=None):
    for f in task.get('check_files', []):  # the worker may not grade itself by editing the test
        try:
            git(workdir, 'checkout', base, '--', f)
        except RuntimeError:
            pass
    try:
        p = subprocess.run([*check_sandbox(workdir), '/bin/sh', '-c', task['check']], cwd=workdir,
                           capture_output=True, text=True, timeout=timeout, env=dict(os.environ, **(env or {})))
        output, passed = (p.stdout + p.stderr)[-4000:], p.returncode == 0
    except subprocess.TimeoutExpired:
        output, passed = f'check timed out after {timeout}s', False
    return passed, output


def attempt(repo, base, rung, task, out, cfg, findings=None, wrap=(), clean=False, after=None, env=None):
    """One worker attempt on a fresh checkout of `base`. `after(workdir)` may add fields (calibration)."""
    root = Path(tempfile.gettempdir()) / 'ud'
    root.mkdir(exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix=rung['id'] + '-', dir=root))
    shutil.rmtree(workdir)
    git(repo, 'worktree', 'add', '--detach', str(workdir), base)
    try:
        result = launch(rung, worker_prompt(task, findings), workdir, out, cfg['worker_timeout_seconds'], wrap, clean, env)
        result.update(rung=rung['id'], model=rung['model'], effort=rung.get('effort'), passed=None, check_output='')
        if result['status'] == 'completed' and task.get('check'):
            result['passed'], result['check_output'] = run_check(task, workdir, base, cfg['check_timeout_seconds'], env)
        elif result['status'] != 'completed':
            result['passed'] = False
        git(workdir, 'add', '-A')
        patch = git(workdir, 'diff', '--cached', '--binary', base)
        (out / 'patch.diff').write_text(patch)
        result.update(patch=str(out / 'patch.diff'), patch_bytes=len(patch))
        if after:
            result.update(after(workdir))
        return result
    finally:
        subprocess.run(['git', 'worktree', 'remove', '--force', str(workdir)], cwd=repo, capture_output=True)
        shutil.rmtree(workdir, ignore_errors=True)
