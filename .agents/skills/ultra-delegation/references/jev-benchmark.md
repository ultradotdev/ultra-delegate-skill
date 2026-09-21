# Quantitative downstream routing benchmark

`jev_benchmark.py` replays the production router offline against explicitly supplied captured Jev answers and independent downstream worker assessments. It creates a standard JSON report and a readable Markdown report. It never reads credentials, calls a service, starts workers, accepts outputs, promotes profiles, or writes worker learning.

## Run the demo and inspect the input contract

From the repository root:

```sh
python3 .agents/skills/ultra-delegation/scripts/jev_benchmark.py \
  --demo --output-prefix /tmp/jev-routing-demo \
  --emit-demo-input /tmp/jev-routing-demo-input.json
```

From an installed skill, use `scripts/jev_benchmark.py` relative to that skill directory. Output files are `/tmp/jev-routing-demo.json` and `/tmp/jev-routing-demo.md`. Existing output files are never overwritten. Dataset input reads are bounded to 64 MiB, matching the explicit capture collector. `--emit-demo-input` emits a complete, valid example packet rather than an abbreviated JSON sketch.

The demo contains eight authored synthetic cases, two task families, two workers per case, ambiguous requests, defective requirement coverage, unknown costs and separate calibration/test groups. All answers, assessments, timings and costs in the demo are fixture values. They are not observed API or worker results, even where the example cost field demonstrates the `measured` schema variant. The report is marked `synthetic-demo`, qualification remains pending, and there is no deployment recommendation or realized savings claim. It is useful for demonstrating the measurement interface in a video; it cannot support a performance or savings claim.

Evaluate an independently collected dataset:

```sh
python3 .agents/skills/ultra-delegation/scripts/jev_benchmark.py \
  --input /path/to/benchmark-input.json --output-prefix /tmp/jev-routing-results
```

## Capture actual router answers explicitly

Prepare and inspect the dataset with `capture: null` for cases awaiting inference. Use the separate opt-in collector after enabling project summary sharing and Jev routing:

```sh
python3 .agents/skills/ultra-delegation/scripts/jev_benchmark_capture.py \
  --input /path/to/benchmark-input.json --output /tmp/benchmark-captured.json \
  --root /path/to/project/.ultra-delegation --live
python3 .agents/skills/ultra-delegation/scripts/jev_benchmark.py \
  --input /tmp/benchmark-captured.json --output-prefix /tmp/jev-routing-results
```

The collector reads the existing environment credential or configured credential-store entry. It never creates or changes a credential. It submits the ordinary production routing payload only: task summary, requirements, signature and candidate metadata. Downstream artifact assessments, costs and reviewer references stay local. Capturing predictions does not execute workers or establish reference quality. Missing credentials or unavailable captures leave qualification pending. Inspect the collector's CLI help for the exact project-root convention and status output.

Without `--live`, collection previews availability without credential lookup or network activity. Live collection requires a new output filename and limits newly captured cases to 20 by default (`--max-calls` changes that bound). It stops on a service/authentication failure. The dataset policy must match the project policy, except that project shadow routing is represented as active recommendation replay in the dataset. The dataset is a private local input containing your explicit task summaries; publish only the sanitized report after review. Existing captures must still match the exact payload or the collector rejects them.

## Input and evidence contract

The versioned root object has these required fields:

| Field | Contract |
|---|---|
| `schema` | `ultra-delegation-benchmark-v1` |
| `dataset_id` | Public machine label, no user prompt or sensitive text |
| `synthetic` | Boolean; synthetic references cannot appear in a real dataset |
| `policy` | Complete production policy, with Jev routing `active`; used only for local replay |
| `rubric` | Predeclared `version`, `minimum_scores` for coverage/scope/evidence/clarity, and overall `quality_floor`, all on a 0–100 scale |
| `risk_target` | Predeclared `max_false_acceptance_upper` in 0–1 and positive integer `minimum_labeled_groups` |
| `thresholds` | At most twenty distinct experimental operating thresholds in `(0.5, 1]` |
| `cases` | Explicit cases with unique IDs; packet content remains local unless separately submitted through the capture workflow |

Each case contains `id`, `group_id`, `split` (`calibration` or `test`), the ordinary `packet` accepted by `jev.route`, `capture`, `preparation_cost`, and `observations`. Related variations of the same underlying task must share a `group_id`; a group crossing splits is rejected. The tool cannot discover undisclosed near-duplicates, biased sampling, or invalid reviewer assertions. Audit those before claiming independent evidence. The task family comes from the authoritative packet signature and drives report breakdowns.

A capture may be `null`, which records an unavailable inference rather than substituting a prediction. A populated capture contains:

- `payload_hash`: SHA-256 from `jev.hash_value(payload)` over the exact API payload, including model, questions, ordered candidate cards and task state.
- `response`: the validated response shape expected by the existing transport, including pinned model, exact question answer coverage and usage.
- `latency_ms`: observed router request latency.
- `cost`: `{ "kind": "measured" | "estimated" | "unknown", "usd": number | null }`.

The replay callback injects this capture into the actual `jev.route` function. No separate benchmark selector is substituted. A changed packet, question, model, evidence tier or candidate ordering causing a different payload fails the hash check. Freshness is reevaluated at run time; old captures can require a new capture after evidence expires. Record a report at collection time for historical reproducibility. Changing only the numerical operating threshold does not change today's questions or payload.

