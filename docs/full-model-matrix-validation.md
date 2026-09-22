# Complete native model matrix — 2026-09-22

All twelve frozen Python, TypeScript, Go and Rust tasks were executed on every
currently available native model at **medium effort**. This is 60 distinct
task/configuration cells: 24 original executions reused and 36 new executions.
Reused results retain their original failures; they are not additional samples.

| Model | Accepted / 12 | Review defects missed |
| --- | ---: | ---: |
| GPT-5.6 Luna | 10 | 2 |
| GPT-5.6 Terra | 11 | 1 |
| GPT-5.6 Sol | 12 | 0 |
| GPT-5.5 | 12 | 0 |
| GPT-6 Astra | 12 | 0 |

All 20 implementation submissions passed the frozen behavioral checks. All 20
test-writing submissions passed the correct implementation and killed every
seeded behavioral mutant: 65/65 mutant executions. Every output was independently
reviewed against the same rubric. New outputs were reviewed by fresh Astra medium
agents using opaque artifact copies with worker identity and cost withheld.
The coordinator retains final acceptance. An independent artifact audit checked
all 60 cells, review/score consistency, native completion handles and manifests.

The rejected outputs were Luna's Python transfer review, Terra's Python transfer
review, and Luna's TypeScript cache review. The first two missed same-account
balance inflation; the third missed premature idle during overlapping refreshes.
Luna's Python review additionally contained an unsupported balance-restoration
claim and duplicate finding. A passing comparator never erases those failures.

[Machine-readable results](full-model-matrix-results.json) preserve every cell,
its original artifact hash, score, native task handle, and reuse status. The
underlying worker artifacts, gate logs, blind review dossiers and HTML matrix are
retained in the local evaluation directory, outside release packages.

This is one observation per task/model, on twelve small exercises. It does not
establish a general model ranking or reliable success rate. All twelve tasks have
now been exposed; later question changes cannot treat them as fresh held-out
cases. Native task handles are coordinator-attested references to actual tool
calls, not signed model or billing receipts. Elapsed times include scheduling,
tools and coordinator observation delays, so they do not rank model speed.
Worker/reviewer billing is unavailable; no savings are claimed. Security checks
were off. No code or worker artifacts were sent to Jev.

The original paired Epoch routing campaign made 24 calls. Its suitability sweep
at 0.80, 0.85, 0.90 and 0.95 made identical development selections: 0.85 remains
experimental and the sweep was inconclusive. The complete matrix expands native
execution coverage; it does not create additional independent routing calls.
See [the coordinator-gate experiment](coordinator-dependency-validation.md) for
the subsequent question and cutoff work.
