# Orchestration Protocol

## Context lifecycle preflight

Run `guard evaluate` when Ultra Delegation starts, before creating a worker, after receiving a worker result, at a material milestone, and after a host-reported compaction. A material milestone is an accepted worker batch, evaluated bakeoff, integrated feature phase, or completed validation suite.

Use only telemetry the host supplies. Classify context utilization as healthy below 70%, elevated at 70%, high at 82%, and critical at 90%. Treat a compaction as critical when it reduces context by less than 20%, leaves context at or above 90%, or repeats twice within ten minutes while staying at or above 82%.

At elevated risk, minimize inline payloads. At high risk, write a checkpoint and re-evaluate with `checkpoint.completed_for_snapshot: true` before further delegation. At critical risk, complete only the current atomic action, create no workers or follow-ups, request at most one terse status from active workers, and write a handoff. Starting a fresh task remains a user action.

When token telemetry is unavailable, report `unknown`. Checkpoint at every material milestone and after 60 unattended minutes without a checkpoint. Do not infer context utilization from elapsed time, attachment count, or serialized size.

Keep checkpoint summaries sanitized. Include the objective, completed work, accepted decisions, remaining packets, validation, artifact references, active-worker disposition, and next action. Exclude source content, screenshots, full prompts, raw outputs, reasoning traces, and secrets.

## Task packets

Create a packet before delegation. Include:

- Generalized task family and operation.
- Goal, in-scope components, and explicit exclusions.
- Baseline revision or artifact hash.
- Required tools and tool policy.
- Mandatory acceptance gates, scoring rubric, and validation commands.
- Expected output: analysis, patch proposal, or isolated implementation.
- Risk, coupling, isolation mode, and budget.
- A concise result contract: summary, affected paths, validation result, recommendation, and artifact references for larger material.

Keep architecture, integration, and acceptance decisions with the frontier coordinator.

## Controlled experiments

Declare the hypothesis, candidates, changed variable, constants, budget, isolation, and evaluator before workers run. Change only model, native/normalized thinking budget, or prompt profile. Preserve all other inputs.

Prefer patch proposals for small independently judged changes. Use separate worktrees only after approval when execution or multi-file changes require it. Never allow candidates to share a mutable working tree.

Run mandatory checks first. Blind model identity and cost for qualitative review. Store the rubric score, gate results, acceptance, regressions, retries, tool turns, time to accepted result, available token data, latency, and cost provenance.

Default promotion floor is 80/100 and all mandatory gates must pass. A profile is normally proven after three comparable passing outcomes whose conservative score (mean minus one sample standard deviation) clears the floor.

Allow `early-decisive` promotion at moderate confidence when only one candidate passes gates, one candidate leads quality by at least 10 points without a major cost penalty, or one candidate is at least 50% cheaper while within two quality points and 10% measured latency. Require the next similar task as confirmation.

Retest after a regression, ten later selections, 30 days for moving aliases, or 90 days for pinned revisions.

## Evidence and recommendations

Use the exact profile identity:

`task_family | model_revision | host_runtime | normalized_thinking | native_thinking | prompt_profile_version | tool_policy_version`

When Cortex exists, query and spread from task-family and environment nodes, then record an outcome against the exact profile and reinforce only the useful exact relationship. Keep an eligibility boundary outside Cortex: an external recommendation cannot execute in Phase 1.

Without Cortex, append one sanitized JSON object per outcome to `.ultra-delegation/evidence.jsonl` using atomic writes. Keep reports and run artifacts gitignored.

## Route imports with trust-but-verify

An imported recommendation may guide the first local route only when it has qualifying evidence or source promotion, clears the local quality floor, passed source gates, reaches 0.80 compatibility, is fresh and available, and has no stronger local conflict.

Mark that route `imported-prior-pending-verification`. Run local gates and frontier review. Promote it to `locally-verified` after strong confirmation. If validation is subjective or weak, compare it with one eligible host-native alternative first. If it fails, quarantine the prior for this environment, record the contradiction, and schedule a bakeoff. Imported early-decisive or low-confidence routes always require local comparison.

Apply conflicts in this order: current-turn choice, project pin, local proven/verified evidence, compatible high-confidence global prior, compatible bundle prior, then provisional evidence.
