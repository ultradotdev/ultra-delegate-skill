# Yarn consolidation handoff

Consolidate the user-described GPT-6 and Fable 5.1 Yarn app versions into one
coherent app. Those labels identify source versions, not discoverable worker
models. Locate the actual branches, directories, or history before choosing a
consolidation path. Preserve unrelated edits and follow the repository's own
instructions.

The bundled Ultra Delegation pilot prepares bounded native work through
`runtime/ultra-delegation/scripts/pilot.py`. It does not execute a model, run
tests, make a worktree, merge a patch, or accept the product. The coordinator owns
architecture, integration, native tool calls, independent review, and release.

Read `PLAN.md`, then `RUNBOOK.md`. Begin with a concise inventory and behavior
matrix, select one small end-to-end slice, declare its acceptance contract, and
complete it when the repository inputs and authorization exist. Do not stop at a
plan where implementation is in scope.

## RC6 status

The bundled pilot routes an eligible worker immediately after project setup; it
does not wait for local qualification counts or a shadow rollout. The scoped live
routing check recorded 12/12 `clarify` responses with wording v4 and, on the
same task data after a two-question v5 wording revision, 11/12 `route` responses
plus one `no-suitable-candidate`. The bundled
[validation](../../docs/active-recovery-validation.md) and
[results](../../docs/active-recovery-results.json) record 11 accepted native
requests across 12 task cards: six primary successes, three comparison recoveries,
and two later recovery paths. They include eight native invocations and 23 task
attempts, one preserved coordinator misdispatch, and correlated batches. Security
and artifact judges were off and worker/review costs are unknown. These are not
Yarn trial results, independent worker-quality evidence, savings, or a promise of
delivery.

## Operating contract

- Python 3.10+ is the pilot runtime. A Rust rewrite is out of scope.
- Initialize a **fresh RC6 pilot ledger**. Do not copy or silently activate a
  previous release policy. Historical records remain reportable as history.
- `pilot init` defaults to active routing, but a live Jev request still requires
  both `--live` and explicit summary sharing. Artifact sharing, advisory security,
  and the optional judge are separate permissions.
- Discover exact current Codex models, efforts, capacities, and declared
  `read-files`/`edit-files`/`run-tests` tools. A tool declaration is not a sandbox.
- After routing, use the persisted workflow: plan → per-attempt recheck → native
  run record → artifact completion → independent outcome → reviewed event. One
  repair may follow a concrete review finding, then an eligible fallback.
- Preserve failed, rejected, incomplete, comparison, repair, and canceled
  attempts. A passing alternative completes the request; never auto-merge it.
- Credential lifecycle is user-controlled. Read an existing environment credential
  or configured store locator only; never create, modify, expose, or place a key
  in argv.

The local tests and simulated examples verify tooling behavior. They do not show a
real Yarn trial, live Jev quality, native-worker quality, security certification,
calibrated thresholds, or savings. Use the twelve prepared task cards as the first
real trial plan and record only actual observed results.
