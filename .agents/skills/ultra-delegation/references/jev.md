# Optional Jev routing and shadow judging

Jev evaluates bounded task packets at delegation boundaries. The native host still executes workers; the coordinator owns architecture, integration, final verification and acceptance. This is an experimental adapter, not an interceptor for the host's internal agent loop.

The ordinary `ultra_delegation.py` helper remains offline and dependency-free. `jev.py` uses the standard-library HTTP client for TypeSafe calls. Keyring is optional and only used for read-only OS credential lookup. Provider-crossing worker adapters and local execution remain unsupported.

Read the generated [question contract](jev-questions.md) for the exact questions, outbound fields, answer consumption, and current atomicity limitations. The adjacent [JSON contract](jev-questions.json) is generated from the same production payload builders. Refresh with `python3 <skill>/scripts/jev_docs.py --write`; CI runs `--check` and fails on drift. Generation is offline and never reads credentials.

For measured downstream outcomes and threshold sweeps, use the [benchmark workflow](jev-benchmark.md). For shipped candidates that adapt to local outcomes, use the [shortlist workflow](shortlist.md). Neither changes policy or promotes Jev judgments into worker evidence.

## Setup and credentials

Resolve these scripts relative to the installed skill directory. Always place `--root` before the subcommand. In examples below, `<skill>` is that directory and `<state>` is the project's `.ultra-delegation` directory.

On macOS, existing credentials are read through the system `/usr/bin/security find-generic-password` utility. Only service/account names enter its arguments; the value stays in captured process memory. This uses the utility's existing permissions and never modifies the item, access controls or lock state. It avoids granting a changing Python executable access merely to read the entry.

On Windows/Linux, install `keyring>=25,<26` in a dedicated Python virtual environment and use that environment's Python for `jev.py`. Windows Credential Locker and Linux Secret Service/KWallet backends are accepted; plaintext, third-party, null and chained backends are refused. Backend discovery and reading run in an owned subprocess with a private result pipe. No automatic installation or machine-wide changes occur.

Both read paths have a separate five-second bound. A locked, denied or unavailable store returns an explicit unavailable result; a stalled read returns `credential-store-timeout`. The owned reader is terminated. OS permissions remain authoritative; the adapter never answers a permission dialog or prompts for a password. Use the existing environment variable option if the store cannot be accessed.

```sh
python3 <skill>/scripts/jev.py --root <state> auth status
python3 <skill>/scripts/jev.py --root <state> auth check
```

The adapter only reads credentials. It never creates, changes, deletes, migrates, or prompts for a Keychain/credential-store value. `auth status` checks local availability only; `auth check` explicitly sends a small synthetic request. Neither returns the key. Existing entries do not need to be saved again.

Point to an existing entry using its non-secret service and account names:

```sh
python3 <skill>/scripts/jev.py --root <state> configure --credential-service "EXISTING_SERVICE" --credential-ref "EXISTING_ACCOUNT"
```

`--credential-ref` identifies the account; it is not the key. These names must match the user's existing entry. The adapter does not enumerate the credential store or guess another entry. Defaults remain service `ultra-delegation.typesafe` and account `default` for compatibility. Account labels such as email addresses and service names containing spaces are supported. Configuring the locator writes only project policy, never the credential store.

Alternatively, inject `TYPESAFE_API_KEY` with your secret manager or CI configuration. A nonempty environment value takes precedence over the OS store, including when that value is invalid. Do not put keys in project JSON, shell arguments, source, logs, or reports. Missing credentials return an unavailable result; there is no setup or write fallback.

Credential availability enables nothing. Enable routing independently:

```sh
python3 <skill>/scripts/jev.py --root <state> configure --routing shadow --share-summaries yes
# Explicit opt-in to let the host consume active routing decisions:
python3 <skill>/scripts/jev.py --root <state> configure --routing active
# Separate permission for selected code/output excerpts:
python3 <skill>/scripts/jev.py --root <state> configure --judging shadow --share-artifacts yes
```

Configuration preserves existing project settings. The version-1 `jev` section defaults to routing/judging `off`, sharing `false`, model `jev-1.13.0`, rubric `jev-rubric-v1`, threshold `0.90`, credential service `ultra-delegation.typesafe` and account reference `default`. Old policies inherit these defaults without rewriting. `--model` accepts pinned revisions, not moving aliases. `--suitability-threshold` is configurable above 0.5 through 1.0. The default is an experimental threshold, not a measured correctness probability.

## Routing packet and workflow

