# Jev Ladder: design and results

**Rule:** use the cheapest worker rung Jev says can do the job, check the result, and escalate one rung on failure. The coordinator does the task itself only after every worker rung fails.

**Proof plan:**
1. Run every rung on every synthetic fixture to build a ground-truth table.
2. Replay routing rules offline against that table.
3. Run a small live check against a solo coordinator.

Running every rung on every task happens only in deliberate calibration runs.

## Milestones

| # | Milestone | Status |
|---|---|---|
| M0 | Branch `jev-ladder`; Codex AGENTS.md carve-out | Done. Pushed as one scrubbed commit on main. |
| M1 | Worker launchers plus live smoke on both hosts | Done, 2026-10-04 |
| M2 | `ud delegate` end to end, including from inside a Codex coordinator | Done, 2026-10-04 |
| M3 | ~20 fixtures plus go/no-go probe | Done, 2026-10-05. $2.54 on Codex, $7.78 on Claude. The maintainer decides go/no-go and the matrix budget. |
| M4–M7 | Matrix, replay, live check, release | Not started |

## M1–M2 findings (2026-10-04)

All runs are on the `python-csv` fixture (CSV parsing with edge cases), one run each.

| Run | Rung | Visible check | Hidden check | Cost | Time |
|---|---|---|---|---:|---:|
| Codex smoke | gpt-6-luna / medium | pass | **fail** (5000-digit field) | $0.0039 | 29 s |
| Claude smoke | claude-haiku-4-5 | pass | **fail** | $0.125 | 53 s |
| `ud`, Jev route, Codex | luna-high (Jev start) | pass (full check visible) | — | $0.0080 | 88 s |
| `ud`, Jev down, Codex | luna-medium (fallback) | pass (full check visible) | — | $0.0042 | 43 s |
| `ud`, Jev route, Claude | sonnet-medium (Jev start) | pass | **fail** | $0.138 | 40 s |
| `ud` inside a Sol coordinator | luna-high | pass | — | worker $0.0067; coordinator $0.147 | 283 s total |

- **Accounting is complete.** With `approval_policy=never` on Codex, no auto-review calls run, so every token is reported. Claude reports `total_cost_usd` directly. The Sep 28 accounting blocker is gone.
- **Visible checks close the quality gap.** When the full check was visible, the cheapest Codex rung passed. When only a partial check was visible, every rung tried shipped the same subtle bug. Routing quality only matters where checks are partial, so fixtures need a public check plus hidden checks.
- **Coordinator overhead dominates small tasks.** The Sol coordinator spent about 22× the worker's cost on the reading, writing, applying and verifying around one `ud` call. Delegation can only pay off on tasks large enough that a solo coordinator would spend many turns. The live check must use tasks of that size.
- **Jev's answers are informative but not monotone.** On Codex, the pass probability was 0.28 for Luna-medium, 0.57 for Luna-high and 0.46 for Sol. Its "cheapest rung" choice still favoured Luna-medium at 0.70. A call costs about $0.00006 and takes 0.12 s. Calibration will decide which signal to trust.
- **Rung prices.** Codex rungs are about 20× apart per token; Claude rungs are 2× apart (Haiku $1, Sonnet 5.5 $2, Opus 5.5 $4 per million input tokens). Routing should matter more for wall time on Codex and more for dollars on Claude.
- **Global context reaches every worker.** About 8k tokens per Codex call come from the global `~/.codex/AGENTS.md` and the installed skill list, roughly half of each call's input. No CLI flag removes them. A scratch `CODEX_HOME` would, but it means linking the auth file, so that waits on the maintainer's call.
- **Infrastructure errors happen.** "Selected model is at capacity" appeared once. `ud` retries once and never counts it as a quality failure.

## M3 so far (2026-10-04)

**20 fixtures validated.** For each, the starter fails both checks and the reference passes both. Every hidden test cites a numbered SPEC requirement.

| Band | Count | Starter lines | Requirements | Languages |
|---|---:|---|---|---|
| easy | 4 | 35–48 | 5–8 | Python, TypeScript |
| medium | 8 | 33–201 | 9–14 | Python, TypeScript, Go |
| hard | 8 | 332–690 | 19–27 | Python, TypeScript, Go, Rust |

