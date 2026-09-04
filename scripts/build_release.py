#!/usr/bin/env python3
"""Build deterministic allowlisted skill/source ZIPs. Never package repository history."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

VERSION = "1.2.0-beta.1"
REPOSITORY = Path(__file__).resolve().parents[1]
SKILL = Path(".agents/skills/ultra-delegation")
SKILL_FILES = (
    "SKILL.md",
    "agents/openai.yaml",
    "scripts/ultra_delegation.py",
    "scripts/evidence.py",
    "scripts/local_resources.py",
    "references/cli.md",
    "references/host-native.md",
    "references/hosts.md",
    "references/measurement-and-portability.md",
    "references/orchestration.md",
    "assets/hosts/codex-worker.toml",
    "assets/hosts/claude-worker.md",
    "assets/hosts/opencode-worker.md",
)
SOURCE_FILES = (
    "README.md", "LICENSE", "CONTRIBUTING.md", ".github/workflows/tests.yml",
    "docs/compatibility.md", "docs/demo.md", "docs/ultra-dev-handoff.md", "docs/qualification.md",
    "scripts/build_release.py", "scripts/demo_learning.py", "tests/test_demo.py",
    "tests/test_beta_safety.py", "tests/test_ultra_delegation.py",
    "tests/test_local_resources.py", "tests/test_release_packaging.py",
    "tests/test_evidence.py", "tests/test_guard_freshness.py",
)
SOURCE_PREFIX = f"ultra-delegate-skill-{VERSION}"
SOURCE_GITIGNORE = b"__pycache__/\n*.py[cod]\n/dist/\n/.ultra-delegation/\n.env\n"
MAX_FILE_BYTES = 1_048_576
PERSONAL_PATH = re.compile(rb"(?:/" rb"Users/[^/\s]+/|/" rb"home/[^/\s]+/)")
SECRET = re.compile(rb"(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?\n[A-Za-z0-9+/=]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9_-]{32,})")


def read_checked(repository: Path, relative: Path) -> bytes:
    current = repository
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Symlink is not a release input: {relative}")
    if not current.is_file():
        raise ValueError(f"Missing required release file: {relative}")
    if current.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"Release file exceeds size limit: {relative}")
    data = current.read_bytes()
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"Release file exceeds size limit: {relative}")
    data.decode("utf-8")
    if PERSONAL_PATH.search(data) or SECRET.search(data):
        raise ValueError(f"Review personal path or recognizable secret in: {relative}")
    return data


def release_entries(repository: Path) -> dict[str, bytes]:
    entries = {f"ultra-delegation/{name}": read_checked(repository, SKILL / name)
               for name in SKILL_FILES}
    entries["ultra-delegation/LICENSE"] = read_checked(repository, Path("LICENSE"))
    entrypoint = entries["ultra-delegation/SKILL.md"].decode("utf-8")
    if not entrypoint.startswith("---\n") or "\nname: ultra-delegation\n" not in entrypoint:
        raise ValueError("Skill frontmatter must name ultra-delegation")
    helper = entries["ultra-delegation/scripts/ultra_delegation.py"].decode("utf-8")
    if not re.search(r'(?:VERSION|SKILL_VERSION|RELEASE)\s*=\s*[\"\x27]' + re.escape(VERSION) + r'[\"\x27]', helper):
        raise ValueError("Helper version and release version must match")
    return entries


def source_entries(repository: Path) -> dict[str, bytes]:
    release_entries(repository)  # Apply the same version/frontmatter release gate.
    paths = [Path(name) for name in SOURCE_FILES] + [SKILL / name for name in SKILL_FILES]
    entries = {f"{SOURCE_PREFIX}/{path.as_posix()}": read_checked(repository, path)
               for path in paths}
    # Never copy the development checkout's personal ignore/configuration files.
    entries[f"{SOURCE_PREFIX}/.gitignore"] = SOURCE_GITIGNORE
    return entries


def zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    # Stored entries avoid zlib-version variability; metadata is fully normalized.
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, data)
    return buffer.getvalue()


def atomic_write(path: Path, data: bytes) -> None:
    if path.is_symlink():
        raise ValueError(f"Refusing symlink output: {path.name}")
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate inputs and reproducibility without writing")
    parser.add_argument("--source", action="store_true", help="Build a clean public source archive instead of the installable skill")
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    args = parser.parse_args()
    try:
        entries = source_entries(REPOSITORY) if args.source else release_entries(REPOSITORY)
        data = zip_bytes(entries)
        if data != zip_bytes(entries):
            raise ValueError("Archive reproducibility check failed")
        digest = hashlib.sha256(data).hexdigest()
        name = f"ultra-delegate-skill-{VERSION}-source.zip" if args.source else f"ultra-delegation-{VERSION}.zip"
        if not args.check:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            atomic_write(args.output_dir / name, data)
            atomic_write(args.output_dir / f"{name}.sha256", f"{digest}  {name}\n".encode())
        print(json.dumps({"version": VERSION, "archive": name, "sha256": digest,
                          "files": sorted(entries), "written": not args.check}, indent=2))
        return 0
    except (ValueError, OSError, UnicodeError) as exc:
        parser.exit(1, f"Release check failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
