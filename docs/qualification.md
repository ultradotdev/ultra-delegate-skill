# Active routing status: 1.3.0-rc.6

RC6 implements active Jev routing for an eligible worker on the first task after
project setup. It does not require a qualification certificate, a minimum number
of prior outcomes, a routing shadow phase, or a statistical release threshold.
Historical qualification records below remain audit context only.

The bounded live routing check used the same task data twice. Question wording v4
returned `clarify` for all 12 of 12 requests. After the v5 two-question wording
revision, 11 of 12 requests returned `route` and one returned
`no-suitable-candidate`.

The [active recovery validation](active-recovery-validation.md) and its
[recorded results](active-recovery-results.json) contain 12 task cards and 11
accepted native requests. Six primary attempts succeeded. Three primary failures
were accepted through comparison, and two later recovery paths covered a preserved
coordinator dispatch mismatch corrected to Luna and an A-to-B-to-A portability
defect fixed by Luna fallback after both initial results missed it. Eight native
invocations and 23 task attempts, including the mismatch, are recorded. The
batches are correlated development work, not independent samples. Security and
artifact judges were off; worker and review costs are unknown. There is no savings
or calibration claim.

Recovery, acceptance, report, learning, and malformed-input behavior have local
test coverage. The current local suite has 304 passing tests; six
optional-keyring archive checks pass. All 304 tests pass from the extracted archive
with and without optional keyring. Consult the PR checks for current CI status. Simulated fixtures remain distinct from the recorded native trials.

## Historical RC5 routing-design correction

### Routing-design correction: 1.3.0-rc.5

An implementation audit found that the pilot used reasoning, interaction and
synthesis signals as a global complexity veto, whereas the design called for
candidate-specific evidence and review requirements. RC5 corrects that rule,
keeps task-kind classification diagnostic, derives cohort descriptions from
recorded outcome metadata, and rejects active observations outside selected or
nominated configurations. Old decisions require reevaluation; old outcomes are
not silently given new demand qualifications.

An offline replay verified the exact original payload hash and reused its
recorded Jev answers. The recommendation changed from `repackage` to reviewed
experiment proposals for Terra and Luna with interaction/synthesis review gates.
There were zero new HTTP calls, worker executions or accepted outcomes. This
isolates the deterministic rule correction, not improved live model selection.
The original trial and its failed routing expectation remain historical records.

All 246 tests pass locally and from the extracted source archive with site
packages disabled. Six archive tests pass with optional keyring installed. Python
3.10 grammar checks pass for 42 files; generated references, skill validation and
deterministic archive checks pass.

