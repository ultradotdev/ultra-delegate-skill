# Jev v2 project pilot

Use `scripts/pilot.py` for the new project test drive. This is an experimental Python 3.10+ workflow with JSON inputs and self-contained HTML/JSON telemetry. It does not execute workers: the coordinator uses the current host's native worker tools after rechecking an effective route. No direct worker-provider APIs or local inference adapters are added.

The pilot replaces the legacy router's broad fit question with the [generated v2 question contract](pilot-questions.md). Its defaults are experimental operating points, not qualified success guarantees. Keep `jev.py` and its existing benchmarks available as comparison tools; they do not control pilot policy or its independent outcome ledger.

## First test drive: Yarn consolidation

The intended project is the consolidation of the GPT-6 and Fable 5.1 versions of Yarn into one app with delegation built in. These are descriptions of the source app versions, not model IDs discovered by the router.

Start with bounded packets: compare one component's behavior, propose one migration, add component regression tests, or review one consolidation patch. The coordinator owns the unified architecture, cross-component integration, and acceptance. Record related variants under the same `group_id` so repeating one component does not inflate confidence.

```sh
# Set this to the extracted or checkout skill directory, not a live-installed copy.
SKILL_PATH=/path/to/ultra-delegation

# Offline demonstration. Use a fresh directory. Calls no API or credential store.
python3 "$SKILL_PATH/scripts/pilot.py" --root /tmp/yarn-demo demo

# Inspect broader discovery seeds and create an illustrative packet.
python3 "$SKILL_PATH/scripts/pilot.py" catalog
python3 "$SKILL_PATH/scripts/pilot.py" example --output /tmp/yarn-packet.json

# Initialize within the target project. Security is off by default.
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot init \
  --mode shadow --share-summaries --baseline-id candidate-2

# Replace synthetic fixture values with actual host discovery and a prepared task.
# Set synthetic=false only for a real packet, after replacing the example model IDs.
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot route \
  --input /tmp/yarn-packet.json --dry-run

# This is the explicit network step. A saved decision is returned as JSON.
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot route \
  --input /tmp/yarn-packet.json --live

# Use the returned decision ID, then execute through the native coordinator host.
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot recheck \
  --decision dec_REPLACE_WITH_RETURNED_ID --input /tmp/yarn-packet.json

# Prepare a review form for the actual worker, baseline or challenger.
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot outcome-template \
  --decision dec_REPLACE_WITH_RETURNED_ID --candidate candidate-2 --output /tmp/yarn-outcome.json

# Fill the form from independent review and observed tests. Unfilled forms are invalid.
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot observe \
  --input /tmp/yarn-outcome.json

python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot report
```

Commands must be run in the intended project's directory or with an explicit `--root`. Keep `.ultra-delegation/` ignored in that project before using version control. The CLI does not edit the project's ignore file, auto-install the skill, scan repository content, or send anything beyond the prepared packet.

`init` is exclusive and never overwrites an existing policy. To change mode, baseline, sharing, thresholds, exclusions, quarantine or the non-secret credential locator, edit the project's `policy.json`; subsequent decisions include its hash. Old decisions must be reevaluated after changes. Saving credentials does not activate the pilot. Credentials resolve from `TYPESAFE_API_KEY`, then the selected existing OS-store service/account. There is no credential set/delete/prompt flow. macOS uses its native read-only Keychain utility; Windows/Linux use optional keyring. Credential reads have a separate five-second timeout, and stalled reads return `credential-store-timeout` with zero HTTP attempts.

## Packet contract and boundaries

The `example` command writes a complete synthetic packet with four illustrative configurations. Replace all example models, capabilities, costs, and token counts before a real test. `catalog` returns five Codex discovery seeds across different intended roles. A seed establishes neither availability nor quality. Include any additional discovered current-host/provider configuration; packets accept up to 128 candidates, with a deterministic shortlist of eight by default and a configurable maximum of twelve. The API request remains bounded to 24 KiB; oversized requests return an explicit unavailable result and the offline baseline rather than truncating state. A dry-run rejects oversize input.

The packet includes:

