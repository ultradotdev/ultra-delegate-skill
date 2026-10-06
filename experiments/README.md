# Calibration experiments (not packaged)

These tools build the ground-truth table and replay routing rules against it. They
run only when someone deliberately starts them; ordinary `ud delegate` use never
triggers them.

Workers run under their host's own sandbox, in a fresh repository outside this
checkout. Each run's logs are then scanned for any reference to a checkout of this
repository, the fixtures tree, or a hidden test file name. Flagged runs are reported
and excluded from analysis. This is detection, not prevention: Codex's sandbox
cannot run inside another sandbox, and the maintainer chose detection over turning it off.

- `fx.py`: fixture loader, materializer, evaluator and validator. Run `python3 experiments/fx.py validate`.
- `calibrate.py`: runs rungs on fixtures. *(M3/M4)*
- `replay.py`: replays routing rules against the matrix. *(M5)*

## Fixture format

Each fixture lives in `fixtures/<id>/`:

```
fixture.json   id, language, band, summary, goal, files, public_check,
               public_check_files, hidden_check, timeout
starter/       the repository the worker gets: SPEC.md, source, public tests
hidden/        hidden tests; copied over the finished tree at evaluation time only
reference/     overlay files that make the starter correct
```

`fixtures/python-ranges` is the template.

### Fixture rules

1. **Numbered requirements.** SPEC.md states every requirement as a numbered line (`R1.`, `R2.`, ...). The spec alone must be enough to build a correct solution, with no hidden expectations.
2. **Tagged hidden tests.** Each hidden test names the requirement it checks (`test_R7_...`, or an `R7` comment), and every requirement has at least one hidden test. The validator enforces both.
3. **Public check.** The public check is visible to the worker and covers the obvious requirements, roughly a third to a half. The hidden check covers all of them.
4. **Starter state.** The starter fails both checks; starter plus reference passes both.
5. **Self-contained.** No network or third-party packages:
   - Python: standard library and `unittest`.
   - TypeScript: Node 24 with native type stripping, plus `node:test` and `node:assert/strict`, no npm packages, run with `node --test`.
   - Go: standard library, `go test`.
   - Rust: no dependencies, `cargo test --offline`.

   Checks finish in well under 60 s and are deterministic: no wall-clock or random dependence, no sleeps over 50 ms.
6. **No name collisions.** Hidden files must not overwrite starter files. Use names like `test_hidden.py`, `hidden.test.ts`, `hidden_test.go` (inside the package directory, mirrored under `hidden/`), or `tests/hidden.rs`.

### Difficulty bands

- **easy:** one small function with a clear bug; about 2–10 requirements.
- **medium:** one or two files with several interacting rules or edge cases; about 8–15 requirements.
- **hard:** a small multi-file project (300–1500 lines in the starter) with bugs that cross modules, or a feature that touches several of them; 15–30 requirements.

Hard fixtures should be hard because the pieces interact, not because of trivia. Examples of what to test:
- state that must stay consistent across modules
- an invariant one module assumes and another breaks
- ordering, rounding or error-propagation rules stated in the spec

A strong model should usually pass. A cheap model should plausibly miss a requirement it never tested.