Validation covers routine interaction, uncertain demands, relevant proof versus
generic successes, retained failures, independent band overrides, actual cohort
counts, active/shadow acceptance separation, blocked active outcomes, current
policy rechecks and report privacy/clarity. The generated atomic question wording
is unchanged; its consumption metadata and version now reflect the new rule.
Current automated and packaging results are tracked on
[PR 4](https://github.com/ultradotdev/ultra-delegate-skill/pull/4).

The [demand contract](../.agents/skills/ultra-delegation/references/pilot-demands.md)
documents both corrected behavior and remaining design gaps: full-path cost and
latency optimization, calibrated thresholds, broader semantic evidence retrieval,
and automatic trial scheduling. The pilot is not the full proposed design.
No live installation or publication was performed.

# Native repository readiness: 1.3.0-rc.4

PR 3 merged at `5a7e79d584c9cea11aa6284cfa0b13960c0a7206` after its
Python 3.10/3.12/3.14 and optional-keyring Linux/macOS/Windows CI passed.
This unreleased candidate is tracked in
[PR 4](https://github.com/ultradotdev/ultra-delegate-skill/pull/4), including remote
results for each subsequent commit. It has not been installed or published.

Local validation passes 226 tests on macOS Python 3.14, also from the extracted
source archive with site packages disabled. These cover the native
output opt-in, strict defaults, unknown-context stop, required completeness gate,
exact host/catalog effort intersection, read-only packet tool policy, CLI recheck,
policy changes and null-capacity reporting, alongside all existing regressions.
Extracted archives are checked with site packages disabled and with optional
keyring installed. The packaged helper supports isolated Python execution.
Python 3.10 grammar checks pass for 41 Python files, and the official skill validator
passes. Generated question references and deterministic packaging checks pass. Historical
CI results do not substitute for this candidate's current PR checks.

Seven live Jev requests completed. Requests 1–2 found/diagnosed the rounded Score
mismatch; their billing is unknown. Request 3 validated the transport correction
but returned `clarify` for the original synthetic test packet (missing-requirement
probability 0.22 versus the unchanged 0.20 cutoff). That failed expectation remains
recorded. An earlier stalled credential read made no HTTP request and was stopped.
The native macOS read resolved the Keychain blocker without changing an item or
its permissions. Credential reads now have a separate five-second deadline.

Requests 4–6 used authored fixture version `repo-smoke-2`: explicit namespace and
output requirements produced `experiment`; missing requirements produced
`clarify`; missing document authorization produced advisory security `fail`.
All three expected actions passed. These fixtures were refined after observing
version 1, so they are not a held-out benchmark. No threshold changed.

Request 7 evaluated a prepared summary for an actual read-only Python CLI review.
The candidate packet used currently discovered Terra/Luna medium configurations,
known effective context of 258400 tokens and an unreported output ceiling. Explicit
host-managed-output opt-in plus a mandatory completeness gate allowed the native
Codex path without inventing a numeric output limit. Recheck passed immediately
before native Terra medium execution. Jev recommended `repackage` for greater
complexity; shadow mode preserved the configured Terra baseline. It did not select
Terra on the strength of that recommendation.

The coordinator independently checked all four source/test-cited findings, four
passing smoke tests, output completeness and unchanged source hashes. The accepted
outcome has coverage/correctness/maintainability/clarity scores 100/100/90/95. The
next independent task group sees one scoped success with Wilson lower bound
0.20655, still unqualified. This establishes one complete route/recheck/worker/
review/observe/report cycle, not comparative model quality or calibrated routing.
Security assessment was off for the real review; only the toy authorization case
exercised the live advisory evaluator.

Known token-price estimates for requests 3–7 total $0.000346836. Total workload
cost remains unknown, including the first two requests and native worker/reviewer
costs. No savings claim follows. Browser visual inspection remains pending;
HTML generation, source structure and escaping are covered by tests.

The next step is a few independent read-only repository trials in shadow mode,
including paired worker results where useful. Active-route quality, threshold
calibration, broader security accuracy and total cost comparisons remain pending.
See the [reproducible test-drive guide](pilot-test-drive.md) and packaged
[native Codex workflow](../.agents/skills/ultra-delegation/references/pilot-codex.md).

# Jev project pilot qualification: 1.3.0-rc.3

The first iteration is Python 3.10+ with local metadata ledgers and HTML/JSON telemetry. New tests exercise batched question contracts, scoped group evidence, independent acceptance gates, shadow versus active behavior, unavailable service, dispatch rechecks, redacted responses, optional nonblocking security evaluation, output escaping, and archive portability. The synthetic Yarn demo covers proposals, accepted/failed observations, confidence accumulation, security unavailability and pending results.

No real Yarn source has been evaluated by this candidate. No live Jev request, native worker bake-off, security-accuracy benchmark or threshold qualification was performed. The report's synthetic observations and prices are illustrative. Browser visual inspection of the generated local HTML was blocked by the browser URL policy; source/escaping and report-generation behavior are covered by automated checks instead.

Local validation: all 196 tests pass on macOS Python 3.14 and from the extracted source archive; all six archive checks also pass in the isolated optional-keyring environment. Python 3.10 grammar checks pass for 34 Python files. Generated references, reproducible skill/source packaging checks and the official skill validator pass. An independent forward test exercised the documented offline CLI workflow, rejected an incomplete outcome form, and confirmed recheck, security-off and pending-cost behavior. Actual Python 3.10 execution and new remote CI remain pending; historical results below do not establish this candidate's live quality.

# Jev evaluation infrastructure qualification: 1.3.0-rc.2

Date: 2026-09-20. This is local implementation qualification, not live routing-quality evidence.

- All 158 tests pass locally on macOS Python 3.14 and from the extracted source archive. Python 3.10 grammar checks pass; actual candidate remote Python/OS CI remains pending.
- Six archive checks pass with site packages disabled and with optional keyring installed. The official skill validator passes.
- Generated references are checked against the production payload builders and current field projection.
- The standard benchmark runs offline with synthetic captures and independently labeled downstream observations supplied by the operator. Its demo remains synthetic and qualification pending.
- Threshold selection uses calibration data only; held-out labels cannot change the selected threshold. Missing captures, outcomes, or costs remain explicit.
- Downstream per-dimension floors and critical-defect vetoes prevent high clarity from compensating for missing requirements.
- Standing discovery seeds require exact host/model/effort availability. Matching reviewed outcomes can change ranking; stale/failed results require retesting. Normalized records preserve latest-failure behavior when composing a Jev packet.
- Capture tests use fake credentials and transports only. Existing/missing/unwritable output targets are rejected before requests; no real credential-store or endpoint operation was performed.
- A Terra medium read-only review found a collector output-preflight defect; output is now reserved before a paid request. No remaining concrete findings were reported after correction. An independent forward test used the documented commands to generate question docs, a benchmark report, and the standing shortlist without credentials or network access.

No live Jev call or worker bake-off was run for this candidate. No threshold or model has been qualified by this work. No personal skill installation or credential was modified. Candidate CI has not run remotely.

Reproduce the synthetic report:

```sh
python3 .agents/skills/ultra-delegation/scripts/jev_benchmark.py --demo --output-prefix /tmp/jev-routing-demo
python3 .agents/skills/ultra-delegation/scripts/jev_docs.py --check
python3 -B -m unittest discover -s tests -v
python3 scripts/build_release.py --check
python3 scripts/build_release.py --source --check
```

The preceding release candidate subsequently passed all 120 tests across Python 3.10/3.12/3.14 and optional-keyring packaging jobs on Linux/macOS/Windows in [PR 2](https://github.com/ultradotdev/ultra-delegate-skill/pull/2). Those results are historical and do not establish the new candidate's remote compatibility.

---

# Jev candidate qualification: 1.3.0-rc.1

Date: 2026-09-18. This candidate adds an external decision adapter while preserving the offline helper. The previous beta report follows as historical evidence, not a claim that its CI has run on this candidate.

## Candidate checks

- All 119 dependency-free tests pass locally on macOS Python 3.14, including existing regression tests and mocked Jev routing, judge, credential, transport and ledger tests.
- Extracted skill archives run with site packages disabled and in a separate temporary environment with keyring 25.7.0 installed. This tests packaging/import compatibility, not real Keychain reads or cross-platform native-store operation.
- Credential lifecycle is user-owned: tests reject all mutation commands before lookup, prove existing service/account entries are read without writes, and verify missing entries never trigger creation.
- An owned delayed transport process is terminated under a shortened test deadline. Mock HTTP checks cover retry caps, authentication errors, malformed responses, redirects and size limits.
- Official skill validation passes using PyYAML only in the isolated validation environment.
- A Codex-native Terra medium read-only review examined the adapter boundaries. Follow-up changes bound dispatch rechecks to saved decisions and kept cleanup within the request budget. Imported-prior first-use routing remains intentional and explicitly pending verification, consistent with the existing trust-but-verify contract.
- An independent Terra medium forward test exercised keyless CLI configuration, routing/judging previews, safe missing-credential behavior and mock experiment/judge behavior. Its profile-location documentation finding was corrected with an explicit requirement and complete minimal packet.
- Optional-keyring archive checks are configured for Linux, macOS and Windows CI. New remote CI results are pending; local success does not qualify all operating systems or Python versions.

## Pending qualification

No real TypeSafe endpoint request, live routing-quality benchmark, or live judge-quality benchmark was performed. No credential was requested, saved, or read from the user's OS store. The opt-in synthetic runner reports `pending` until explicitly run with access. Synthetic authored labels are not a substitute for representative independent review and held-out task families.

No installed personal skill or external provider configuration was modified. No worker was dispatched through Jev. Worker gates, acceptance and promotion remain coordinator-owned. Review cost and latency comparisons are unavailable; no savings claim is made.

Reproduce:

```sh
python3 -B -m unittest discover -s tests -v
python3 scripts/build_release.py --check
python3 scripts/build_release.py --source --check
python3 .agents/skills/ultra-delegation/scripts/jev_qualification.py
```

---

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

[Release CI](https://github.com/ultradotdev/ultra-delegate-skill/actions/runs/33914545619) passed on Linux with Python 3.10, 3.12, and 3.14, including tests and both packaging checks. These are automated helper checks, not model benchmarks.

The maintainer reports successful real-world use in Codex in another repository and in Claude Code. These reports support releasing a proof of concept; they do not supply exact model revisions, thinking settings, cost, latency, or controlled comparison evidence.

## Delegation value report

This implementation used Codex-native subagents for bounded evidence, resource-control, packaging, and safety-review tasks. The coordinator integrated the work and ran the combined deterministic checks. Review found and repaired imported-prior gate-count, confidence, and exact-profile identity defects.

Worker profiles inherited the coordinator configuration; this was **not** a controlled cheaper-model or thinking-budget bakeoff. Token cost, experiment savings, latency comparisons, and break-even count are **unavailable**. No preferred model recommendation was created from this implementation work.

## Known experimental areas

- Clean-context host/model/thinking comparisons with real accepted code changes across Codex, Claude Code, and OpenCode. Supplied templates and documentation remain experimental.
- End-to-end Cortex graph reinforcement and reuse.
- Any local execution adapter. Preflight and monitor decisions are tested, but actual runtime limits and owned-request cancellation are not implemented. Local execution remains disabled by default and unsupported even after policy opt-in.
- The automated learning demonstration uses explicitly synthetic fixtures. It verifies bookkeeping and portability, not model quality or savings.

The proof-of-concept release permits these scoped claims with the README disclaimer. Further host qualification is follow-up work, not a requirement to publish this experimental beta. Do not advertise unexercised combinations as verified or use synthetic reports as performance evidence.

## Publication boundary

A clean source snapshot has been pushed to the private review branch, and the beta was installed locally for Codex testing. The original development history and unrelated Cortex/host configuration were excluded. Public visibility is a separate owner-controlled decision. See [release audit](release-audit.md) for the content and history scan scope.
