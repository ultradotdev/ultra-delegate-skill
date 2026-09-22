# Repository trial validation: 1.3.0-rc.7

RC7 adds native packet preparation, configurable selection, workflow conveniences,
attributed research, twelve executable fixtures, and concise HTML/JSON reports.
This is development evidence for repository trials, not general model qualification.

## Implementation checks

- **377 tests pass** on local Python 3.14, including the twelve fixture contracts,
  frozen checks/reference implementations, seeded mutations, and review scoring.
- All **377 tests pass from the extracted source archive** with site packages
  disabled (`python -S`) and with optional keyring installed. Six dedicated
  optional-keyring release-package checks also pass.
- Generated legacy/pilot question references and capability-index documentation
  match runtime definitions; skill validation and Git whitespace checks pass.
- Installable and source archives pass reproducibility/allowlist checks.
- CI exercises Python 3.10, 3.12, and 3.14, optional keyring on Linux/macOS/Windows,
  and the language fixtures with Node 22.18 and Go 1.24 plus Rust. Check the PR for
  the actual remote result rather than interpreting this job list as a pass.

## What forward testing changed

The extracted-package test exposed vague default operation descriptions, ambiguous
capability-fit wording, and a cold-start policy contradiction. Required demand
still applies the experimental **0.85** fit cutoff. An *uncertain* demand now adds
an explicit independent-review gate; it does not establish that a capability must
be prequalified. Operation, scope, host, tools, permissions, and acceptance gates
remain in force. Runtime questions are `pilot-routing-v7`; selection is
`pilot-selection-v6`.

The initial parser calls abstained with no suitable candidate; those results are
retained as development failures, not relabeled as successful routing. Clarifying
supported operations improved operation matching but did not resolve fit
uncertainty. A local oversized-payload rejection led to concise questions with
explicit yes/no criteria, without silent truncation or increasing the request
limit. These were development changes on a known fixture, not held-out tuning or
calibration.

Forward tests also found and fixed report-directory creation, legacy configuration
being applied to a pilot ledger, existing empty preparation directories, global
`--root` argument spelling, and a symlink-output regression caught by independent
review. The coordinator walkthrough now includes the complete task contract and
host-observation expiry handling.

## Native trial

The [sanitized result artifact](repository-trial-results.json) contains the
reviewed outcomes, request summary, corrections, and learning-probe result.

The clean generated Python parser fixture produced a successful live route over
five available native models. Jev selected **Luna / medium** using dated efficiency
hints; automatic comparison ran **Terra / medium** in a separate proposal copy.
Both delivered patches passed root frontier review and the frozen contract checks.
Luna's initial attempt was accepted and delivered. No worker repair or fallback
was required. Worker-authored checks passed: four Luna test methods and three
Terra methods, plus two frozen contract methods with invalid-input subcases for
each implementation. Review was independent of the workers but not blinded.

The fresh coordinating agent used the extracted skill. Root assistance was needed
for host approval context, correcting an accidentally restricted one-model packet,
refreshing expired host observations, and independent frontier review. Two
completion hashes were transcribed incorrectly by the coordinator. Root verified
the actual artifacts and used the new one-time pre-review correction event; the
original hashes remain in the audit trail. A file-based hash option now avoids
manual transcription. Neither erroneous record was accepted or exported as
learning before correction. This is an assisted fresh-agent development trial,
not a claim of unattended autonomy or zero setup errors.

| Observation | Recorded result |
| --- | --- |
| Executed request | `req_136cfb067f1ce458dcf64ed8` |
| Live decision | `dec_e6f56facc93f6287d2cbcbb4` |
| Initial worker | `gpt-5.6-luna`, medium; accepted |
| Comparison worker | `gpt-5.6-terra`, medium; accepted |
| Code recovery | None needed; forced recovery is covered separately by tests |
| Record corrections | Two artifact hashes, before review; preserved in reports |
| Learning probe | `dec_d274dcea03e471e77136899c`: same selection with reviewed history |
| Immediate learning | One comparable group per exercised model; no minimum count |
| Automatic bake-off after learning | One planned attempt in an isolated replay; no additional worker launched |
| Native worker/review billing and worker-only timing | Unavailable |
| Security / artifact judging | Off; no security assurance claimed |

The parser's frozen fixture revision is
`014569373dcdb119ce43b4e7853171261de8ff3addcd9e6c9eb310c35f0838ca`.
The pre-worker input manifest binds `TASK.md` and `task.py`; the recorded Git base
names the containing repository HEAD, not a separate fixture checkout commit.
Candidate cards are generated exercises and public model descriptions. No code
artifacts were sent to Jev. Earlier attempts include a transient service failure,
host permission interruptions, and the retained abstentions described above.
These are not worker-quality observations.

The local HTML/JSON report shows the accepted task and comparison first, with
routing-only records and detailed evidence expandable. Both reviewed outcomes
remain in the sanitized ledger. The subsequent learning probe is diagnostic
routing evidence only, not another independent worker success.

## Limits and next measurements

The research snapshot contains **266 Epoch model rows and five exact native
mappings**. Full research coverage does not make other providers executable.
Source dates, unknown evaluation dates, 90% intervals, and attribution are retained.
Relative API-price hints are dated 2026-09-21; they are not native billed costs.
Artificial Analysis is excluded.

The complete **12-case live paired Epoch campaign remains pending**, including the
development threshold sweep and frozen held-out evaluation. The fixture/reference
checks establish the harness, not worker performance. The default 0.85 threshold
is experimental. No general quality rate, security accuracy, Epoch routing benefit,
or native cost savings is established by this iteration. Natural worker results,
controlled failure tests, and replay diagnostics remain separate.

The live installed skill was not changed. RC7 and the portable Yarn handoff are
release candidates prepared for review; packaging does not publish a release.
