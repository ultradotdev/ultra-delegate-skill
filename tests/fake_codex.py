#!/usr/bin/env python3
"""Stand-in for `codex exec --json`. Behaviour is chosen by the -m model name."""
import json
import sys
from pathlib import Path

args = sys.argv[1:]
model, cwd, last = args[args.index('-m') + 1], Path(args[args.index('-C') + 1]), args[args.index('-o') + 1]
sys.stdin.read()


def emit(event):
    print(json.dumps(event), flush=True)


emit({'type': 'thread.started', 'thread_id': 'fake'})
emit({'type': 'turn.started'})
if model == 'fake-capacity':
    emit({'type': 'error', 'message': 'Selected model is at capacity. Please try a different model.'})
    emit({'type': 'turn.failed', 'error': {'message': 'Selected model is at capacity.'}})
    sys.exit(1)
if model == 'fake-good':
    (cwd / 'solution.py').write_text('def add(a, b):\n    return a + b\n')
elif model == 'fake-bad':
    (cwd / 'solution.py').write_text('def add(a, b):\n    return a - b\n')
elif model == 'fake-cheat':  # leaves the bug and rewrites the test to pass
    (cwd / 'check.py').write_text("print('ok')\n")
elif model == 'fake-newfile':
    (cwd / 'solution.py').write_text('from helper import plus as add\n')
    (cwd / 'helper.py').write_text('def plus(a, b):\n    return a + b\n')
Path(last).write_text(f'{model} finished')
emit({'type': 'turn.completed', 'usage': {'input_tokens': 1000, 'cached_input_tokens': 800,
                                          'cache_write_input_tokens': 0, 'output_tokens': 100,
                                          'reasoning_output_tokens': 20}})
