# Contributing

Use Python 3.10 or newer and the standard library. The runtime helper must not launch models, other CLIs, or provider requests. Execution belongs to the active host; resource observations must be attributable to that host or an explicit adapter.

Keep the main skill brief. Put conditional guidance in references. Changes to routing, import verification, privacy, resource limits, or accounting need behavior tests reproducing the relevant failure. Avoid tests that only assert wording. Use synthetic observations for resource-pressure tests; never intentionally exhaust a machine.

Run:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build_release.py --check
python3 scripts/build_release.py --source --check
python3 scripts/build_release.py --output-dir dist
python3 scripts/build_release.py --source --output-dir dist
```

When available, also run the official skill creator's `quick_validate.py` against `.agents/skills/ultra-delegation`. That validator checks packaging conventions, not delegation quality.

Each behavioral qualification should name the release hash, host version, exact model revision and native thinking setting, task gates, result, and telemetry availability. Mark supplied snapshots as simulations. Promote compatibility only after a clean-context run exercises the advertised path; documentation and installed binaries alone are insufficient.

Do not commit personal host configuration, environment files, credentials, project learning, local catalogs, or raw session transcripts. Share minimal sanitized reproductions. Avoid putting secrets into public issue reports. Exported free text still needs human review.

Release archives use `scripts/build_release.py`'s explicit allowlist. Add legitimate runtime resources there deliberately. A release review must inspect the tracked tree and reachable history independently: an archive allowlist does not sanitize Git history. Create a clean public source history when private development configuration is present; do not publish the private branch by accident.

Contributions are licensed under the repository's MIT license.