Prepare JSON explicitly; the adapter never discovers source files, host logs, conversation history, or candidate capabilities. Use actual host discovery and current evidence, including sanitized Cortex records when applicable. This new command uses only the supplied evidence and candidates; the coordinator must include applicable catalog entries explicitly.

Required top-level fields:

- `run_id`: letters, digits, hyphens and underscores, at most 100 characters.
- `summary`: bounded sanitized description, plus `requirements`: 1–24 acceptance criteria.
- `task`: authoritative signature with `task_family`, `operation`, `language`, `risk`, `coupling`, `validation`, and `tools`; other existing task signature dimensions should be supplied when known. Automatic routing is limited to low risk and low coupling.
- `context`: current host/provider, exact available model revisions and native thinking settings, following the ordinary helper contract.
- `snapshot`: host-supplied context-guard snapshot, explicitly marking unavailable telemetry when necessary. A saved stopped guard state for this run must be reevaluated through the ordinary guard commands first.
- `candidates`: objects containing `profile` (the existing exact worker identity plus required `execution_location: "remote"` discovery metadata), `description`, and optionally `user_selected`, `source`, or `imported_prior`. Descriptions explain scope and demonstrated capability, not permission.
- Optional `records`: canonical validated worker outcome records. Never manufacture evidence for live routing.
- Optional `experiment`: `variable` (`model`, `thinking`, or `prompt_profile`), `isolation` (`read_only` or `patch_proposal`), and `max_candidates` (2–3).

A complete minimal packet follows. `example-worker-v1` is a placeholder, not a claim of availability. Replace the model/revision, native thinking setting, host and provider with actual discovery. With no evidence this candidate remains provisional, so this example cannot become a routine direct route. To nominate an experiment, supply a second eligible candidate and an `experiment` specification.

```json
{
  "run_id": "review-1",
  "summary": "Review a small Python function for empty-list handling.",
  "requirements": ["Check empty and nonempty input", "Return a read-only patch proposal"],
  "task": {
    "task_family": "python-correctness-review", "operation": "patch_proposal",
    "language": "python", "risk": "low", "coupling": "low",
    "validation": "unit-tests", "tools": "read-only"
  },
  "context": {
    "host": "codex", "provider": "openai",
    "available_models": ["example-worker-v1"],
    "thinking_settings": {"example-worker-v1": ["medium"]}
  },
  "snapshot": {"telemetry": {"availability": "unavailable"}},
  "candidates": [{
    "profile": {
      "task_family": "python-correctness-review", "provider": "openai",
      "model": "example-worker-v1", "model_revision": "example-worker-v1",
      "host": "codex", "execution_location": "remote",
      "thinking": {"normalized": "medium", "native": "medium"},
      "prompt_profile": "bounded-review-v1", "tool_policy": "read-only-v1"
    },
    "description": "Candidate for bounded Python correctness review; no local evidence yet."
  }],
  "records": []
}
```

```sh
python3 <skill>/scripts/jev.py --root <state> route --input packet.json --dry-run
python3 <skill>/scripts/jev.py --root <state> route --input packet.json --write > decision.json
python3 <skill>/scripts/jev.py --root <state> recheck --input packet.json --decision decision.json
```

`--input -` reads stdin. A dry run validates the packet and shows the exact outbound body without retrieving credentials or making a request. A blocked or disabled route returns its reason rather than a body. Treat previews and packet/decision files as local working artifacts and keep them out of version control. `--dry-run` and `--write` are mutually exclusive.

Eligibility and context checks run first. Eligible user choices and pins bypass Jev. High risk, coupling, coordinator-owned work, no eligible candidate, or more than 12 eligible candidates return to the coordinator; candidates are never silently truncated. Jev sees task summaries, profile metadata and evidence aggregates, not whole evidence records. It evaluates ambiguity, coordinator ownership, and per-candidate semantic fit together.

In active mode, sufficiently suitable profiles are selected by the existing evidence-tier and cost order. Unknown cost remains unknown. Locally proven/verified evidence outranks compatible imported priors. Imported first-use routes remain `pending_verification`: run local gates and frontier review, and follow the existing weak-validation comparison/quarantine rules. Jev never promotes them itself.

Provisional or stale profiles cannot become routine direct routes. When no suitable established profile exists, Jev may nominate 2–3 suitable eligible profiles for a controlled experiment. Nominations obey the one-variable, low-risk, isolation and medium-or-lower effort limits and project limits. `action: experiment` is a proposal requiring coordinator handling under the existing experiment protocol, never a worker-launch instruction.

