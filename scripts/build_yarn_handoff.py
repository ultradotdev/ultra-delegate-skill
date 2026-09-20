#!/usr/bin/env python3
"""Package the Yarn handoff around the fixed, validated rc.3 pilot archives.

Run from any directory. Rebuild the pilot archives with build_release.py first.
This wrapper intentionally pins the pilot baseline; changing it needs review.
"""
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
VERSION = "1.3.0-rc.3"
BASELINE = "eff47efbc55bdf02b6d722cf9628d1858eef2d7a"
ARCHIVES = {
    "ultra-delegation-1.3.0-rc.3.zip": "fb0a43ecc9f1013e58f4e3074c54948308c258caef23f90558b3fad790d0c4a5",
    "ultra-delegate-skill-1.3.0-rc.3-source.zip": "64540ab93309353984f0c471b9fd2b345ccde958a6e7a07d542aa8102e906fc3",
}
DOCS = ("START-HERE.md", "PLAN.md", "RUNBOOK.md", "templates/task-cards.json", "templates/acceptance-checklist.md")


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def build(output_dir):
    archives = {}
    for name, expected in ARCHIVES.items():
        data = (ROOT / "dist" / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Pilot archive differs from the reviewed baseline: " + name)
        archives[name] = data
    if hashlib.sha256(release.zip_bytes(release.release_entries(ROOT))).hexdigest() != ARCHIVES["ultra-delegation-1.3.0-rc.3.zip"]:
        raise ValueError("Current skill source differs from the pinned pilot archive")
    entries = {name: release.read_checked(ROOT, Path("handoffs/yarn") / name) for name in DOCS}
    with zipfile.ZipFile(io.BytesIO(archives["ultra-delegation-1.3.0-rc.3.zip"])) as z:
        for name in z.namelist():
            path = Path(name)
            if not name.startswith("ultra-delegation/") or ".." in path.parts or path.is_absolute():
                raise ValueError("Unexpected archive path")
            entries["runtime/" + name] = z.read(name)
    source_name = "ultra-delegate-skill-1.3.0-rc.3-source.zip"
    entries["validation/" + source_name] = archives[source_name]
    with zipfile.ZipFile(io.BytesIO(archives[source_name])) as z:
        for name in ("qualification.md", "compatibility.md"):
            entries["validation/" + name] = z.read("ultra-delegate-skill-1.3.0-rc.3/docs/" + name)
    sys.path.insert(0, str(ROOT / ".agents/skills/ultra-delegation/scripts"))
    import pilot
    packet = pilot.fixture()
    packet["context"]["observed_at"] = "1970-01-01T00:00:00+00:00"
    entries["templates/task-packet.synthetic.json"] = encoded(packet)
    entries["templates/policy.off.json"] = encoded(pilot.core.policy())
    # Bundle only the explicitly selected synthetic, metadata-only preview.
    preview = ROOT / ".ultra-delegation/yarn-pilot-preview/reports"
    for suffix in ("html", "json"):
        entries["examples/synthetic-report." + suffix] = (preview / ("yarn-pilot-report." + suffix)).read_bytes()
    example = json.loads(entries["examples/synthetic-report.json"])
    if not example["decisions"] or not all(d["synthetic"] for d in example["decisions"]) or not all(o["synthetic"] for o in example["outcomes"]):
        raise ValueError("Example report must contain synthetic observations only")
    entries["MANIFEST.json"] = encoded({
        "schema": "yarn-agent-handoff-v1", "pilot_version": VERSION,
        "pilot_baseline_revision": BASELINE, "pilot_archives_sha256": ARCHIVES,
        "purpose": "Consolidate the GPT-6 and Fable 5.1 Yarn app versions and integrate the optional Jev project pilot.",
        "qualification": "196 local and extracted-source tests passed; live Jev, real Yarn quality and remote candidate CI pending.",
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
