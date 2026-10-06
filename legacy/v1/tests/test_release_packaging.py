"""Release boundary checks, including a helper run using only the extracted ZIP."""
from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

REPOSITORY = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_release", REPOSITORY / "scripts/build_release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleasePackagingTests(unittest.TestCase):
    def test_crlf_checkout_produces_identical_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {Path(name) for name in release.SOURCE_FILES}
            paths.update(release.SKILL / name for name in release.SKILL_FILES)
            for path in paths:
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                data = (REPOSITORY / path).read_bytes().replace(b"\r\n", b"\n")
                target.write_bytes(data.replace(b"\n", b"\r\n"))
            for collect in (release.release_entries, release.source_entries):
                self.assertEqual(release.zip_bytes(collect(REPOSITORY)),
                                 release.zip_bytes(collect(root)))

    def test_source_archive_has_only_public_inputs_and_rebuilds(self):
        entries = release.source_entries(REPOSITORY)
        expected = {f"{release.SOURCE_PREFIX}/{p}" for p in release.SOURCE_FILES}
        expected.update(f"{release.SOURCE_PREFIX}/{release.SKILL.as_posix()}/{p}" for p in release.SKILL_FILES)
        expected.add(f"{release.SOURCE_PREFIX}/.gitignore")
        self.assertEqual(expected, set(entries))
        self.assertFalse(any("/.git/" in name or "/.cursor/" in name or "/.eva/" in name
                             or "/.ultra-delegation/" in name for name in entries))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with zipfile.ZipFile(io.BytesIO(release.zip_bytes(entries))) as archive:
                archive.extractall(root)
            extracted = root / release.SOURCE_PREFIX
            self.assertEqual(entries, release.source_entries(extracted))
            self.assertEqual(release.release_entries(REPOSITORY), release.release_entries(extracted))

    def test_reproducible_and_extracted_helper_is_self_contained(self):
        entries = release.release_entries(REPOSITORY)
        first = release.zip_bytes(entries)
        second = release.zip_bytes(dict(reversed(list(entries.items()))))
        self.assertEqual(first, second)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with zipfile.ZipFile(io.BytesIO(first)) as archive:
                self.assertEqual(sorted(entries), archive.namelist())
                self.assertTrue(all(item.date_time == (1980, 1, 1, 0, 0, 0)
                                    for item in archive.infolist()))
                archive.extractall(root)
            helper = root / "ultra-delegation/scripts/ultra_delegation.py"
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            env["ULTRA_DELEGATION_HOME"] = str(root / "catalog")
            for args in (["--help"], ["--root", str(root / "project/.ultra-delegation"), "init"],
                         ["--root", str(root / "project/.ultra-delegation"), "validate"]):
                result = subprocess.run([sys.executable, "-I", str(helper), *args],
                                        cwd=root, env=env, text=True, capture_output=True,
                                        timeout=20, check=False)
                self.assertEqual(0, result.returncode, result.stderr)

    def test_extracted_jev_runs_without_site_packages_and_with_optional_keyring(self):
        entries = release.release_entries(REPOSITORY)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with zipfile.ZipFile(io.BytesIO(release.zip_bytes(entries))) as archive:
                archive.extractall(root)
            adapter = root / "ultra-delegation/scripts/jev.py"
            qualify = adapter.with_name("jev_qualification.py")
            state = root / "state"
            env = dict(os.environ)
            env.pop("TYPESAFE_API_KEY", None)
            env["PYTHON_KEYRING_BACKEND"] = "keyring.backends.null.Keyring"
            # -S demonstrates that site dependencies are not needed at all.
            for flags in (["-I", "-S"], ["-I"]):
                for script, args in ((adapter, ["--help"]),
                                     (adapter, ["--root", str(state), "auth", "status"]),
                                     (qualify, []),
                                     (adapter.with_name("jev_docs.py"), ["--check"]),
                                     (adapter.with_name("pilot_questions.py"), ["--check"]),
                                     (adapter.with_name("pilot.py"), ["catalog"]),
                                     (adapter.with_name("pilot_codex.py"), ["--help"]),
                                     (adapter.with_name("pilot_codex.py"), ["prepare", "--help"]),
                                     (adapter.with_name("pilot_fixtures.py"), ["list"]),
                                     (adapter.with_name("pilot.py"), ["workflow-status", "--help"]),
                                     (adapter.with_name("capability_index.py"), ["--check"]),
                                     (adapter.with_name("epoch_import.py"), ["--help"]),
                                     (adapter.with_name("pilot.py"), ["--root", str(root / ("pilot-" + str(len(flags)))), "demo"]),
                                     (adapter.with_name("shortlist.py"), ["--help"]),
                                     (adapter.with_name("jev_benchmark_capture.py"), ["--help"]),
                                     (adapter.with_name("jev_benchmark.py"), ["--demo", "--output-prefix", str(root / ("benchmark-" + str(len(flags))))])):
                    result = subprocess.run([sys.executable, *flags, str(script), *args],
                                            cwd=root, env=env, text=True, capture_output=True, timeout=20)
                    self.assertEqual(0, result.returncode, result.stderr)
            # An actual keyring installation, when present, must not disturb env auth.
            env["TYPESAFE_API_KEY"] = "synthetic-private-credential"
            result = subprocess.run([sys.executable, "-I", str(adapter), "--root", str(state), "auth", "status"],
                                    cwd=root, env=env, text=True, capture_output=True, timeout=20)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn(env["TYPESAFE_API_KEY"], result.stdout + result.stderr)

    def test_unrelated_private_files_are_not_packaged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in [release.SKILL / name for name in release.SKILL_FILES] + [Path("LICENSE")]:
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(REPOSITORY / path, root / path)
            for relative in [".env", ".eva/identity.mdc", ".git/config", ".ultra-delegation/evidence.jsonl",
                             ".agents/skills/ultra-delegation/scripts/__pycache__/private.pyc"]:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("private-sentinel", encoding="utf-8")
            entries = release.release_entries(root)
            self.assertEqual(len(release.SKILL_FILES) + 1, len(entries))
            self.assertFalse(any(b"private-sentinel" in data for data in entries.values()))

    def test_symlink_size_and_secret_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / "sample"
            file.write_text("ordinary input", encoding="utf-8")
            (root / "linked").symlink_to(file)
            with self.assertRaisesRegex(ValueError, "Symlink"):
                release.read_checked(root, Path("linked"))
            file.write_bytes(b"x" * (release.MAX_FILE_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "size limit"):
                release.read_checked(root, Path("sample"))
            file.write_text("ghp_" + "x" * 36, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "recognizable secret"):
                release.read_checked(root, Path("sample"))


if __name__ == "__main__":
    unittest.main()