Results separate `action` / `selected_profile_id` (effective behavior) from `recommended_action` / `recommended_profile_id` and `nominated_profile_ids`. `action: coordinator` means no worker dispatch. Shadow routing preserves an established baseline and records disagreements. Service failures return `unavailable`, the baseline and original ranking for coordinator handling; do not guess a replacement route.

Before dispatch, refresh discovery and evidence, regenerate the packet if anything changed, and run `recheck`. It requires an identical saved event, matching packet/policy hashes, an age of at most five minutes, current eligibility and a passing context guard. Any changed packet requires reevaluation. This is a cooperative stale-decision check, not a signature, sandbox or proof of host authorization. The host applies worker tools and authority and executes the selected exact profile.

## Shadow judge packet

Required fields are `run_id`, pinned `model`, `rubric_version`, `requirements`, and 1–3 anonymized `candidates`. Each candidate contains:

- `excerpts`: 1–12 explicitly selected text snippets, each at most 4,096 characters.
- `gates`: nonempty observed results with `id`, boolean `mandatory`, and boolean `passed`; at least one must be mandatory. Execute deterministic checks before constructing these results.
- `validation_summary`: bounded observations explaining what checks do and do not establish.
- Optional independent `reference_score` (0–100) and `reference_acceptable` (boolean), used only locally for comparisons and never sent to Jev.

No worker name, model, cost or profile field is accepted in judge candidates. Remove identifying prose from excerpts yourself; the adapter cannot reliably anonymize arbitrary text. Excerpts remain untrusted data and can steer a model despite explicit instructions. Include adversarial examples in qualification.

```sh
python3 <skill>/scripts/jev.py --root <state> judge --input judge-packet.json --dry-run
python3 <skill>/scripts/jev.py --root <state> judge --input judge-packet.json --write
```

The fixed rubric scores requirement coverage, scope adherence, evidence support and clarity on five described levels. Code maps each expectation to 0–100 and averages dimensions equally. Insufficient evidence produces no aggregate score. A mandatory gate failure always prevents a suggested acceptable result, even when semantic scores are high. `shadow_scores` are never authoritative quality, acceptance or promotion evidence. Keep the same pinned model and rubric for every candidate in a bake-off. Frontier review remains authoritative.

## Bounds, evidence and costs

Only `https://api.typesafe.ai/v1/systemone` receives requests; redirects are refused. The transport runs in an owned child process with a 20-second deadline covering DNS, TLS, response reading and at most one retry for transient failures. Process scheduling is not a real-time guarantee. Invalid credentials and 422 validation failures are not retried. Request bodies are limited to 24 KiB and response bodies to 256 KiB. Oversized inputs are rejected without truncation. Returned model, questions, types, probabilities, choices and score expectations are validated.

`--write` appends allowlisted metadata to ignored `<state>/jev/decisions.jsonl`. It excludes packet summaries, requirements, excerpts, raw responses and secrets. Decision and question hashes support reproducibility; sanitized probabilities, rubric scores, usage and provenance support comparisons. These events never enter worker evidence, Cortex capability outcomes, catalogs or learning exports.

Ordinary run/project reports include Jev routing and judging overhead and disagreements. Token-based costs use a dated price for `jev-1.13.0` and are labeled estimated. Retry costs are unavailable because an unanswered request might have been billed. Unknown-model pricing remains unavailable. Worker savings are reported separately and exclude Jev overhead; no counterfactual savings are inferred from shadow routing.

## Qualification

```sh
# Offline status, no credential access or API call:
python3 <skill>/scripts/jev_qualification.py
# Explicit paid evaluation using only public synthetic fixtures:
python3 <skill>/scripts/jev_qualification.py --root <state> --live --output qualification.json
```

The live runner compares authored synthetic labels, including an ambiguous task, a defective constant-return implementation, embedded judge instructions and reversed candidate order. It reports route agreement, abstention, false acceptance, judge disagreement, order sensitivity, latency and estimated cost. Missing credentials or incomplete service results leave qualification pending. Completed means measurements were collected, not that quality passed a production threshold. It does not tune thresholds or enable any project mode.

These fixtures test a narrow demonstration. Before relying on active routing at scale, use independently reviewed examples and held-out tasks from your own task families. No live routing-quality or judging-quality claim follows from mocked tests.

Authoritative API and credential references: [TypeSafe API](https://docs.typesafe.ai/api), [models](https://docs.typesafe.ai/models), [confidence](https://docs.typesafe.ai/confidence), [documented model limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13), [OS keyring documentation](https://keyring.readthedocs.io/en/latest/).
