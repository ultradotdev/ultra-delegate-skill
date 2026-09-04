# Helper CLI

Resolve the helper path from the active skill directory, run it with Python 3, and place `--root` before the subcommand:

```bash
python3 <skill-directory>/scripts/ultra_delegation.py --root /absolute/project/.ultra-delegation validate
```

The helper performs deterministic local bookkeeping only. It never launches a model, provider CLI, or provider API.

## Commands

- `init [--force]`: create policy and required `.gitignore` entries.
- `validate`: validate host-bound policy and JSON fallback evidence.
- `doctor [--context '<json>']`: distinguish supplied capabilities from exercised execution, and explain local eligibility. Does not probe or invoke a provider.
- `guard evaluate --snapshot '<json>' [--run-id ID] [--write]`: classify host-supplied context telemetry and optionally persist the latest sanitized guard state.
- `guard checkpoint --run-id ID --summary '<json>' --write`: write a sanitized Markdown/JSON handoff and stop delegation until guard state is re-evaluated. Critical state remains stopped.
- `profile-id '<json-profile>'`: return the stable exact-profile ID.
- `rank --context '<json>' --task '<json>' --candidates '<json-list>' [--records FILE]`: apply locality, pins, local evidence, compatible global priors, quality, and cost. `--records` supports sanitized Cortex evidence without copying it into the fallback ledger.
- `experiment score --context '<json-host-context>' '<json-experiment>'`: enforce host/provider eligibility and the one-variable rule, score candidates, and detect decisive early promotion.
- `record '<json-outcome>'`: append one sanitized outcome to the JSON fallback ledger. Use only when Cortex is unavailable.
- `report run --run-id ID [--records FILE] [--write]`: produce one run report.
- `report project [--records FILE] [--write]`: aggregate project quality, performance, and realized savings.
- `catalog promote PROFILE_ID [--force]`: explicitly write a sanitized profile to the user-global catalog. Use `--force` only for an explicit human promotion.
- `catalog list` and `catalog report`: inspect global learning.
- `export [--records FILE] --output FILE`: create a sanitized `ultra-delegation-learning-v1` bundle.
- `import --input FILE --task '<json>' --context '<json>' --dry-run`: preview compatibility, conflicts, freshness, and eligibility.
- Replace `--dry-run` with `--apply` only after reviewing the preview. Applied entries remain pending local verification.
- `verify-import PROFILE_ID --result '<json-result>' --validation-strength strong|weak [--comparison-run-id ID]`: confirm a pending import, require a comparison for weak or exploratory evidence, or quarantine it after failure.
- `isolation prepare NAME --mode patch-proposal|temporary-copy`: create a managed local isolation directory and manifest. It does not copy a repository or create a Git worktree.
- `isolation cleanup NAME`: remove only a managed directory whose manifest validates.

## Profile shape

```json
{
  "task_family": "rust-code-change",
  "provider": "openai",
  "model": "gpt-5.6-terra",
  "model_revision": "gpt-5.6-terra",
  "host": "codex",
  "execution_location": "remote",
  "thinking": {"normalized": "medium", "native": "medium"},
  "prompt_profile": "worker-v1",
  "tool_policy": "patch-proposal-v1"
}
```

## Host-supplied results

Host context must include `host`, `provider`, `available_models` (exact revisions), and `thinking_settings` (revision to supported native settings). Missing discovery is unknown, while an empty catalog explicitly offers no models. Unknown execution locations cannot route. Example: `{"host":"codex","provider":"openai","available_models":["gpt-5.6-terra"],"thinking_settings":{"gpt-5.6-terra":["low","medium","high"]}}`. This is a shape example, not a claim about availability.

New records require a profile, boolean `accepted`, numeric quality score, and at least one mandatory gate. Unknown fields, embedded media, recognizable secrets, nonfinite values, and oversized records are rejected. Legacy records are projected to canonical fields on read without rewriting the original ledger. Resource-aborted records instead use `failure_kind: resource`, `accepted: false`, and `local_execution.status: resource-aborted`, with no quality score or gates.

Usage fields are `input_tokens`, `cached_input_tokens`, `output_tokens`, and `thinking_tokens`. When thinking tokens are supplied, `thinking_in_output` must explicitly say whether they are already included in output. Estimates require a dated price table and all relevant rates; incomplete usage remains unavailable. Do not put cached tokens in a second input total.

The host must supply gates, quality, selection/comparator flags, and telemetry. Use fields such as `metrics.quality_score`, `metrics.cost_usd`, `cost_kind`, `metrics.latency_ms`, `metrics.time_to_first_token_ms`, `metrics.tokens_per_second`, `metrics.tool_turns`, `metrics.retries`, and `metrics.escalations`. Mark unavailable values by omitting them rather than inventing numbers.

## Context guard snapshot

Supply only sanitized observations:

```json
{
  "observed_at": "2026-08-08T05:00:00Z",
  "telemetry": {"availability": "measured"},
  "context": {"used_tokens": 210000, "window_tokens": 258400},
  "compactions": [
    {"timestamp": "2026-08-08T04:59:00Z", "before_tokens": 240000, "after_tokens": 210000}
  ],
  "checkpoint": {"minutes_since": 30, "completed_for_snapshot": false},
  "milestone": {"completed": true},
  "history": {"attachment_count": 8, "serialized_bytes": 1000000, "task_age_minutes": 90},
  "active_workers": 1,
  "unattended": false
}
```

Label telemetry `measured`, `estimated`, or `unavailable`. Omit token values when unavailable. History counters are diagnostic only and never determine a hard stop.

Replace illustrative timestamps with fresh observations. Observations older than `max_observation_age_seconds` (300 by default) become unknown. After `guard evaluate --write`, `guard checkpoint --write` binds its handoff to that evaluation's `snapshot_id`. Supply that exact ID in `checkpoint.completed_for_snapshot` when re-evaluating; `true` alone cannot unblock delegation. Critical states stay stopped. These are cooperative safeguards, not a process watchdog.

The checkpoint summary accepts `objective`, `completed`, `decisions`, `remaining`, `validation`, `artifact_references`, `active_workers`, and `next_action`. Store references rather than artifact bodies. The helper rejects unsupported fields, raw outputs, prompts, source, reasoning, screenshots, and common secret markers.

For Cortex-backed runs, pass a sanitized JSON list, `{ "records": [...] }`, or JSONL file through `--records`. This generates reports and exports without writing the fallback evidence ledger.
