"""Admission and lease tests; resource pressure is simulated, never induced."""
import importlib.util
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / ".agents/skills/ultra-delegation/scripts/local_resources.py"
SPEC = importlib.util.spec_from_file_location("local_resources", MODULE)
lr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lr)


def fixture():
    return ({"execution_location": "local", "provider": "ollama", "model_revision": "tiny:q4"},
            {"now": 100, "local_resources": {
                "observed_at": 100, "ram_total_bytes": 32 * lr.GIB,
                "ram_available_bytes": 24 * lr.GIB, "memory_pressure": "normal",
                "active_local_requests": 0, "existing_model_processes": 1,
                "unified_memory": True, "gpu_kind": "unified",
                "capabilities": dict.fromkeys(lr.CAPABILITIES, True),
                "footprint": {"runtime": "ollama", "model_revision": "tiny:q4",
                              "quantization": "q4", "context_tokens": 8192,
                              "weights_bytes": 4 * lr.GIB, "cache_bytes": lr.GIB,
                              "overhead_bytes": lr.GIB}}},
            {"local_execution": {"mode": "enabled"}})


def crash_holding(directory, pipe):
    lease = lr.LocalLease(directory)
    pipe.send(lease.acquire())
    pipe.recv()
    os._exit(0)


class ResourceTests(unittest.TestCase):
    def test_default_disabled_authorization_and_exclusions(self):
        p, c, policy = fixture()
        self.assertEqual(lr.evaluate_local(p, c, {})["status"], "excluded-by-policy")
        c["local_authorized"] = True
        self.assertTrue(lr.evaluate_local(p, c, {})["eligible"])
        for field, values in (("excluded_models", ["ollama/tiny:q4"]), ("allowed_models", [])):
            with self.subTest(field=field):
                self.assertFalse(lr.evaluate_local(p, c, {"local_execution": {field: values}})["eligible"])
        self.assertFalse(lr.evaluate_local(p, {**c, "local_authorized": False}, {"local_execution": {"mode": "ask"}})["eligible"])

    def test_location_unknown_and_remote(self):
        p, c, policy = fixture()
        del p["execution_location"]
        self.assertEqual(lr.evaluate_local(p, c, policy)["status"], "unknown-location")
        p["execution_location"] = "remote"
        self.assertTrue(lr.evaluate_local(p, {}, {})["eligible"])

    def test_headroom_topology_and_footprint(self):
        p, c, policy = fixture()
        self.assertTrue(lr.evaluate_local(p, c, policy)["eligible"])
        c["local_resources"]["ram_available_bytes"] = 10 * lr.GIB
        self.assertEqual(lr.evaluate_local(p, c, policy)["status"], "insufficient-headroom")
        p, c, policy = fixture()
        c["local_resources"]["footprint"].pop("cache_bytes")
        self.assertEqual(lr.evaluate_local(p, c, policy)["status"], "unknown-footprint")
        p, c, policy = fixture()
        s = c["local_resources"]
        s.update(gpu_kind="discrete", unified_memory=False, vram_total_bytes=8 * lr.GIB, vram_available_bytes=5 * lr.GIB)
        s["footprint"]["vram_bytes"] = 4 * lr.GIB
        self.assertEqual(lr.evaluate_local(p, c, policy)["status"], "insufficient-headroom")
        s["vram_available_bytes"] = 7 * lr.GIB
        self.assertTrue(lr.evaluate_local(p, c, policy)["eligible"])
        s["unified_memory"] = True
        self.assertFalse(lr.evaluate_local(p, c, policy)["eligible"])

    def test_freshness_numbers_bounds_and_controls(self):
        for change in (lambda c: c.update(now=111), lambda c: c.update(now=99),
                       lambda c: c["local_resources"].update(ram_available_bytes=float("nan")),
                       lambda c: c["local_resources"]["capabilities"].update(scoped_cancel=False),
                       lambda c: c.update(context_tokens=8193), lambda c: c.update(output_tokens=2049),
                       lambda c: c["local_resources"].update(active_local_requests=1),
                       lambda c: c.update(local_attempt=2)):
            p, c, policy = fixture()
            change(c)
            self.assertFalse(lr.evaluate_local(p, c, policy)["eligible"])

    def test_malformed_snapshots_fail_closed(self):
        p, c, policy = fixture()
        for field in ("footprint", "capabilities"):
            snapshot = {**c["local_resources"], field: None}
            self.assertFalse(lr.evaluate_local(p, {**c, "local_resources": snapshot}, policy)["eligible"])
        for value in (None, [], "enabled"):
            self.assertFalse(lr.evaluate_local(p, c, {"local_execution": value})["eligible"])

    def test_resource_abort_timeout_and_run_suppression(self):
        p, c, policy = fixture()
        c["elapsed_seconds"] = 1
        c["local_resources"]["active_local_requests"] = 1
        # Loaded weights must not be counted twice in monitoring.
        c["local_resources"]["ram_available_bytes"] = 9 * lr.GIB
        self.assertFalse(lr.monitor_local(p, c, policy, {})["cancel_owned_request"])
        c["elapsed_seconds"] = 300
        stopped = lr.monitor_local(p, c, policy, {})
        self.assertTrue(stopped["cancel_owned_request"])
        c["local_run_state"] = stopped["state"]
        self.assertEqual(lr.evaluate_local(p, c, policy)["status"], "resource-aborted")
        p, c, policy = fixture()
        c["elapsed_seconds"] = 1
        c["local_resources"]["memory_pressure"] = "critical"
        self.assertTrue(lr.monitor_local(p, c, policy, {})["cancel_owned_request"])

    def test_lease_two_owners_and_recovery_after_process_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = lr.LocalLease(directory), lr.LocalLease(directory)
            token = a.acquire()
            self.assertIsNone(b.acquire())
            with self.assertRaises(ValueError):
                a.release("wrong-owner")
            a.release(token)
            token = b.acquire()
            self.assertIsNotNone(token)
            b.release(token)
            ctx = multiprocessing.get_context("fork")
            parent, child = ctx.Pipe()
            process = ctx.Process(target=crash_holding, args=(directory, child))
            process.start()
            self.assertTrue(parent.poll(5))
            self.assertTrue(parent.recv())
            self.assertIsNone(a.acquire())
            parent.send("exit")
            process.join(5)
            self.assertEqual(process.exitcode, 0)
            token = a.acquire()
            self.assertIsNotNone(token)
            a.release(token)

    def test_lease_does_not_follow_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target"
            target.write_text("do not overwrite")
            (Path(directory) / "local-execution.lock").symlink_to(target)
            with self.assertRaises(OSError):
                lr.LocalLease(directory).acquire()
            self.assertEqual(target.read_text(), "do not overwrite")


if __name__ == "__main__":
    unittest.main()
