import copy
import datetime as dt
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / ".agents/skills/ultra-delegation/scripts"
sys.path.insert(0, str(SCRIPTS))

import pilot
import pilot_boundaries as boundaries
import pilot_codex
import pilot_core as core


NOW = dt.datetime(2026, 9, 20, tzinfo=dt.timezone.utc)


def packet():
    return {
        "schema": "ultra-pilot-task-v1", "task_id": "task-a", "group_id": "group-current",
        "synthetic": False,
        "task": {
            "scope_id": "parser", "summary": "Repair a parser.", "requirements": ["Keep API."],
            "worker_boundary": "Patch plus tests.", "intended_use": "Internal reviewed release.",
            "risk": "low", "work_kind": "coding", "operation": "repair-parser",
            "complexity": "routine", "acceptance_gates": ["tests-pass"],
            "required_tools": ["read-files"], "required_modalities": [],
            "input_tokens": 100, "output_tokens": 100,
        },
        "context": {"host": "codex", "provider": "openai", "observed_at": NOW.isoformat(),
                    "delegation_allowed": True},
        "candidates": [{
            "id": "candidate-a", "provider": "openai", "model": "model-a",
            "model_revision": "model-a-v1", "host": "codex", "adapter": "codex-native",
            "effort": "medium", "prompt_contract": "contract-v1", "prompt_version": "prompt-v1",
            "tool_policy": "read-only", "capability_description": "Bounded parser repair.",
            "scope_envelope": "One module and tests.", "available": True,
            "tools": ["read-files"], "modalities": [], "context_window": 4096,
            "max_output_tokens": 1024, "execution_location": "remote", "estimate_usd": 0.02,
            "roles": ["economical"],
        }],
    }


def bounded_packet():
    value = packet()
    value["task"]["boundaries"] = boundaries.example()
    return value


class PilotBoundaryTests(unittest.TestCase):
    def test_validate_returns_deep_validated_copy_and_accepts_explained_na(self):
        source = boundaries.example()
        result = boundaries.validate(source)
        self.assertEqual(result, source)
        self.assertIsNot(result, source)
        self.assertIsNot(result["allowed_changes"]["items"], source["allowed_changes"]["items"])
        source["allowed_changes"]["items"][0] = "Changed after validation."
        self.assertNotEqual(result, source)
        self.assertEqual(result["protected_data"]["items"], [])
        self.assertTrue(result["protected_data"]["not_applicable"])

    def test_every_category_requires_items_xor_explained_na(self):
        for name in ("allowed_changes", "allowed_actions", "protected_behavior",
                     "protected_data", "coordinator_decisions", "security_requirements"):
            with self.subTest(category=name, form="neither"):
                value = boundaries.example()
                value[name] = {"items": [], "not_applicable": None}
                with self.assertRaisesRegex(core.PilotError, "invalid-task-boundaries"):
                    boundaries.validate(value)
            with self.subTest(category=name, form="both"):
                value = boundaries.example()
                if not value[name]["items"]:
                    value[name]["items"] = ([{"id": "bounded-rule", "requirement": "Apply the bounded rule.",
                                                    "mandatory": True}]
                                                   if name == "security_requirements"
                                                   else ["Apply the explicit boundary."])
                value[name]["not_applicable"] = "An explanation cannot accompany concrete items."
                with self.assertRaisesRegex(core.PilotError, "invalid-task-boundaries"):
                    boundaries.validate(value)

    def test_limits_and_security_requirement_shape_are_enforced(self):
        too_many = boundaries.example()
        too_many["allowed_actions"]["items"] = [f"Bounded action {index}." for index in range(25)]
        with self.assertRaisesRegex(core.PilotError, "invalid-task-boundaries"):
            boundaries.validate(too_many)

        too_many_security = boundaries.example()
        too_many_security["security_requirements"]["items"] = [
            {"id": f"rule-{index}", "requirement": f"Apply security rule {index}.", "mandatory": True}
            for index in range(13)
        ]
        with self.assertRaisesRegex(core.PilotError, "invalid-task-boundaries"):
            boundaries.validate(too_many_security)

        invalid_boolean = boundaries.example()
        invalid_boolean["security_requirements"]["items"][0]["mandatory"] = 1
        with self.assertRaisesRegex(core.PilotError, "invalid-task-boundaries"):
            boundaries.validate(invalid_boolean)

    def test_packets_require_explicit_boundaries_and_granted_authorization(self):
        with self.assertRaisesRegex(core.PilotError, "task-boundaries-required"):
            core.validate_packet(packet())

        unknown = bounded_packet()
        unknown["task"]["boundaries"]["authorization"] = "unknown"
        self.assertEqual(boundaries.validate(unknown["task"]["boundaries"])["authorization"], "unknown")
        with self.assertRaisesRegex(core.PilotError, "authorization-required"):
            core.validate_packet(unknown)

        self.assertEqual(core.validate_packet(bounded_packet())["task"]["boundaries"]["authorization"], "granted")

    def test_worker_contract_contains_exact_contract_and_matching_hash(self):
        value = boundaries.example()
        rendered = boundaries.worker_contract(value)
        match = re.search(r"Contract hash: `sha256:([0-9a-f]{64})`", rendered)
        self.assertIsNotNone(match)
        encoded = rendered.split("```json\n", 1)[1].rsplit("\n```", 1)[0]
        self.assertEqual(json.loads(encoded), value)
        self.assertEqual(match.group(1), core.digest(value))

    def test_preparation_preserves_boundaries_and_writes_bound_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            state = base / "state"
            pilot.init_project(state, {"mode": "active", "share_summaries": True, "bakeoff": "off"})
            source = bounded_packet()
            task = {key: copy.deepcopy(source[key]) for key in ("task_id", "group_id", "task")}
            expected = copy.deepcopy(task["task"]["boundaries"])
            host = {"observed_at": core.now(), "models": {"gpt-5.6-luna": ["medium"]},
                    "tools": ["read-files"], "delegation_allowed": True}
            catalog = {"models": [{
                "slug": "gpt-5.6-luna", "supported_reasoning_levels": [{"effort": "medium"}],
                "context_window": 32000, "max_output_tokens": 8000,
                "input_modalities": ["text"],
            }]}

            result = pilot_codex.prepare_project(state, task, catalog, host, base / "prepared")
            prepared = pilot.read_json(result["files"]["packet.json"])
            self.assertEqual(prepared["task"]["boundaries"], expected)
            contract_path = Path(result["files"]["worker-contract.md"])
            rendered = contract_path.read_text(encoding="utf-8")
            self.assertEqual(json.loads(rendered.split("```json\n", 1)[1].rsplit("\n```", 1)[0]), expected)
            self.assertIn("sha256:" + core.digest(expected), rendered)


if __name__ == "__main__":
    unittest.main()
