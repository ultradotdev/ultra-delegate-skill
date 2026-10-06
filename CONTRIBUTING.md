# Contributing

The skill lives in `.agents/skills/ultra-delegation/`. Its scripts are `ud.py` (CLI),
`jev.py` (one batched request), `ladder.py` (decision rules) and `workers.py`
(launch, check, patch, measure). Keep the scripts under 900 lines and SKILL.md under
80 lines.

Ground rules:
- No new thresholds, gates or required fields that can stop a task.
- Unknown cost stays `null` and never blocks.
- Tests exercise routing, launching, checking or replay.

Run `python3 -m unittest discover -s tests -v` and
`python3 scripts/build_release.py --check` before submitting. Calibration code and
fixtures live in `experiments/` and are never packaged. `legacy/` is archival.
