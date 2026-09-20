---
name: ultra-delegation
description: Plan high-effort work while delegating bounded tasks to the lowest-cost proven model and thinking budget in the current agent host. Use for model routing, subagent delegation, controlled model/thinking/prompt bakeoffs, long-running coordinator context guardrails and handoffs, delegation quality or savings reports, Cortex-backed recommendations, and portable trust-but-verify learning imports.
---

# Ultra Delegation

Use this skill when delegation can improve cost, throughput, or reliability without giving up frontier ownership of the plan and integration.

## New project test drives

For the Jev v2 pilot, including Yarn consolidation, read [pilot.md](references/pilot.md) and use `scripts/pilot.py`. It provides one batched semantic routing request, broader discovered candidate pools, scoped independent outcome learning, and self-contained HTML/JSON telemetry. The generated [pilot question contract](references/pilot-questions.md) is the source of exact question wording. Security assessment is optional and advisory, off by default; an unavailable evaluator must not block recording an otherwise independently assessed result.

Pilot policy and evidence are separate from the legacy helper below. In the pilot, prompt wording versions are audit metadata; a material prompt contract or tool-policy change separates capability evidence. Use effective routes, perform `recheck`, and execute through the native host. Trials are proposals until the coordinator has an authorized isolated execution plan. Keep comparisons scoped, and do not turn synthetic demos or Jev shadow scores into observed worker quality.

## Host boundary

Stay in the current host and provider family. In Codex, use only Codex-native subagents and supported OpenAI model and effort controls. Do not invoke OpenCode, Claude Code, Ollama, another CLI, or a worker provider API as a fallback. The separately enabled Jev decision adapter may evaluate permitted packets; it cannot execute workers or widen provider scope.

In Claude Code or OpenCode, use that host's native workers instead. Read the relevant section of [hosts.md](references/hosts.md); templates are not proof of compatibility. The helper performs bookkeeping, not execution. Unexercised combinations are experimental.

Before selecting a worker, load `.ultra-delegation/policy.json` if it exists. Default to current host/current provider, external adapters disabled, and explicit Phase 2 approval for provider crossing.

Treat unavailable or external candidates as ineligible. State the mismatch and offer eligible host-native choices. Never silently substitute an external runtime.

## Local hardware is opt-in, not a free route

Apply `local_execution.mode` (default `disabled`, including older policies), exact `excluded_models`, and optional `allowed_models` before cost or evidence. A task-specific explicit opt-in does not persist; persisting policy requires an explicit user request. Model exclusions always win. Ordinary delegation approval is not local-hardware approval. An endpoint with unknown execution location is ineligible.

This beta has no verified local execution adapter: even an otherwise passing preflight must not launch a local model. Use an eligible remote native route or retain the task. Never download models, start servers, kill unrelated processes, or modify machine-wide settings.

Future local dispatch must enforce fresh memory-pressure/headroom observations, a runtime estimate including weights and cache, unified-memory accounting, a cross-project user lease, bounded context/output, timeout, monitoring, and owned-request cancellation. The supplied resource module tests this contract; it does not supervise a runtime. Limits are safeguards, not guarantees against overload.

## Protect coordinator context

Evaluate context risk when delegation starts, before and after worker activity, at material milestones, and after a host-reported compaction. Use host-reported telemetry only; never read private host session logs or estimate tokens from attachments.

At high risk, checkpoint before further delegation. At critical risk, finish only the current atomic action, launch no workers or follow-ups, request at most one terse status from active workers, and prepare a sanitized handoff for a fresh task. Do not create, archive, or delete a task automatically.

When telemetry is unavailable, mark it unavailable and checkpoint at material milestones or after the policy's unattended fallback. Task age and attachment counts alone never justify a hard stop.

Keep worker responses concise: summary, affected paths, validation result, and recommendation. Reference large logs, diffs, screenshots, and generated outputs by local artifact path or hash instead of copying them into coordinator messages, later packets, reports, or Cortex.

Read [orchestration.md](references/orchestration.md) before evaluating context risk or writing a handoff. Use the helper's `guard evaluate` and `guard checkpoint` commands for deterministic decisions and artifacts.

## Own the high-leverage work

Keep these with the frontier coordinator unless the user explicitly changes the boundary:

- Architecture, cross-cutting design, integration, and final verification.
- Security-sensitive, destructive, externally consequential, or tightly coupled work.
- Tasks whose acceptance criteria cannot be made independently testable.

Delegate only a bounded task packet with an explicit goal, scope, baseline, acceptance gates, validation commands, and output format. Use separate isolated proposals or worktrees when candidate outputs could conflict.

For routine work, pass minimal context rather than conversation history. Cache capability discovery within the session, invalidating it on host/model configuration changes or rejected settings. Use one worker, one bounded result, and at most one repair attempt before coordinator escalation. Run bakeoffs only when requested or when evidence is missing, stale, or conflicting. Load references only for the current operation.

## Legacy helper: route each packet

Classify the packet by task family, language/framework, operation, risk, coupling, tools, validation method, and affected paths. Use this exact profile identity:

`task family + provider/model revision + host/runtime + normalized/native thinking setting + prompt-profile version + tool-policy version`

Select in this order:

