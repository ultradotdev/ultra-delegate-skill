---
name: ultra-delegation
description: Delegate a bounded coding task to the cheapest worker model Jev says can do it, run the task's check, and escalate to a stronger worker on failure. Use when the user invokes Ultra Delegation or asks to delegate or route work to cheaper models.
---

# Ultra Delegation

One command does the delegation. `ud.py delegate` asks Jev which rung to start on, runs a headless worker in a temporary checkout, runs your check, and escalates up the ladder on failure. You review and apply the patch. If every rung fails, you do the task yourself.

## When to delegate

- **Delegate** bounded, verifiable work: a bug fix, a function, tests for a module, a refactor of named files. It works best with a check command that proves the result.
- **Keep** trivial edits (faster to do than to describe), decisions that depend on this conversation, integration across many areas, and anything the user wants you to do yourself.

## 1. Write task.json (outside the repo, e.g. in a temp dir)

```json
{
  "goal": "Fix parse_counts so quoted commas and CRLF input are handled",
  "acceptance": ["Every rule in the contract below holds", "Only src/parser.py changes"],
  "files": ["src/parser.py"],
  "check": "python3 -m pytest tests/test_parser.py -q",
  "check_files": ["tests/test_parser.py"],
  "context": "Contract, interfaces and decisions the worker needs"
}
```

- `goal` and `acceptance` are required. The worker sees only this file and the repository, so state every requirement.
- `check` must exit 0 only when the task is done. Without a check, the result comes back to you for review.
- `check_files` are restored before checking, so a worker cannot pass by editing the tests.
- The worker starts from your current tree, uncommitted changes included.

## 2. Run it

`ud.py` is in `scripts/` beside this SKILL.md; use that absolute path.

```sh
python3 /abs/path/to/ultra-delegation/scripts/ud.py delegate /tmp/task.json --host codex   # or --host claude
```

It launches worker CLIs and calls Jev over the network, and a run takes a few minutes per rung.
- **Codex:** if the sandbox blocks it, request escalated permissions. A prefix rule for that `python3 .../ud.py` command avoids repeat prompts.
- **Claude Code:** run it in Bash with a long timeout or in the background.

## 3. Act on the result

The command prints JSON. The fields to read:
- `status`
- `rung`
- `apply`, the command that applies the patch
- `attempts`, with per-worker cost and seconds
- `route`, Jev's answers

What to do for each `status`:
- **`passed`:** read the patch, apply it with `git apply --3way <patch>`, and run your own checks before reporting done.
- **`needs_review`:** review the patch. If it is wrong, run `ud.py escalate <run> --findings "what is wrong"`, which tries the next rung.
- **`escalate_to_coordinator`** (exit code 3): every worker rung failed. Do the task yourself using `findings`. The hand-off is already logged.

## Rules

- Never weaken acceptance or the check to make a worker pass.
- Jev outages and missing credentials fall back to cheapest-first automatically. Report the `route` field; nothing else to do.
- Cost is measured per worker from the host CLI's own output (`null` when unknown). Do not claim savings from a single run.
- Jev receives the goal, acceptance, context and the contents of `files`. Set `"share_code": false` in `assets/tiers.json` to send file names only.
- Credentials are read-only: `TYPESAFE_API_KEY`, or an existing macOS Keychain entry. Its service and account default to `typesafe-api-key` and `$USER`. Override them with environment variables or `~/.config/ultra-delegation/config.json`, never in a repository. Never create or change a credential.

## Ladders

`assets/tiers.json` defines the rungs, dated prices and the rule:
- **Codex:** luna-medium → luna-high → sol-medium
- **Claude:** haiku → sonnet-medium → opus-medium
- **Default rule:** `jev_noul`, which picks the cheapest rung Jev rates at or above the cutoff.

Outcomes are logged in `~/.local/state/ultra-delegation/` (override with `UD_STATE`). A coarse per-rung record from verified outcomes feeds back into Jev's next decision.