- `task_id` and `group_id`, safe opaque labels for telemetry, and `synthetic`.
- `task`: explicit `scope_id`, `operation`, `risk`, `complexity` (`routine` or `complex`), `work_kind`, summary, requirements, declared `acceptance_gates`, worker boundary, intended use, required tools/modalities, input/output token budget.
- `context`: current `host` and `provider`, timezone-aware `observed_at`, and `delegation_allowed` from the coordinator context guard.
- `candidates`: exact model/revision, host/adapter, native effort, prompt contract/version, tool policy, remote execution location, discovered availability, tools, modalities, context/output capacities, capability/scope descriptions, optional roles, and estimated full worker/review/retry/fallback cost or null.
- Optional `user_choice_id`, which takes precedence over a configured project pin.

`input_tokens` is the coordinator’s admission reservation for the complete worker input, including host instructions and tool overhead; `output_tokens` reserves output. These declared budgets are not measured usage or native API controls, and the short routing summary cannot establish them. Unknown context capacity always blocks admission. By default, unknown output capacity also blocks it. An explicit `allow_host_managed_output` policy opt-in permits an unreported output ceiling only for remote Codex/OpenAI `codex-native` configurations marked `output_limit_source: native-host`. Context fit remains required, any reported output ceiling still applies, and the task must declare the mandatory `complete-output` acceptance gate. The native host manages generation limits; this exception supplies no numeric ceiling or hard resource guarantee. See [the native Codex workflow](pilot-codex.md). `available` means the exact native model and effort combination was discovered, not merely that the provider exists. Discovery and recheck are cooperative host protocols, not a sandbox or proof against falsified packets.

One batch asks eight task questions and independent candidate operation/scope/evidence questions. Code enforces host/provider, adapter, location, context capacity, required tools, exclusions, quarantine, allowed risk and fresh capability checks. It retains eligible explicit user choices/pins without a Jev call. Changing inference state or policy changes the recorded hashes.

Scope has explicit risk and complexity. A semantic signal suggesting greater consequences or complexity than the prepared scope triggers repackage/coordinator handling. Ordinary bounded architecture proposals can use a planning scope; final architecture and acceptance remain coordinator-owned. Explicitly add `external-retrieval` to discovered tools when the host can provide authorized external retrieval. Jev cannot grant it.

## Effective routes and experiments

Modes are separate from `--live`:

- `off`: use the eligible configured baseline or an empirically qualified offline route; no Jev call.
- `shadow`: retain that offline route while recording the batched recommendation.
- `active`: use the Jev recommendation after deterministic checks. Unproven suitable candidates produce experiment nominations rather than executable routes.

Without `--live`, an enabled mode records an offline baseline decision with `live-not-requested`. Disabled sharing, missing credentials, transport failures, malformed responses and oversized payloads are explicit unavailable results with the eligible offline baseline. An unavailable explicit user choice is not silently substituted.

Read `action` and `selected_configuration_id` for effective execution; `recommended_*` fields describe Jev's suggestion. A saved decision alone never authorizes execution. `recheck` verifies the saved record, packet/policy/evidence hashes, time and fresh eligibility. Synthetic decisions cannot pass dispatch recheck. Experiment nominees require a separately scoped, isolated trial execution plan and independent review, including when no previous outcome evidence exists. The pilot proposes up to the shortlisted set; it does not impose the legacy three-candidate nomination cap or launch those candidates automatically.

The configured baseline is an explicit trusted starting choice, not a claim that it passed statistical qualification. Record baseline failures too. A selected-worker result measures adequacy; comparison requires another actual reviewed result for the same decision/task. An accepted baseline is not ground truth. Use extra comparison runs early, then target uncertain/new/failed cases plus periodic sampled audits. The first iteration does not automatically schedule bake-offs or claim the audit rate is calibrated.

## Learning and independent acceptance

Configuration learning identity is provider + resolved model revision + host/adapter + native effort + behavior-changing prompt contract + tool policy. `prompt_version` is audit metadata. Minor wording edits retain learning. A material instruction or tool-authority change requires a new contract/policy identity; the tool cannot infer semantic equivalence from two arbitrary prompts.

Evidence must match explicit scope, operation, risk, complexity and work kind. It excludes stale/future records, synthetic outcomes for real packets, and the current task group. Distinct groups are the denominator; a group with any failed outcome is failed. Current required gates and quality floors are reapplied. Initial routine eligibility requires at least five groups and a 95% Wilson lower endpoint of at least 0.70. These are uncalibrated pilot settings, not a production reliability target. Expose counts and bounds rather than a made-up Jev success confidence. Broader evidence transfer, automatic semantic scope inference and learned threshold calibration are later work.

