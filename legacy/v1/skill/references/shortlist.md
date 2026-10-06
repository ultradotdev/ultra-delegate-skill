# Standing and adaptive candidate shortlist

`scripts/shortlist.py` prepares a deterministic candidate pool of at most 12 exact profiles. It runs offline and does not authorize dispatch, promote a profile, call Jev, or execute a worker. Pass both its `candidates` **and its normalized, chronologically sorted `records`** into the usual prepared Jev routing packet, preserving the authoritative task, context and snapshot. Copying the unsorted original evidence can change which failure the ranker treats as latest. The route and dispatch recheck still apply.

## Shipped starting pool

`assets/standing-shortlist.json` ships two native Codex/OpenAI discovery seeds: `gpt-5.6-luna` medium and `gpt-5.6-terra` medium. They carry **no demonstrated capability, cost or quality claim**. Exact availability and native thinking settings must be supplied by current host discovery. An absent seed is rejected; a name never establishes availability. A host may remove or rename these models independently of the skill release.

Seeds become task-specific profiles only when the caller supplies `seed_profile.prompt_profile` and `seed_profile.tool_policy`. These must identify the actual prompt and tool configuration the host will use. The task family comes from the explicit task signature. This creates a new profile; it does not rewrite a previously recorded identity. Without `seed_profile`, only explicit candidates and supplied compatible worker records are considered.

Claude Code and OpenCode have native worker templates elsewhere in the skill. No provider model IDs are guessed for those hosts, and no new API execution adapters are introduced here. Supply profiles discovered on the current host/provider. Cross-provider profiles remain ineligible.

## Input and command

```sh
python scripts/shortlist.py --input shortlist-packet.json > shortlist-result.json
# Optional: read only this project's policy.json; no evidence/catalog auto-discovery.
python scripts/shortlist.py --input shortlist-packet.json --root /project/.ultra-delegation
```

The JSON packet has `task`, `context`, optional `candidates`, optional `records`, optional `seed_profile`, optional `limit` (1–12, default 12), and optional `policy` (normalized routing policy overrides). `--root` and an inline `policy` are mutually exclusive. Use `--root` for policy files containing the older nested `routing`/`promotion` layout, so the existing loader normalizes them. There are no writes, credentials or network calls.

```json
{
  "task": {
    "task_family": "python-correctness-review",
    "operation": "patch_proposal",
    "language": "python",
    "risk": "low",
    "coupling": "low",
    "validation": "unit-tests",
    "tools": "read-only"
  },
  "context": {
    "host": "codex",
    "provider": "openai",
    "available_models": ["gpt-5.6-luna", "gpt-5.6-terra"],
    "thinking_settings": {
      "gpt-5.6-luna": ["medium"],
      "gpt-5.6-terra": ["medium"]
    }
  },
  "seed_profile": {"prompt_profile": "review-v1", "tool_policy": "read-only-v1"},
  "candidates": [],
  "records": [],
  "limit": 12
}
```

The availability in this example is illustrative. Replace it with observed host capabilities. Candidates use the existing Jev shape: `profile`, `description`, optional `user_selected`, `source`, `imported_prior`. Outcomes use the validated worker evidence contract with `created_at` including a timezone. Duplicate outcomes and profile ID mismatches are rejected. The caller must supply independently reviewed observations; schema validation cannot prove their truth. Jev shadow judgments are not worker outcomes.

## How results change the pool

The helper merges explicit project profiles, exact profiles from task-compatible outcomes, and enabled shipped seeds. Explicit metadata takes precedence over a discovery seed with the same identity; conflicting project/worker metadata is rejected. It never reads repository code, chat history, project evidence, or the global catalog automatically. Worker records with a different task signature, host or provider cannot supply learned ranking evidence. Matching checks include every signature dimension present in the requested task; supply relevant language/framework versions when they affect comparability.

The shared offline ranker applies current host/provider availability, native thinking support, exclusions, quarantine, existing imported-prior rules, freshness, and minimum comparable outcome rules. Records are ordered by observation time before ranking; equal timestamps place failures/regressions after passes so array order cannot hide a failure. User selections and project pins remain subject to eligibility. Unknown cost remains `null`.

An accepted worker result does not automatically prove a seed. Promotion uses the existing minimum comparable outcomes and quality requirements. Fresh qualifying outcomes can move an exact local profile above seeds; a later failure, stale evidence or retest interval removes its proven status under the existing rules. Retest-required profiles lose exploratory priority but remain inspectable. Historical failures are not discarded to manufacture recovery: use the normal verification workflow. Explicit choices and pins retain their existing override semantics.

The shortlist preserves the eligible baseline, all eligible user selections and pins, and the entire highest qualifying evidence tier. If that protected pool exceeds the limit, it returns `status: coordinator` with an empty candidate list rather than silently removing protected profiles. Remaining slots follow evidence tier, retest status, known cost, conservative quality, and exact profile ID as the stable tie-breaker. No cost is inferred from model names or seed order.

Output includes candidates, validated matching records, per-profile inclusion/rejection reasons, source provenance, evidence status, measured statistics, `evidence_baseline_profile_id` (null when all profiles are unproven), ignored-record reasons, and input/policy/standing-asset hashes. This baseline differs from Jev's diagnostic `baseline_profile_id`, which can identify an unproven top-ranked profile. `dispatch_authorized` is always false. Send unproven seeds through the existing controlled-experiment rules; shortlisting alone cannot turn them into executable Jev routes.

Local results change subsequent invocations when the coordinator explicitly supplies the updated records. They do not modify the shipped asset or export private learning. The shipped list changes through reviewed releases; the task-specific list changes through local evidence.
