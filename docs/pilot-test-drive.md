# Repository pilot test drive

Run these commands from the source checkout or extracted source archive. They
exercise the experimental v2 `pilot.py` workflow. Use a fresh output directory
each time. None of the synthetic configurations qualifies a real worker.

```sh
# No credentials, network, workers, or optional dependencies.
python3 -I -S scripts/pilot_smoke.py --output-dir /tmp/jev-smoke-offline

# Contract, subprocess integration, and bounded smoke-runner tests.
python3 -m unittest discover -s tests -p 'test_pilot*.py'

# Full suite, generated documentation, and reproducible archives.
python3 -m unittest discover -s tests
python3 .agents/skills/ultra-delegation/scripts/pilot_questions.py --check
python3 scripts/build_release.py --check
python3 scripts/build_release.py --source --check
```

Fixture version `repo-smoke-2` uses three authored examples: a fully specified Python test draft,
input validation with missing requirements, and a toy document endpoint missing
authorization. Expected results are respectively an experiment nomination,
clarification, and an advisory security failure. Offline answers are mocked to
test orchestration; they say nothing about Jev accuracy.

`smoke.json` records expected/observed results, call count, provenance and pending
cases. Its linked pilot HTML/JSON report contains routing telemetry. The separate
`security.json` contains the advisory result, when reached. No workers execute and
no downstream quality or savings claim follows from these examples.

## Explicit live option

Inspect the synthetic fixtures and generated previews before opting in. A live
run shares only those authored examples. It creates an isolated policy under the
new output directory with summary and artifact sharing enabled; it does not
change another project's policy. It reserves that directory before looking up
credentials or making requests.

```sh
python3 scripts/pilot_smoke.py --output-dir /tmp/jev-smoke-live --live \
  --credential-locator /path/to/credential-locator.json
```

The optional locator is a JSON object containing only `credential_service` and
`credential_ref`, the service and account names of an existing secure store entry.
Never put the key in that file. `TYPESAFE_API_KEY` takes precedence. Without the
locator the existing default service/account apply. The adapter only reads
credentials; the user manages the store. Saving a key enables nothing by itself.

Each live run reserves at most three HTTP attempts with retries disabled. Missing
credentials leave the run pending; an unavailable routing response stops the
remaining scenarios. Re-running requires a fresh directory and a new paid-call
budget. An exit status of zero means the report was written: inspect `status`,
`passed` and each case, rather than interpreting process success as qualification.

## Observable behavior and executable specifications

| Contract | Coverage |
| --- | --- |
| User selection cannot bypass context freshness, delegation stop, tools or capacity | `test_pilot_spec.py` |
| Current group and mismatched risk/work/complexity cannot supply qualification evidence | `test_pilot_spec.py` |
| Five successful groups remain below the default Wilson confidence floor; ten cross it | `test_pilot_spec.py` |
| Missing requirements, coordinator coupling and greater impact cause semantic stops | `test_pilot_spec.py` |
| Shadow recommendations retain the baseline; active mode applies semantic stops | `test_pilot_spec.py` |
| Unknown capacity and changed candidate order preserve hard boundaries | `test_pilot_spec.py`, `test_pilot_integration.py` |
| Incomplete/duplicate observations reject; failed mandatory gate vetoes favorable quality scores | `test_pilot_integration.py` |
| Synthetic decisions cannot authorize dispatch; unavailable optional security does not block observation | `test_pilot_integration.py` |
| Output reservation precedes paid work; credentials/errors remain redacted; live retries are disabled | `test_pilot_smoke.py`, `test_jev.py` |

`action` is the effective decision; `recommended_action` is Jev's suggestion.
Neither launches a worker. `dispatch_authorized: false` remains false until a
separate native-host workflow validates `recheck`. Synthetic packets always fail
that recheck. Demo "independent" review fields are generated fixture data, not
actual human or frontier assessments.

## Live response compatibility finding

The first limited live test returned `invalid-response`. A second, separately
budgeted diagnostic isolated a valid four-level Score with probabilities
`[0.97, 0.03, 0, 0]` and scalar score `0.04`. The displayed probabilities imply
`0.03`; this discrepancy is compatible with independent two-decimal rounding.
The API describes Score as a probability-weighted value but does not specify a
wire precision guarantee ([TypeSafe API reference](https://docs.typesafe.ai/api)).

Validation now allows only differences feasible under rounding each probability
and the scalar to hundredths, constrained to a unit-mass distribution. It retains
the strict check for higher precision responses, exact model/question/legend
checks, finite ranges and the original probability-sum check. It neither
normalizes probabilities nor changes routing thresholds. Pilot decisions use the
distribution; the legacy shadow judge may display the validated scalar.

This is a bounded compatibility policy supported by one diagnostic, not a claim
that the vendor guarantees rounding behavior. A materially inconsistent score or
distribution still fails closed to the baseline. Regression tests retain both
the observed success case and malformed-response counterexamples.

## Readiness follow-up

The bounded native macOS read resolved the Python Keychain wait. The third live
request successfully validated the rounded Score response, but the original
bounded-test packet returned `clarify`: missing-requirement probability `0.22`
exceeded the unchanged `0.20` cutoff. That failed expectation remains part of the
qualification record. Fixture version 2 explicitly supplies the test symbol's
namespace and exact output shape; a new result cannot retroactively pass version 1
or establish held-out accuracy.

Repo readiness requires successful access/transport, observed semantic smoke
results, an actual native-worker/reviewer cycle and an attributable report. Broad
quality/security accuracy and calibrated thresholds require subsequent independent
repo tasks; they are not established by these synthetic checks.

Native-host discovery remains a concrete integration gap: the observed Codex
catalog exposes context size but no output-token ceiling. The current automatic
dispatch gate requires both and correctly returns `unknown-capacity`. Do not fill
this with an invented number. A separately supervised advisory workflow must be
explicit about coordinator ownership and cannot claim the automatic gate passed.
