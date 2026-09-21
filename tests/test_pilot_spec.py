"""Public-contract scenarios for the bounded Jev v2 project pilot."""
from __future__ import annotations

import copy
import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / ".agents/skills/ultra-delegation/scripts"
sys.path.insert(0, str(SCRIPTS))
import jev_transport as transport
import pilot
import pilot_core as core


def real_packet():
    value = pilot.fixture()
    value["synthetic"] = False
    return value


def historical(candidate, packet, group, *, accepted=True, **changes):
    """A completed, independently assessed ledger record for evidence-only tests."""
    t = packet["task"]
    value = {
        "configuration_id": core.configuration_id(candidate), "scope_id": t["scope_id"],
        "operation": t["operation"], "risk": t["risk"], "work_kind": t["work_kind"],
        "complexity": t["complexity"], "group_id": group, "synthetic": False,
        "created_at": core.now(), "accepted": accepted,
        "gates": [{"id": gate, "mandatory": True, "passed": accepted} for gate in t["acceptance_gates"]],
        "scores": {name: 90 if accepted else 40 for name in core.DIMENSIONS},
        "costs": {name: {"usd": 0.01, "kind": "measured"} for name in ("worker", "review", "retry", "fallback")},
    }
    value.update(changes)
    return value


def answers(count, *, missing=0, coupling=0, external=0, severe=0):
    value = {
        "missing_requirement": {"noul": missing}, "coordinator_coupling": {"noul": coupling},
        "failure_impact": {"probabilities": {"0": 1-severe, "1": 0, "2": 0, "3": severe}},
        "work_kind": {"choice": "coding", "confidence": 1},
        "reasoning_depth": {"probabilities": {"0": 1, "1": 0, "2": 0, "3": 0}},
        "context_synthesis": {"noul": 0}, "code_interaction": {"noul": 0},
        "external_information": {"noul": external},
    }
    for i in range(count):
        value["operation_match_" + str(i)] = {"noul": 1}
        value["scope_exceeded_" + str(i)] = {"noul": 0}
    return value


class PilotSpecTests(unittest.TestCase):
    def test_default_evidence_requires_wilson_confidence_beyond_five_successes(self):
        packet = real_packet(); candidate = packet["candidates"][0]; p = core.policy()
        five = [historical(candidate, packet, "group-" + str(i)) for i in range(5)]
        row = core.prepare(packet, p, five)["rows"][0]
        self.assertEqual((row["evidence"]["groups"], row["evidence"]["passed_groups"]), (5, 5))
        self.assertFalse(row["evidence"]["qualified"])
        self.assertLess(row["evidence"]["lower_bound"], 0.70)
        ten = [historical(candidate, packet, "group-" + str(i)) for i in range(10)]
        row = core.prepare(packet, p, ten)["rows"][0]
        self.assertTrue(row["evidence"]["qualified"])
        self.assertGreaterEqual(row["evidence"]["lower_bound"], 0.70)

    def test_evidence_cannot_bootstrap_current_group_or_cross_explicit_scope(self):
        packet = real_packet(); candidate = packet["candidates"][0]
        records = [historical(candidate, packet, packet["group_id"]),
                   historical(candidate, packet, "wrong-risk", risk="high"),
                   historical(candidate, packet, "wrong-kind", work_kind="writing"),
                   historical(candidate, packet, "wrong-complexity", complexity="complex")]
        row = core.prepare(packet, core.policy({"minimum_groups": 1}), records)["rows"][0]
        self.assertEqual(row["evidence"]["groups"], 0)

    def test_explicit_choice_never_bypasses_hard_stops_or_invokes_inference(self):
        for name, change in (
            ("context", lambda p: p["context"].update(delegation_allowed=False)),
            ("stale", lambda p: p["context"].update(observed_at=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(seconds=301)).isoformat())),
            ("tool", lambda p: p["task"].update(required_tools=["not-discovered"])),
            ("capacity", lambda p: p["task"].update(input_tokens=30000)),
        ):
            with self.subTest(stop=name):
                packet = real_packet(); packet["user_choice_id"] = "candidate-0"; change(packet)
                with patch.object(transport, "credential", side_effect=AssertionError("credential lookup")):
                    decision = pilot.route_packet(packet, core.policy({"mode": "active", "share_summaries": True}), live=True)
                self.assertEqual((decision["action"], decision["selected_configuration_id"]), ("coordinator", None))
                self.assertEqual(decision["reason_codes"], ["explicit-choice-unavailable"])

    def test_external_information_never_grants_retrieval(self):
        packet = real_packet(); packet["candidates"] = [packet["candidates"][0]]
        prepared = core.prepare(packet, core.policy())
        result = core.recommendation(packet, prepared, answers(1, external=.70), core.policy())
        self.assertEqual((result["action"], result["reason_codes"]), ("repackage", ["external-information-unavailable"]))
        packet["candidates"][0]["tools"].append("external-retrieval")
        prepared = core.prepare(packet, core.policy())
        result = core.recommendation(packet, prepared, answers(1, external=.70), core.policy())
        self.assertEqual(result["action"], "experiment")

    def test_semantic_stops_are_effective_in_active_and_advisory_in_shadow(self):
        packet = real_packet()
        def semantic_response(payload, key):
            result, meta = pilot.synthetic_response(payload, key)
            result["answers"]["missing_requirement"]["noul"] = .21
            return result, meta
        shadow = pilot.route_packet(packet, core.policy({"mode": "shadow", "share_summaries": True, "baseline_id": "candidate-2"}), live=True, call=semantic_response, key="fixture")
        self.assertEqual((shadow["action"], shadow["recommended_action"]), ("route", "clarify"))
        active = pilot.route_packet(packet, core.policy({"mode": "active", "share_summaries": True, "baseline_id": "candidate-2"}), live=True, call=semantic_response, key="fixture")
        self.assertEqual((active["action"], active["selected_configuration_id"]), ("clarify", None))
        prepared = core.prepare(packet, core.policy())
        self.assertEqual(core.recommendation(packet, prepared, answers(4, coupling=.21), core.policy())["action"], "repackage")
        self.assertEqual(core.recommendation(packet, prepared, answers(4, severe=.11), core.policy())["action"], "coordinator")

    def test_candidate_order_and_oversized_payload_keep_contract_boundaries(self):
        packet = real_packet(); p = core.policy({"mode": "off", "baseline_id": "candidate-2"})
        forward = pilot.route_packet(packet, p)
        reordered = copy.deepcopy(packet); reordered["candidates"].reverse()
        reverse = pilot.route_packet(reordered, p)
        self.assertEqual(forward["selected_configuration_id"], reverse["selected_configuration_id"])
        huge = real_packet()
        source = huge["candidates"][0]
        huge["candidates"] = [{**source, "id": "candidate-" + str(i), "model": "worker-" + str(i),
                               "model_revision": "worker-" + str(i) + "-v1", "capability_description": "x" * 4096,
                               "scope_envelope": "y" * 4096} for i in range(12)]
        p = core.policy({"mode": "active", "share_summaries": True, "baseline_id": "candidate-0"})
        with patch.object(transport, "credential", side_effect=AssertionError("credential lookup")):
            with self.assertRaises(transport.ServiceError):
                pilot.route_packet(huge, p, live=True, dry_run=True)
            unavailable = pilot.route_packet(huge, p, live=True)
        self.assertEqual(unavailable["status"], "unavailable")
        self.assertEqual(unavailable["reason_codes"], ["request-too-large"])
        self.assertEqual(unavailable["selected_configuration_id"], core.configuration_id(huge["candidates"][0]))


if __name__ == "__main__":
    unittest.main()