The fixture authors checked discrimination by simulating "fix only what the public test shows". In 22 of 23 planted single mistakes on medium fixtures, and on all eight hard fixtures, that fix passes the public check and fails the hidden one.

**Cold Jev answers.** One call per fixture per host costs $0.004 per host, with requests up to 20 KB. Three repeats on five fixtures differed by about ±0.03. Mean `pass_<rung>` answers by band:

| Band | Codex: luna-med / luna-high / sol-med | Claude: haiku / sonnet / opus |
|---|---|---|
| easy | 0.37 / 0.66 / 0.63 | 0.25 / 0.63 / 0.74 |
| medium | 0.24 / 0.53 / 0.49 | 0.14 / 0.47 / 0.62 |
| hard | 0.20 / 0.34 / 0.33 | 0.14 / 0.33 / 0.42 |

- **The pass answers track difficulty**, and are ordered by capability on Claude.
- **On Codex, Jev rates luna-high at or above sol-medium.** The likely cause is the rung cards: both mention price, and luna-high's says it "thinks longer". As things stand, `jev_noul` would never start on Sol. A candidate fix for after the probe: cards that describe capability only.
- **The `start` Choice picks the cheapest rung almost every time** (39 of 40), so it carries no routing signal.
- **Answers are compressed** and never exceed 0.77, so a 0.5 cutoff is arbitrary. Replay tunes it leave-one-out.

**Calibration isolation.** Codex's own sandbox cannot start inside a sandbox-exec wrapper. The maintainer chose to keep each host's own sandbox on and check afterwards. Every run's logs are scanned for references to a checkout of this repo, the fixtures tree or a hidden test name; flagged runs are excluded.

## M3 go/no-go probe (2026-10-05)

Each fixture was run once on the cheapest rung and once on the top worker rung. Escalation follows the public check; correctness is the hidden check. The leak scan flagged 0 of 80 runs, and there were no infrastructure errors.

| | Codex: luna-medium / sol-medium | Claude: haiku / opus-medium |
|---|---|---|
| Hidden-check pass | 16/20 / 20/20 | 7/20 / 19/20 |
| Cheap rung fails hidden, top passes | 4/20 (target ≥ 1/3) | 12/20 |
| Cheap rung passes public but fails hidden (silent bad result) | 4 | 12 |
| Mean cost per run | $0.0044 / $0.122 | $0.166 / $0.238 |
| Jev pass answers vs hidden outcome, AUC (all runs; cheap rung only) | 0.88; 0.73 | 0.92; 0.85 |
| Spend | $2.54 | $7.78 |

Two-rung rules from these runs:

| Rule | Codex cost / correct / silent bad | Claude cost / correct / silent bad |
|---|---|---|
| Cheapest first, escalate on public failure | $0.09 / 16 / 4 | $3.31 / 8 / 12 |
| Always top rung | $2.45 / 20 / 0 | $4.76 / 19 / 1 |
| Jev: top rung when cheap pass < 0.25 (Codex) or < 0.30 (Claude) | $1.78 / 20 / 0 | $4.76 / 19 / 1 |
| Oracle | $0.83 / 20 / 0 | $4.66 / 19 / 1 |

### What this shows

- **Codex.** Luna is very good: it passed 16 of 20 for about 1/28 of Sol's price. All four misses were hard multi-module fixtures, and all four passed the public check, so cheapest-first ships them silently. Jev's cheap-rung answers separate hard from easy (AUC 0.73) but not which hard tasks Luna will miss (0.44 within hard). A Jev threshold reaches full quality for 27% less than always-Sol. Perfect routing would cost 66% less.
- **Claude.** Haiku is dominated. It got 7 of 20 right and was slower, and Opus cost only 44% more in total. Per correct result, Opus is cheaper than Haiku. Routing between Haiku and Opus adds almost nothing over always-Opus. The useful Claude question is Sonnet against Opus, which the probe did not run.
- **The headline AUC is inflated** because it pools rungs. Judge Jev on within-rung discrimination.
- **One run per cell.** Luna's `python-csv` hidden result flipped between yesterday's smoke run and this probe. The matrix needs two runs per cell.
