# Measurement and Portable Learning

Use this reference when recording outcomes, generating value reports, promoting routes, or moving learnings between projects.

## Outcome envelope

Record a JSON object with these groups. Use `null` plus `availability: "unavailable"` rather than guessing missing telemetry.

- `run`: run ID, timestamps, baseline revision, isolation mode, verification commands, and artifact hashes.
- `task`: family, operation, language/framework, relevant major versions, risk, coupling, tools, validation method, and affected-path classes.
- `profile`: provider, exact model/revision, host/runtime, normalized and native thinking settings, prompt-profile ID/hash, and tool-policy ID.
- `quality`: score from 0 to 100, mandatory gates, regressions, evaluator confidence, acceptance, and validation strength.
- `usage`: input, output, thinking, and cached tokens when reported.
- `performance`: total latency, time to first token, throughput, tool turns, retries, escalations, and time to accepted result.
- `cost`: selected-route cost, comparator cost, experiment cost, currency, price source/date, and measurement method.
- `learning`: provenance, evidence count, conservative score, promotion state, compatibility, confirmation requirement, and quarantine state.

Do not store source contents, secrets, full prompts, raw candidate outputs, or reasoning traces. Store hashes and sanitized summaries.

For local estimates, put a dated entry under `price_table.<model-revision>` with `effective_date`, `input_per_million_usd`, `output_per_million_usd`, and optionally `thinking_per_million_usd`. The helper estimates only components whose token counts and rates are both present.

## Quality and promotion

Require every mandatory gate and a default score of at least 80. For three or more comparable outcomes, calculate:

`conservative_score = mean(scores) - sample_standard_deviation(scores)`

Promote normally when the conservative score clears the floor. Allow `early-decisive` promotion when any condition holds:

1. Only one candidate passes mandatory gates.
2. One passing candidate leads by at least 10 quality points without a major cost penalty.
3. One passing candidate costs at least 50% less, quality differs by no more than 2 points, and measured latency differs by no more than 10%.

Mark early promotion as moderate confidence and require confirmation on the next similar task.

## Savings accounting

Choose the baseline in this order:

1. Rejected candidate from the same bakeoff (`measured`).
2. Recent comparable historical run (`measured` or `estimated`, depending on telemetry).
3. Configured frontier route using a dated price table (`estimated`).
4. No claim (`unavailable`).

Keep these values distinct:

- Selected-route cost.
- Comparator cost.
- Total experiment cost across all candidates and evaluation.
- Realized savings on later routine executions.
- Projected savings per future similar task.
- Break-even count: `ceil(experiment_overhead / projected_savings_per_task)` when both values are positive.

Do not call a bakeoff itself a saving. It is an experiment investment.

## Inline report

Use this order:

1. State that Ultra Delegation was used and what variable was tested or routed.
2. Name candidates and settings.
3. Report gates and quality equivalence or difference.
4. Report measured performance and cost, clearly labeling estimates or missing values.
5. State the recommendation, confidence, confirmation requirement, and where it was recorded.
6. Mention other task-family recommendations only as separate historical evidence.

## Artifact reports

Write significant reports to `.ultra-delegation/reports/<run-id>.md` and `.json`. Include the hypothesis, constants, candidates, task packet, isolation, budgets, checks, anonymized scoring, outcome, confidence, experiment overhead, projected savings, and break-even estimate.

When guard state exists, include its latest risk, delegation decision, and required action. Label context telemetry by provenance. Do not claim realized or projected savings from avoided compaction because the counterfactual cost is not defensible.

## Cortex mapping

When Cortex supports constellation types:

- Create one `agent_identity` per exact task-specific profile.
- Create a task-family `pattern` or capability node.
- Link the profile to only its exact capability.
- Store compact outcome metrics through `record_outcome` or an `agent_outcome` node.
- Link report/export artifacts without embedding their contents.

Query and spread before routing. Filter recommendations for host/provider eligibility outside Cortex. If constellation types are unavailable, store sanitized `preference`, `pattern`, and `insight` nodes. Use JSON evidence only when Cortex is absent.

## Export bundle

Use schema ID `ultra-delegation-learning-v1`. Export only sanitized aggregates:

- Generalized task and environment signature.
- Exact profile identity.
- Evidence count, gate reliability, aggregate quality, cost, performance, confidence, and freshness.
- Promotion method, evaluation methodology, pseudonymous provenance, and content hashes.

Exclude project names, paths, source, full prompts, raw outputs, report bodies, credentials, and secrets. Make imports idempotent by hashing canonical JSON for each recommendation.

## Trust-but-verify import

Treat an import as an eligible prior when it has qualifying evidence, clears the local quality floor, has compatibility at least 0.80, is fresh, is available in the current host/provider, and does not conflict with stronger local evidence.

On first local use:

1. Mark it `imported-prior-pending-verification`.
2. Apply full local gates and frontier review.
3. Promote to `locally-verified` after strong validation passes.
4. If validation is weak or subjective, compare one eligible host-native alternative before promotion.
5. On failure, quarantine the import for this environment and trigger a bakeoff.

Imported early-decisive or lower-confidence results stay exploratory until locally compared.

## Conflict precedence

1. Current-turn choice.
2. Project policy pin.
3. Locally proven or locally verified evidence.
4. Compatible high-confidence global prior.
5. Compatible bundle prior.
6. Provisional evidence.
