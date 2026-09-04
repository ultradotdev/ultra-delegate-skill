# Beta qualification — 1.2.0-beta.1

Qualification date: 2026-09-04. This is a scoped implementation report, not a certification of every host or model.

## Executed checks

- 78 passing dependency-free unit and integration tests on macOS with Python 3.14.6. Coverage includes canonical/legacy evidence, gates and project floors, model/thinking/prompt isolation, cost completeness and cached/thinking tokens, trust-but-verify imports, quarantine, freshness, output safety, and local exclusions.
- Simulated resource-pressure and timeout tests, unified/discrete memory accounting, unknown footprint rejection, cross-process concurrency, and process-exit lease recovery. No machine-exhaustion test or local inference was performed.
- Official `quick_validate.py` skill validation passed. PyYAML was used only by that external validator; the distributed helper remains dependency-free.
- Allowlisted deterministic skill packaging and extracted-archive init/validate tests. The clean source archive excludes existing Git history and unrelated host configuration.

Reproduce from the source archive:

```sh
python3 -B -m unittest discover -s tests -v
python3 -B scripts/build_release.py --check --source
python3 -B scripts/demo_learning.py
```

CI defines additional Python versions. A configured CI job is not evidence it has run; only the local version above was exercised here.

## Delegation value report

This implementation used Codex-native subagents for bounded evidence, resource-control, packaging, and safety-review tasks. The coordinator integrated the work and ran the combined deterministic checks. Review found and repaired imported-prior gate-count, confidence, and exact-profile identity defects.

Worker profiles inherited the coordinator configuration; this was **not** a controlled cheaper-model or thinking-budget bakeoff. Token cost, experiment savings, latency comparisons, and break-even count are **unavailable**. No preferred model recommendation was created from this implementation work.

## Not yet qualified

- Clean-context host/model/thinking comparisons with real accepted code changes across Codex, Claude Code, and OpenCode. Supplied templates and documentation remain experimental.
- End-to-end Cortex graph reinforcement and reuse.
- Any local execution adapter. Preflight and monitor decisions are tested, but actual runtime limits and owned-request cancellation are not implemented. Local execution remains disabled by default and unsupported even after policy opt-in.
- The automated learning demonstration uses explicitly synthetic fixtures. It verifies bookkeeping and portability, not model quality or savings.

The release gate permits only these scoped claims. Do not advertise unexercised combinations as verified or use synthetic reports as performance evidence.

## Publication boundary

A filename-only review found unrelated Cortex and host configuration in the development repository and its history. Do not push that history as the public release. Publish only the reviewed clean source archive into the intended repository, after reviewing its contents and checksums. Publication and live skill installation have not been performed by this implementation.
