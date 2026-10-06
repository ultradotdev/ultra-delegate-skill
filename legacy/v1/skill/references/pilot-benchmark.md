# Practical pilot evaluation

`scripts/pilot_benchmark.py` is an opt-in harness for the current pilot. It does
not launch workers, alter project ledgers, certify routing, or claim savings. It
validates prepared cases, runs offline/simulated/live routing, incorporates only
supplied independently reviewed outcomes, and writes HTML, JSON, and CSV.

Create a manifest with `init`, then add real bounded tasks: four each for review,
tests, and implementation. The generated twelve-case `example` is synthetic
template material only. Its review, test-authoring, and implementation families
carry distinct explicit boundary contracts rather than inheriting a generic
patch boundary. Keep related variants in one `group_id`; groups cannot
cross the development/test split. Evidence for an evaluation group must predate
its packet and cannot come from any group in the same evaluation set. Store real
worker artifacts and reviews outside the manifest; the manifest contains only the
allowlisted prepared packet, evidence, reference action, and reviewed outcome
record.

```sh
python3 "$SKILL_PATH/scripts/pilot_benchmark.py" init --output benchmark.json
python3 "$SKILL_PATH/scripts/pilot_benchmark.py" example --output benchmark-template.json
python3 "$SKILL_PATH/scripts/pilot_benchmark.py" run \
  --input benchmark-template.json --output-dir benchmark-simulated --simulate
```

`example` and `--simulate` use synthetic packets and deterministic responses.
They validate workflow measurement only. They are not live Jev calls, native
worker executions, outcome evidence, or a recommendation for Yarn.

Every case uses `prepared_packet` (the older `packet` spelling remains a temporary
transition input), `evidence`, `reference`, and `outcomes`. A reference records
its action, independent reviewer identity/provenance, candidate-order blinding,
and timestamp; optional judge action is advisory beside that independent blinded
reference. For a real trial, prepare non-synthetic cases with fresh packets, a
project policy, optional historical evidence, and independently reviewed worker
outcomes bound to the returned decision input hash. Use `--live` only after the
project explicitly permits summary sharing; it rejects every synthetic packet.
`--simulate` accepts only synthetic packets. Without either, routing remains
offline and selected worker outcomes may remain pending.

```sh
python3 "$SKILL_PATH/scripts/pilot_benchmark.py" run \
  --input real-benchmark.json --output-dir benchmark-real --live
```

Each run writes `report.json`, `report.html`, `observations.csv`,
`observed-outcomes.svg`, and a durable `case-progress-NNN.json` after each case.
Use `report --input REPORT --output-dir DIR` to render a saved report again. The
report separates routing/reference agreement, selected-worker outcomes,
worker-results-pending, independent group count, and observed comparisons.
Agreement with a reference reviewer is diagnostic, not ground truth. Unknown
costs, unrun workers, and missing reviews stay unknown or pending. Do not turn the
small sample, synthetic templates, or a favorable reference-agreement count into a
release gate, population reliability claim, or realized savings assertion.
