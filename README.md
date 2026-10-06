# Ultra Delegation

Delegate bounded coding tasks to the cheapest worker model that can do them. Jev
(TypeSafe's decision model) picks the starting rung in one cheap request. The task's
own check verifies the result, a failure escalates one rung, and the coordinator
does the work itself only after every worker rung fails.

```sh
python3 .agents/skills/ultra-delegation/scripts/ud.py delegate task.json --host codex
```

- **One command for the coordinator.** It routes, launches a headless worker
  (`codex exec` or `claude -p`) in a temporary checkout, runs the check, escalates,
  and prints a patch to apply.
- **Never blocks.** Jev errors or missing credentials fall back to cheapest-first.
- **Measured cost.** Tokens and cost come from each worker CLI's own output.

Read [SKILL.md](.agents/skills/ultra-delegation/SKILL.md) for usage, and
[docs/jev-ladder.md](docs/jev-ladder.md) for the design, calibration plan and results.

**Status: 3.0 development.** The routing rule and cutoff are not yet calibrated, and
no savings claim is made. Earlier designs are archived in `legacy/` and older `docs/`
files; they are historical and not instructions.

Python 3.10+, standard library only. Run `python3 -m unittest discover -s tests -v`
and `python3 scripts/build_release.py --check`. MIT licensed.
