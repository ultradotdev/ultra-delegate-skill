# Jev live pilot — 2026-09-28

The minimal routing core and native demonstration are implemented. The recovery
pilot delivered an independently accepted artifact, but **complete cost accounting
has not been established**. The four matched pairs have not run. No routing cost
advantage or model-quality ranking is established.

## Pilot observations

The first attempt was deliberately instructed to leave the defective source
unchanged. Its failure tests recovery plumbing; it is not a natural worker error.
The second route received those findings, selected a different configuration, and
produced a passing repair. Integration used the exact reviewed bytes.

| Observed call | Configuration | Input | Cached input | Output | API-equivalent USD |
|---|---|---:|---:|---:|---:|
| Initial route | Jev 1.13.0 | 1,739 | 0 | 51 | 0.000073038 |
| Scripted no-op worker | GPT-6 Luna / medium | 19,216 | 11,008 | 9 | 0.000935380 |
| Recovery route | Jev 1.13.0 | 1,954 | 0 | 50 | 0.000082068 |
| Repair worker | GPT-6 Sol / medium | 212,379 | 199,936 | 1,546 | 0.080333200 |

Observed subtotal: **$0.081423686**, with 235,288 input tokens, 210,944 cached
input tokens, 1,656 output tokens, and 138 reasoning tokens already included in
output. Exposed cache-write counts were zero. Worker execution elapsed time summed
to 77.97 seconds. Request elapsed time was 219.79 seconds, including credential
recovery. One task was accepted after two attempts; first-attempt acceptance was
zero by construction.

An earlier credential lookup failed before any model call. That intent remains
recorded and was reconciled as not sent; the user supplied the correct existing
account. No credential was created, replaced, enumerated, or recorded in output.

## Accounting limitation

The repair worker emitted seven automatic permission-review completions. The
public completion events expose no token counters, and the evidence does not
establish whether their usage is included in worker totals. Their cost remains
unknown. The pilot report therefore marks accounting incomplete, total cost
unknown, and cost per accepted result unknown. The original premature complete
report is retained as `report-before-approval-audit` for auditability; the current
`report.json` and `report.md` supersede it.

One separately approved Luna/medium telemetry diagnostic completed in 8.21 seconds.
Its public worker totals were 38,509 input, 29,184 cached input, 174 output, and 92
reasoning tokens included in output: $0.001311340 of observed worker usage at the
frozen rates. This is diagnostic overhead, excluded from the pilot and future
paired task costs.

The diagnostic is **inconclusive**, not proof that the host cannot export usage:
it triggered zero automatic reviews, and our collector crashed on valid null
OTel bodies, saving no exported counters. The collector now discards body text,
accepts null bodies, reports malformed requests, and has a local synthetic HTTP
regression test. No paid rerun was made. A versioned second diagnostic is prepared
to request approval for one synthetic marker read without changing host safeguards.

A successful diagnostic would still not retroactively fill the original pilot's
missing review usage. A fully measured replacement pilot would be required before
the four-pair campaign. Unknown implementation/research overhead from the main
chat is also reported separately, never as zero.

## Evidence and next checkpoint

Durable ignored evidence is under `.ultra-delegation/rebuild/`: pilot decisions,
native receipts and events, captured artifacts, independent reviews, integration
records, the SQLite ledger, current reports, and `otel-probe-v1/result.json`.
The old implementation and experiment snapshots remain recoverable. The active
skill release contains only its entry point, agent metadata, contract, and helper.

Four frozen fixtures were validated against their correct references and defective
starters. Tests cover routing errors, interrupted dispatch, recovery history,
artifact/review binding, accounting gaps and overlaps, evaluator consistency,
and release isolation. These software checks are not experimental acceptance data.

Next: establish exported usage for an actual permission review, its exact model
and applicable pricing, and non-overlapping worker/reviewer coverage. Then run a
new fully measured pilot; expand to the four pairs only if that gate passes.
The prepared diagnostic is `python3 experiments/probe_telemetry.py --revision v2`.
It is not authorized by the already-consumed single-diagnostic approval.

Rates are the dated Standard API-equivalent snapshot in
`experiments/pricing-2026-09-28.json`, based on the official
[OpenAI pricing](https://developers.openai.com/api/docs/pricing) and
[TypeSafe model pricing](https://docs.typesafe.ai/models). API equivalents are
not subscription charges. Capture uses the public
[Codex app-server protocol](https://developers.openai.com/codex/app-server) and
[documented OTel exporter](https://learn.chatgpt.com/docs/agent-approvals-security);
no private host session stores were read.