Record the artifact hash and an independent human/frontier assessment. Every predeclared acceptance gate must be present and mandatory. The default acceptance requires positive independent review, passing mandatory gates, all four dimensions at least 70 and their mean at least 80. Dimensions are coverage, correctness, maintainability and clarity. Missing review stays pending by not submitting a completed outcome; templates contain nulls that validation rejects. One outcome per decision/configuration prevents duplicate counting. Corrections require an explicit future correction workflow; do not overwrite outcomes or silently drop failures.

Outcome cost components are preparation, worker, review, retry and fallback, each labeled measured, estimated or unknown. Allocate shared preparation costs once across comparator outcomes so total logged spend does not double-count them. Log explicit zero only when known. Candidate estimates use comparable observed mean worker/review/retry/fallback cost when available, otherwise the supplied estimate; this is not a calibrated expected-cost model. Router/security usage is independently recorded with dated token-price estimates. Retried/invalid paid responses retain unknown billing. Subscription quotas are not converted to invented dollar prices.

## Optional security assessment

The new security assessment is off by default and advisory when enabled. This does not disable existing project tests or any mandatory security gate already declared in a task. For one result:

```sh
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot observe \
  --input /tmp/yarn-outcome.json --security-check \
  --security-input /tmp/selected-security-excerpts.json --live
```

Separately enable `share_artifacts` in policy before using it. The selected security file has only `requirements` (a nonempty array), `excerpts` (a nonempty array), and `validation_summary` (text). No automatic source collection. The user controls credential storage; the adapter only reads the existing key.

`--security-check` or policy `security_check: true` requests the advisory check. Without either, the status is `not_checked`. Missing permission, input, key, unavailable service, malformed response or evaluator error is `unavailable`; it never prevents the independently assessed outcome from being recorded. Security findings return `fail`, ambiguous evidence `indeterminate`, and sufficiently clear selected evidence without a detected issue `pass`. Pass is not a guarantee that code is secure. Initial independent advisory cutoffs are 0.90 for sufficient evidence and 0.80/0.20 for issue/clear bands; no live qualification is claimed.

Security status is a separate report dimension and never overwrites acceptance or upgrades worker evidence in this iteration. A failed advisory should be inspected by the coordinator, but evaluator availability cannot break the pilot. Logs retain hashes, typed probabilities, reason codes and usage, never code excerpts or provider response prose.

## HTML and JSON telemetry

Each command writes metadata under `decisions/` or `outcomes/`; reports read only those local ledgers. `report` writes a new `.html` and `.json` pair under `reports/`, or `--output-prefix /path/new-report`. Files are created exclusively with private default permissions. HTML has no remote assets or analytics and escapes displayed values. It includes filtering, effective versus recommended choices, candidate evidence, quality/gates, optional security, costs, provenance and pending observations. The JSON is the application integration contract. It also counts inferred route recommendations, independently reviewed recommendation outcomes, pending recommendations, baseline disagreements, and actual paired acceptance comparisons. Explicit choices and pins do not count as Jev inference evidence. An observed accepted result establishes adequacy for that task, not superiority over unrun alternatives.

Reports exclude task summaries, requirements, candidate descriptions, source code, credentials and unknown provider fields. Use opaque scope/task/reviewer labels since those labels are included. Synthetic reports are visibly marked and cannot qualify thresholds or savings. Total workload spend includes actual comparison and experiment costs. It stays unknown while selected/fallback outcomes or final coordinator completion are unobserved; trial artifacts alone do not establish task completion. Known logged spend and experiment spend remain separate diagnostics. No realized savings are inferred from shadow decisions.

The Yarn app can import `pilot.route_packet`, `pilot.observe` and the pure report builder, or run CLI commands and consume JSON. Keep subprocess calls argument-based and secrets out of argv. Policy, question version, payload hash, scope and configuration identity remain explicit so a future Rust implementation can replace internals while preserving recorded semantics. Python remains the first iteration because the policy and contracts are still being evaluated.

## Qualification status and next steps

The local synthetic demo demonstrates routing proposals, accepted/failed outcomes, accumulating scoped evidence, an unavailable optional security check and a pending task. It establishes tooling behavior only. No real Yarn code has been rebuilt or reviewed, no real Jev or worker quality measured, and no threshold calibrated by that demo.

Next: discover the actual Yarn execution host/configurations, define a small set of consolidation packets and independent checks, run in shadow mode, collect actual worker/baseline comparisons, and inspect the report. Broader provider execution, automated experiment scheduling, statistical calibration and a Rust binary remain separate follow-ups.
