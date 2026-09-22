#!/usr/bin/env python3
"""Package the exact current allowlisted skill/source snapshot and Yarn runbook."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import build_release as release

ROOT = Path(__file__).resolve().parents[1]
VERSION = release.VERSION
DOCS = ("START-HERE.md", "PLAN.md", "RUNBOOK.md", "templates/task-cards.json", "templates/acceptance-checklist.md")


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def build(output_dir):
    # Freeze the exact allowlisted source bytes in this bundle, not a stale RC hash.
    skill_name = f"ultra-delegation-{VERSION}.zip"
    source_name = f"ultra-delegate-skill-{VERSION}-source.zip"
    archives = {skill_name: release.zip_bytes(release.release_entries(ROOT)),
                source_name: release.zip_bytes(release.source_entries(ROOT))}
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in archives.items()}
    entries = {name: release.read_checked(ROOT, Path("handoffs/yarn") / name).replace(
        b"../../docs/", b"validation/") for name in DOCS}
    with zipfile.ZipFile(io.BytesIO(archives[skill_name])) as z:
        for name in z.namelist():
            path = Path(name)
            if not name.startswith("ultra-delegation/") or ".." in path.parts or path.is_absolute():
                raise ValueError("Unexpected archive path")
            entries["runtime/" + name] = z.read(name)
    entries["validation/" + source_name] = archives[source_name]
    with zipfile.ZipFile(io.BytesIO(archives[source_name])) as z:
        for name in ("active-recovery-validation.md", "active-recovery-results.json", "compatibility.md", "repository-trial-validation.md",
                     "full-model-matrix-validation.md", "full-model-matrix-results.json",
                     "coordinator-dependency-validation.md", "coordinator-dependency-results.json",
                     "security-review-validation.md", "security-review-results.json"):
            entries["validation/" + name] = z.read(release.SOURCE_PREFIX+"/docs/" + name).replace(
                b"../.agents/skills/", b"../runtime/")
    sys.path.insert(0, str(ROOT / ".agents/skills/ultra-delegation/scripts"))
    import pilot
    packet = pilot.fixture()
    packet["context"]["observed_at"] = "1970-01-01T00:00:00+00:00"
    entries["templates/task-packet.synthetic.json"] = encoded(packet)
    entries["templates/policy.off.json"] = encoded(pilot.core.policy())
    import pilot_report
    demo = pilot_report.build_report([], [])
    demo["example_note"] = "Synthetic empty-ledger report. Follow RUNBOOK to produce actual native results."
    entries["examples/synthetic-report.json"] = encoded(demo)
    entries["examples/synthetic-report.html"] = pilot_report.render_html(demo).encode()
    entries["MANIFEST.json"] = encoded({
        "schema": "yarn-agent-handoff-v1", "pilot_version": VERSION,
        "source_snapshot_sha256": hashes[source_name], "pilot_archives_sha256": hashes,
        "purpose": "Consolidate the GPT-6 and Fable 5.1 Yarn app versions and integrate the optional Jev project pilot.",
        "validation_status_file": "validation/security-review-validation.md",
        "routing": "active after explicit project setup; no statistical admission gate",
        "task_boundaries": "required explicit contract with granted authorization; inspect worker-contract.md and hash",
        "security": "off by default; no scanners; preview optional screening and disposition required findings before acceptance",
        "runtime_entrypoint": "runtime/ultra-delegation/scripts/pilot.py",
        "agent_entrypoint": "START-HERE.md", "synthetic_example_only": True,
        "credential_material_included": False,
    })
    entries["SHA256SUMS"] = "".join(hashlib.sha256(data).hexdigest() + "  " + name + "\n" for name, data in sorted(entries.items())).encode()
    payload = release.zip_bytes({"yarn-agent-handoff/" + name: data for name, data in entries.items()})
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / ("yarn-agent-handoff-" + VERSION + ".zip")
    with output.open("xb") as stream:
        stream.write(payload)
    checksum = hashlib.sha256(payload).hexdigest()
    with Path(str(output) + ".sha256").open("x") as stream:
        stream.write(checksum + "  " + output.name + "\n")
    return {"archive": str(output.resolve()), "sha256": checksum, "files": len(entries), "bytes": len(payload)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    print(json.dumps(build(args.output_dir), indent=2))
