# Capability research

Use `assets/capability-index.json` to add reviewed starting expectations to native
candidate packets. [The generated index](capability-index-data.md) lists every
claim and source. Provider positioning is useful from the first run, but does not
establish task success. Local reviewed outcomes continue through the existing
pilot learning workflow; research is never exported as worker evidence.

The shipped index includes all 266 models in Epoch AI's September 21 snapshot,
across current and older OpenAI, Anthropic, Google, Alibaba, DeepSeek, xAI, Meta,
Mistral and other families. It preserves 90% bootstrap intervals where supplied;
GPT-5 and Claude 3.5 Sonnet have no reported interval in this export. The report
is searchable by model or organization. These model-level priors are available across native
efforts, explicitly labeled as composites across benchmark settings. They do not
claim that a low-effort worker achieved the published score. Jev receives them in
the candidate capability description; code does not sort candidates by ECI or
convert ECI to suitability probabilities. The existing routing, review and
recovery rules continue to apply.

Research coverage is broader than worker availability. The initial five verified
native-ID bindings are included; other rows preserve Epoch's exact model and
organization names under stable research IDs. Add explicit bindings for additional
host-discovered models with `epoch_import.py --mappings FILE`. This is identity
matching, not a performance qualification requirement. Unmapped research rows
stay visible but cannot masquerade as native model IDs. Host/provider restrictions
and tool/context eligibility still apply. Only matched shortlisted candidates
are sent to Jev, not the entire catalog.

## Build and inspect

Run from the target repository, with `SKILL_PATH` pointing at this skill folder:

```sh
python3 "$SKILL_PATH/scripts/capability_index.py" \
  --output-dir .ultra-delegation/capability-review
```

This creates compact `report.html`, `report.json`, and `report.md` artifacts using
today's UTC date. It is entirely offline. Add this option to the normal
`pilot_codex.py` packet-building command:

```sh
--capability-index "$SKILL_PATH/assets/capability-index.json"
```

Keep `--capability-description` for the explicitly prepared work capability and
`--scope-envelope` for the worker boundary. The builder appends matched research
with its index hash, source IDs, check/evaluation dates, effort and age flags.
Its as-of date is the supplied host observation's UTC date. Use a fresh host
observation and inspect the usual routing dry-run before sending the packet.
Research text is selected data within the existing summary-sharing permission.
No source pages, repository files or credentials are fetched automatically.

Exact provider/model strings must match. No family alias or substring inference
is used. General provider claims can describe a model across efforts, but they
are explicitly labeled as effort-unspecified. Benchmark results require matching
effort; an unknown evaluated effort stays in the report and does not enter a
candidate description. Even matched external results describe their own harness,
not Codex-native success. A missing match never blocks an eligible worker.
Composite `capability-prior` rows differ from effort-specific `benchmark-result`
rows: they inform broad expectations even when evaluated effort is unspecified.

The index also covers the five OpenAI discovery seeds with original summaries
of provider documentation checked on September 21, 2026. SWE-bench is a pinned
reference only: that snapshot has no exact matches for these models. Its source
license is CC BY-NC 4.0, and no leaderboard data or scores are bundled. Artificial
Analysis is skipped; this feature has no AA adapter and never reads its key.

