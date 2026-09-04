"""Exercise the public simulation from its CLI in isolated filesystem state."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class DemoTests(unittest.TestCase):
    def test_simulated_lifecycle_cli(self):
        demo = Path(__file__).resolve().parents[1] / "scripts/demo_learning.py"
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            global_dir = base / "global"
            env = {**os.environ, "ULTRA_DELEGATION_HOME": str(global_dir), "PYTHONDONTWRITEBYTECODE": "1"}
            result = subprocess.run([sys.executable, str(demo), "--output-dir", str(base / "artifacts")],
                                    capture_output=True, text=True, env=env, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertTrue(data["simulation"])
            self.assertTrue(data["passed"])
            self.assertTrue(all(data["checks"].values()))
            self.assertEqual(data["model_invocations"], 0)
            self.assertEqual(data["cost"], "unavailable")
            self.assertFalse(global_dir.exists())
            for path in data["reports"]:
                self.assertIn("synthetic fixtures", Path(path).read_text())
            self.assertTrue((Path(data["output_dir"]) / "simulation-report.md").exists())


if __name__ == "__main__":
    unittest.main()