Each downstream observation names an exact `profile_id` from the packet and a SHA-256 `artifact_hash`. It supplies observed `gates` (`id`, `mandatory`, `passed`), all four rubric `scores`, machine-label `critical_failures`, and a `reviewer` object (`id`, `independent: true`, `kind: human | frontier | synthetic`). A real dataset requires human or frontier references. At least one mandatory gate is required. `costs` separately identifies worker, retry and review costs. `latency_ms` represents observed downstream elapsed time including the relevant worker/retry/review work; it may be null.

Predeclare concrete requirements, the mandatory validations, rubric version and critical-defect definitions before observing candidates. Keep those detailed assessment instructions and artifacts in the evaluation record referenced by the reviewer/artifact identifiers. The benchmark deliberately excludes their contents from its report. Have the independent reviewer evaluate each artifact blind to worker identity and cost. Do not use Jev's shadow assessment as the reference. An assertion of independence in JSON is provenance supplied by the operator, not verification performed by this script.

An output passes only when all mandatory gates pass, no critical failure is recorded, **every dimension reaches its own minimum**, and the overall mean reaches the quality floor. Excellent clarity cannot compensate for missing functionality. These assessments remain benchmark observations; they do not update authoritative worker acceptance or catalogs.

## Threshold selection and held-out testing

The script sweeps thresholds on calibration cases only, replaying the production ambiguity, coordinator-ownership and candidate-suitability checks together. It measures an operating curve; it does **not** claim that Jev's semantic suitability score is a calibrated probability of downstream worker success.

Threshold-selection evidence comes only from the `summary.inference_evaluated` subset: cases whose replay actually consulted an available captured Jev inference. Only resulting dispatches contribute risk groups. Direct user-selected and project-pinned routes remain in overall production-policy comparisons, but cannot supply evidence for a Jev threshold. An all-pinned calibration set produces no candidate threshold.

A candidate threshold must have complete labels for all its inference-evaluated dispatches, the predeclared minimum number of unique fully labeled groups, and a Wilson 95% interval upper bound on group failure risk at or below the target. This is the upper endpoint of a two-sided 95% Wilson interval, more conservative than a one-sided 95% bound. A group is counted once, has at least one dispatch, and must have independent labels for every dispatch in that group. Any failed dispatch makes the group fail. Repeating a case within a group cannot increase the effective sample size. Among candidates passing this filter, selection minimizes group failure rate, maximizes the number of passing groups, then prefers the higher threshold. Cost does not buy permission to miss the quality constraint.

If no threshold clears that filter, `candidate_threshold` is null. The held-out test still evaluates the original policy threshold, frozen before inspecting test labels. Otherwise it evaluates the calibration candidate once. Synthetic inputs always have a null candidate recommendation. Neither a passing calibration filter nor a held-out estimate automatically authorizes deployment. Risk targets, representative sampling, sample size, repeated threshold-search effects, independence and external evidence review remain prerequisites for a qualification decision.

## Report interpretation

Both artifacts identify the dataset, input and policy hashes, model, rubric, experimental thresholds and qualification status. The JSON additionally reports per-case profile choices, numerical probabilities, reason codes, artifact/reviewer provenance and task-family summaries. Summaries and excerpts, captured raw responses, credentials and worker identities beyond profile IDs are excluded from reports.

Every rate includes numerator, denominator and Wilson 95% interval. Case-level intervals are descriptive under an IID assumption. Separate `group_failure_risk` and `group_label_coverage` metrics report unique fully labeled groups. Overall metrics include bypasses; threshold safety uses the group risk interval within `summary.inference_evaluated` only. A zero denominator produces null, not zero. Metrics include dispatch coverage, abstention, independent label coverage, quality pass and failed dispatches. Missing worker outcomes are visible and excluded from quality denominators.

The three strategies are Jev, the production ranking baseline, and cheapest eligible based on **preexisting routing evidence cost**, not test outcome costs. Explicit user/project choices and deterministic coordinator/context stops are honored. The cheapest comparator requires known historical costs and does not imply evidence-based dispatch approval. Baseline provisional selections are comparisons only, not executable decisions.

Under-routing is reported only when the selected Jev worker fails an independent assessment and the observed comparator passes. Over-routing compares total cost only when both observed outputs pass and both costs are known. Missing comparator outcomes are never invented. Route disagreement includes abstention differences.

Worker, retry, review, packet preparation and router costs are combined. If any component is unknown, the corresponding total remains unknown. The report separately identifies the known subset and its size. A token-priced router estimate makes the total estimated. Paired passing cost differences are counterfactual replay comparisons, **not realized savings**. They can be positive or negative. Abstentions have no invented coordinator cost; compare dispatch coverage alongside costs. Unobserved fallback and packet-preparation latency prevent an end-to-end latency claim. Median and p95 worker-plus-router latency describe only known observations.

`router_and_preparation_cost` covers every case, including abstentions. `selected_dispatch_cost` covers dispatched cases only. The whole-workload `total_cost` stays unknown when any fallback is unobserved, even if all dispatched workers have known costs. Do not add the overhead subtotal to dispatch totals again; dispatched totals already include it. Per-artifact scores, gate verdicts, and critical-failure codes make the downstream verdict auditable without publishing artifact contents.

Case-level Wilson intervals assume independent cases; repeated tasks and related families can violate that assumption. The threshold filter instead uses unique groups as its sampling unit and the conservative any-failure group outcome. Group-level Wilson intervals still assume groups are independent; shared tasks must not be assigned separate groups. Family breakdowns are descriptive and do not prove independence. A video proof point should show real held-out dispatch counts, quality bounds, coverage, paired cost denominators and qualification limitations together.