Epoch's scores are redistributed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), attributed to
[Epoch AI, Epoch Capabilities Index](https://epoch.ai/eci). The source record
retains the original CSV's SHA-256, retrieval date, attribution, and a notice that
we normalize scored rows, map selected names and generate summaries. This dataset's `date` is the
model release date, preserved as `metric.model_release_on`; it is never copied to
`evaluated_on`. The composite has no single known evaluation date in this export.
General ECI is jointly refitted, so scores can change without fresh evaluations
of a particular model. Confidence intervals describe index uncertainty, not
success probability on the next task.

SWE/Cyber ECI and raw per-benchmark results are not imported in this iteration.
The inspected public CSV exports do not contain a SWE ECI column; the interactive
domain view is not a documented stable export. Raw benchmark rows mix sources
and have no per-row license or explicit internal-evaluation flag. A blank source
does not establish that Epoch ran the evaluation.

## Refresh Epoch

Download the public [official CSV](https://epoch.ai/data/eci_scores.csv) to an
ignored project research folder. No API key or package install is required.
Then run the offline importer, using the actual download date and a new version:

```sh
python3 "$SKILL_PATH/scripts/epoch_import.py" \
  --scores .ultra-delegation/eci_scores.csv \
  --retrieved-on YYYY-MM-DD --version NEW_VERSION \
  --output .ultra-delegation/capability-index-next.json
python3 "$SKILL_PATH/scripts/capability_index.py" \
  --index .ultra-delegation/capability-index-next.json \
  --output-dir .ultra-delegation/capability-review-next
```

The importer reads every scored row, preserving model variants and joint/unknown
organizations. It never infers a native ID from Pro, Instant, family aliases or
new names. Missing scores remove the older matching Epoch prior; missing intervals
remain null and labeled as unreported. They are never filled with zero.
Invalid or half-missing intervals, duplicate identities, mismatched mapped labs,
future release dates and oversized files fail without changing the existing
index. The supplied retrieval date records a maintainer assertion, not an
authenticated timestamp from Epoch. Offline files must come from the cited URL;
the content hash establishes snapshot identity, not authenticity.

An additional mapping file is a JSON array of records containing `source_model`,
`source_organization`, `provider`, and `model`. Use exact Epoch names for the first
two and verified host/API identities for the last two. For example, this synthetic
record illustrates the shape, not a real provider ID:

```json
[{"source_model":"Example model","source_organization":"Example lab",
  "provider":"example-provider","model":"exact-host-exposed-model-id"}]
```

Mappings augment the built-in five and must be supplied again on refresh; native
bindings are not guessed or silently retained from a previous source snapshot.
Duplicate source or target mappings fail. Keep project mapping files alongside
the project-local research snapshot.

Review the generated report/diff, then use the new index with `--capability-index`.
To update the shipped copy, replace the asset after review and regenerate docs.
Refreshing Epoch preserves all other source dates. There is no automatic network
refresh during routing and no credential access.

## Age and updates

The JSON is the source of truth. Dates have distinct meanings:

- `checked_on`: when a maintainer actually inspected the cited source.
- `published_on`: its known publication or source revision date, otherwise null.
- `evaluated_on`: the known evaluation-run date, otherwise null. A submission,
  release, knowledge-cutoff, download or commit date is not this date.

Sources get `source-review-due` after 30 days by default. Benchmark results get
`old-evaluation` after 180 days, or `evaluation-date-unknown` when undated. These
are configurable maintenance warnings, not calibrated expiry or qualification
gates. Old research retains its age warning; it never grants permission, overrides
local failures, or raises the accepted quality score. Refreshing `checked_on`
cannot refresh an old evaluation.

To update, inspect the primary source, verify exact identity/effort and reuse
conditions, revise the short original summary and dates, and increment `version`.
For a benchmark claim record the board/version in `benchmark` and the agent and
known revision in `harness`. Do not infer an evaluation date or fill missing
results with zero. `reference-only` sources cannot supply routing claims.
Use a project-local index file for private research; it is not merged into the
shipped asset automatically.

From a source checkout, regenerate and check the maintained reference:

```sh
python3 .agents/skills/ultra-delegation/scripts/capability_index.py --write-docs
python3 .agents/skills/ultra-delegation/scripts/capability_index.py --check
```

The checked-in reference uses `reviewed_on` for reproducibility. Freshness reports
use today's date (or an explicit `--as-of YYYY-MM-DD` for replay). The check proves
that the docs match the JSON; it does not reverify web content. Claims are curated,
not scraped into executable policy. Oversized descriptions fail explicitly
instead of silently dropping research to fit the routing payload.

## Lessons retained from the Pi router review

Keep short explanations for a selected route and use explicit host usage events
when the host exposes them. An ongoing session's cache may affect switch costs;
isolated workers do not automatically share that cache. The inspected Pi router
revision was `5ca26ca1dac255252d9a83341dec0813301c8f97`. No code or model tiers were
copied. Native usage remains unknown when the host supplies no billing data;
provider price tables are not measured native cost.

## Efficiency hints

`assets/efficiency-hints.json` carries a separate, dated relative ordering of
published standard OpenAI API input/output rates. Both rates ascend in this
snapshot: Luna, Terra, Sol, GPT-5.5, Astra. The source model pages are recorded
per entry. This is a price-order hint for comparable token use, not a measured
Codex cost, a latency ranking, or a claim that native efforts use equal tokens.
Sol's published pricing is promotional through at least November 21, 2026.
Recheck source prices when refreshing the hints; do not derive hints from ECI.

`pilot_codex.py prepare` attaches exact model/effort hints (model-level fallback
when effort is null); `--efficiency-hints FILE` permits a reviewed alternative.
Selection only uses a complete, current, same-basis set. Stale (>180 days), future,
or missing hints cause history/fit fallback, never an invented price. Original
URLs remain in the explicit packet; ledger records retain only rank, basis,
check date and status. The legacy lower-level builder does not silently add hints.
