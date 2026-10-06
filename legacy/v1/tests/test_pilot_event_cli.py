"""CLI-level persistence regressions for native workflow launch observations."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / ".agents/skills/ultra-delegation/scripts/pilot.py"


class NativeWorkflowEventCLITests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)
        self.root = self.directory / "state"
        self.environment = dict(os.environ)
        self.environment.pop("TYPESAFE_API_KEY", None)
        self.environment.pop("PYTHONPATH", None)
        self.environment["PYTHON_KEYRING_BACKEND"] = "keyring.backends.null.Keyring"
        self.cli("init", "--mode", "off", "--baseline-id", "candidate-2")

        self.packet_path = self.directory / "packet.json"
        self.cli("example", "--output", str(self.packet_path))
        packet = self.read(self.packet_path)
        # This is a deterministic local native-host contract fixture.
        packet["synthetic"] = False
        self.write(self.packet_path, packet)
        decision = self.cli("route", "--input", str(self.packet_path))
        self.request = self.cli(
            "workflow-start", "--decision", decision["id"], "--input", str(self.packet_path),
            "--bakeoff", "off",
        )
        self.attempt = self.request["attempts"][0]
        self.launch_event = self.directory / "launch.json"
        self.write(self.launch_event, {
            "id": "launch-native-once", "type": "launching", "attempt_id": self.attempt["id"],
        })
        self.cli(
            "workflow-event", "--request", self.request["id"], "--input", str(self.launch_event),
            "--packet", str(self.packet_path),
        )

    def cli(self, *args, ok=True):
        run = subprocess.run(
            [sys.executable, "-I", "-S", str(SCRIPT), "--root", str(self.root), *args],
            cwd=self.directory, env=self.environment, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(run.returncode, 0 if ok else 2, run.stderr)
        return json.loads(run.stdout if ok else run.stderr)

    @staticmethod
    def read(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    @staticmethod
    def write(path, value):
        Path(path).write_text(json.dumps(value), encoding="utf-8")

    def persisted_request(self):
        return self.read(self.root / "workflows" / (self.request["id"] + ".json"))

    def dispatched_event(self, configuration_id):
        path = self.directory / "dispatched.json"
        self.write(path, {
            "id": "dispatch-native-once",
            "type": "dispatched",
            "attempt_id": self.attempt["id"],
            "run_id": "native-run-once",
            "configuration_id": configuration_id,
            "checkout_hash": "a" * 64,
            "base_revision": "base-revision",
        })
        return path

    def test_duplicate_dispatched_event_from_separate_cli_processes_is_idempotent(self):
        event_path = self.dispatched_event(self.attempt["configuration_id"])

        first = self.cli("workflow-event", "--request", self.request["id"], "--input", str(event_path))
        retry = self.cli("workflow-event", "--request", self.request["id"], "--input", str(event_path))

        self.assertEqual(retry, first)
        persisted = self.persisted_request()
        self.assertEqual([event["id"] for event in persisted["events"]], [
            "launch-native-once", "dispatch-native-once",
        ])
        self.assertEqual(persisted["attempts"][0]["state"], "running")
        self.assertEqual(persisted["attempts"][0]["run_id"], "native-run-once")

    def test_unsupported_observed_configuration_leaves_no_accepted_artifact(self):
        wrong_configuration = "cfg_" + "0" * 24
        self.assertNotEqual(wrong_configuration, self.attempt["configuration_id"])
        event_path = self.dispatched_event(wrong_configuration)

        error = self.cli(
            "workflow-event", "--request", self.request["id"], "--input", str(event_path), ok=False,
        )

        self.assertEqual(error["error"], "observed-configuration-mismatch")
        persisted = self.persisted_request()
        self.assertEqual(persisted["attempts"][0]["state"], "launching")
        self.assertNotIn("run_id", persisted["attempts"][0])
        self.assertNotIn("artifact_hash", persisted["attempts"][0])
        self.assertIsNone(persisted["accepted_attempt_id"])
        self.assertEqual([event["id"] for event in persisted["events"]], ["launch-native-once"])
        self.assertEqual(list((self.root / "outcomes").glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