1. Current-turn user model or budget choice.
2. Project pins and exclusions.
3. Current host/provider eligibility.
4. Locally proven or locally verified profiles.
5. Compatible imported priors.
6. A controlled host-native experiment.
7. Frontier fallback.

Choose the lowest-cost eligible profile that passes the quality floor. Do not infer that success transfers between languages, task families, prompts, tools, or reasoning settings.

Read [orchestration.md](references/orchestration.md) before creating packets, running an experiment, scoring results, or producing a report.

## Legacy helper: optional Jev decisions

When project policy enables Jev, read [jev.md](references/jev.md) at packet-routing or result-evaluation boundaries. Use the separate `scripts/jev.py` adapter; the ordinary helper remains offline. Credentials are read-only: use the user’s existing OS credential entry or `TYPESAFE_API_KEY`. Never create, update, delete, migrate, or prompt for a credential. Configure only the non-secret service/account locator when needed.

Prepare bounded summaries and exact discovered profiles with sanitized evidence. Honor sharing permissions independently: routing summaries do not authorize sending code or outputs to the shadow judge. Preview a new packet shape with `--dry-run`. In active mode, consume only effective `action` and exact profile IDs; experiment nominations require the existing experiment protocol. Shadow recommendations and judge scores do not authorize dispatch or establish capability evidence.

The generated [question contract](references/jev-questions.md) shows exactly what Jev is asked and how code consumes each answer. Use the [shortlist workflow](references/shortlist.md) to combine shipped discovery seeds with validated local outcomes; seeds are unproven until independently exercised. Use the [benchmark workflow](references/jev-benchmark.md) for downstream assessment, threshold evaluation, and standard JSON/Markdown reports. Freeze rubric and calibration/test splits before reviewing outputs; only independent observed worker outcomes establish quality. Keep synthetic reports visibly labeled and leave unmeasured savings unavailable.

Save routing decisions with `--write`, refresh host discovery/evidence, and run `recheck` immediately before dispatch. If inputs changed, reevaluate. Imported routes still require first-use verification. On uncertainty or service failure, retain coordinator ownership and consult the original ranking. Jev never changes the context guard, host permissions, worker acceptance, or promotion.

## Legacy helper: test one variable at a time

Compare exactly one of model, thinking budget, or prompt profile per experiment. Hold the task packet, baseline, tool policy, validation, and evaluator constant. Ask for explicit approval before a factorial experiment.

Record both a normalized thinking level (`off`, `low`, `medium`, `high`, `xhigh`, `max`, or `custom`) and the exact native host setting. Do not equate similarly named settings across providers.

Notification-only experiments may use at most three candidates on one low-risk, independently verifiable, read-only or patch-proposal task at medium worker effort or less. Require approval for worktrees, high effort, external effects, more candidates, or provider crossing.

Define gates and a rubric before reading candidate outputs. Run deterministic checks first and blind worker identity and cost during frontier qualitative review. Use the project quality floor, defaulting to 80/100 with every mandatory gate passing.

Read [host-native.md](references/host-native.md) when choosing a host-native delegation mechanism or reporting an unavailable capability.

## Learn without leaking project content

When Cortex is available, query and spread from the task context before routing; record outcomes and reinforce only the exact task-specific profile. Otherwise append sanitized evidence to `.ultra-delegation/evidence.jsonl`.

Record only metadata and aggregates: profile identity, generalized task signature, gates, quality, acceptance, latency, available usage/cost, prompt hash, tool-policy version, evidence count, confidence, and freshness. Never persist source code, secrets, full prompts, raw candidate outputs, or reasoning traces.

Read [measurement-and-portability.md](references/measurement-and-portability.md) before recording metrics, promoting routes, generating reports, or importing/exporting learning.

Use `scripts/ultra_delegation.py` for deterministic policy validation, IDs, ranking, experiment scoring, JSON fallback evidence, reports, catalogs, exports/imports, and managed isolation directories. Read [cli.md](references/cli.md) before invoking it. The helper never launches models or provider APIs.

## Report the value honestly

For every material delegation, give an inline summary: selected profile, why it was eligible, quality/gates, available cost and performance, and recommendation outcome. Persist Markdown and JSON reports for bakeoffs, significant delegations, and requested summaries under `.ultra-delegation/reports/`.

Mark every cost, saving, and performance figure `measured`, `estimated`, or `unavailable`. Keep selected cost, comparator cost, experiment overhead, realized savings, projected savings, and break-even separate. Never describe projected savings from a bakeoff as savings already realized.

## Portable learning: trust, then verify

Read sanitized global catalog entries automatically unless policy disables it; write to `${ULTRA_DELEGATION_HOME:-~/.ultra-delegation}/catalog.jsonl` only after explicit promotion. Exchange portable `ultra-delegation-learning-v1.json` bundles, never raw evidence.

Use a compatible, fresh, high-confidence imported learning as a route for its first local use, but mark it `imported-prior-pending-verification`. Apply local gates and frontier review. Promote to `locally-verified` only after strong local confirmation; compare one eligible host-native alternative if validation is subjective or weak. On failure, quarantine it for this environment, record the contradiction, and trigger a bakeoff.

Do not let imported evidence override a current-turn choice, project pin, or stronger local evidence.
