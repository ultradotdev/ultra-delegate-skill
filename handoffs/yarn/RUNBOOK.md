# Local runbook

Run shell commands from the Yarn repository root. Extract this bundle somewhere readable; no global skill installation is necessary. Set `HANDOFF_DIR` to the extracted `yarn-agent-handoff` directory using an absolute path.

```sh
HANDOFF_DIR=/absolute/path/to/yarn-agent-handoff
SKILL_PATH="$HANDOFF_DIR/runtime/ultra-delegation"
python3 --version
python3 "$SKILL_PATH/scripts/pilot.py" --help
python3 "$SKILL_PATH/scripts/pilot_questions.py" --check
```

Python 3.10+ is required. Offline commands have no third-party Python dependency. OS credential lookup needs optional `keyring` with a supported secure backend; environment credentials do not. Do not install packages globally or alter the user's credential store as part of this handoff.

## Offline first

Ensure `.ultra-delegation/` is ignored before creating project state; preserve existing ignore rules. Use fresh directories because `init`, templates and report outputs refuse overwrites.

```sh
# Synthetic demonstration only, no API calls or credential access.
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/yarn-demo demo

# Fresh real-project ledger, initially disabled and without sharing permissions.
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/yarn-pilot init

# Discovery hints, not executable configurations.
python3 "$SKILL_PATH/scripts/pilot.py" catalog

# Complete illustrative packet: retain synthetic=true until replacing ALL examples.
python3 "$SKILL_PATH/scripts/pilot.py" example --output .ultra-delegation/yarn-packet.json
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/yarn-pilot route \
  --input .ultra-delegation/yarn-packet.json --dry-run
```

The dry-run is a local payload preview, not a Jev answer or dispatch permission. The included `templates/task-packet.synthetic.json` is another copy of the exact generated fixture with a fixed stale observation timestamp. Never use its example worker IDs, fabricated capacities, or costs as host discovery. `templates/policy.off.json` is the full runtime default policy, provided for inspection; `init` generates the project's actual policy.

## Move from example to a real task

Use the inventory to prepare an actual task and fill the exact packet schema. Replace task/group identifiers, requirements, scope and risk, full worker input/output budgets, host/provider observations, and the complete candidate list. Refresh `context.observed_at` from real host discovery. Only then mark a real packet `synthetic=false`. Use opaque telemetry labels rather than private paths or source text.

Edit `.ultra-delegation/yarn-pilot/policy.json` to choose the eligible `baseline_id` and, when project sharing is enabled, `mode: "shadow"` and `share_summaries: true`. Preserve `share_artifacts: false` and `security_check: false` until separately requested. Configure only the service/account locator for an already saved key if needed. The exact permission, deadline and fallback behavior is described in the bundled pilot guide.

For a live prepared task:

```sh
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/yarn-pilot route \
  --input .ultra-delegation/yarn-packet.json --dry-run

# Explicit network step; use only after project sharing is enabled.
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/yarn-pilot route \
  --input .ultra-delegation/yarn-packet.json --live
```

Read `action`, `selected_configuration_id`, `recommended_*`, `status`, and `reason_codes` from the returned decision. If there is an effective route, call `recheck` with its returned `dec_...` ID and the identical packet immediately before dispatch through native tools. Changes to the packet, policy, evidence or expired discovery require reevaluation. Experiment proposals require a scoped isolated trial; they are not routes.

After independent review, use `outcome-template --decision <saved-id> --candidate <packet-local-id> --output <new-file>`; fill the form, then `observe --input <completed-file>`. Repeat for each actual comparator under that decision. Incomplete forms are rejected. The template's costs are unknown by default. The CLI never runs project tests or reviews worker output on your behalf.

```sh
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/yarn-pilot report
```

This prints newly created HTML/JSON paths. Exact recheck, observation and optional security commands are in `runtime/ultra-delegation/references/pilot.md`; use that reference rather than guessing arguments.

## Inspect and validate the supplied package

`SHA256SUMS` lists all payload files; the outer ZIP also has a companion checksum. Hashes detect drift, not publisher authenticity. `MANIFEST.json` records the pilot baseline and archive fingerprints. No credentials, Yarn source, private history or live evidence are supplied.

To run the pilot's full tests, extract `validation/ultra-delegate-skill-1.3.0-rc.3-source.zip` into a fresh temporary directory, change into its `ultra-delegate-skill-1.3.0-rc.3` root, and run:

```sh
python3 -B -m unittest discover -s tests
python3 scripts/build_release.py --check
python3 scripts/build_release.py --source --check
```

The source ZIP is the matching pilot release source, not the Yarn app or this project-specific handoff wrapper. The report under `examples/` is visibly synthetic and is not imported into the real project ledger.
