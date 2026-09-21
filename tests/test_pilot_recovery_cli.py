#!/usr/bin/env python3
"""Black-box recovery checks for the Ultra Delegation pilot workflow.

All setup is deterministic and simulated.  The tests never request credentials,
contact a provider, or launch a native worker.  All state is isolated in temporary directories; CLI calls use fresh processes.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / ".agents/skills/ultra-delegation/scripts"
sys.path.insert(0, str(SCRIPTS))

import pilot
import pilot_core as core
import pilot_workflow as workflow


class RecoveryCliAdversarialTests(unittest.TestCase):
    """Simulated setup; assertions exercise persisted workflow behavior."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "pilot"
        self.packet = pilot.fixture()
        self.packet["synthetic"] = False
        self.policy = pilot.init_project(
            self.root, {"mode": "active", "share_summaries": True, "baseline_id": "candidate-2"}
        )
        self.decision = pilot.route_packet(
            self.packet, self.policy, live=True, call=pilot.synthetic_response, key="simulated"
        )
        pilot.write_new(self.root / "decisions" / (self.decision["id"] + ".json"), self.decision)
        self.event_number = 0

    def cli(self, *args, expect=0):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "pilot.py"), "--root", str(self.root), *args],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, expect, result.stderr)
        return json.loads(result.stdout) if expect == 0 else result

    def event(self, request, kind, attempt_id, **extra):
        self.event_number += 1
        return workflow.event(
            self.root, request["id"],
            {"id": f"simulated-{self.event_number}", "type": kind, "attempt_id": attempt_id, **extra},
            packet=self.packet,
        )

    def complete(self, request, index):
        attempt = request["attempts"][index]
        request = self.event(request, "launching", attempt["id"])
        request = self.event(
            request, "dispatched", attempt["id"], run_id=f"native-{attempt['id']}",
            configuration_id=attempt["configuration_id"], checkout_hash="a" * 64, base_revision="simulated-base",
        )
        return self.event(request, "completed", attempt["id"], artifact_hash="b" * 64)

    def review(self, request, index, accepted):
        attempt = request["attempts"][index]
        raw = pilot.outcome_fixture(self.decision, attempt["configuration_id"], accepted)
        raw.update(
            artifact_hash=attempt["artifact_hash"], request_id=request["id"], attempt_id=attempt["id"],
            attempt_kind=attempt["kind"], worker_id=attempt["run_id"],
            reviewer_id="independent-frontier", reviewer_kind="frontier",
        )
        outcome = pilot.observe(self.root, raw)
        return self.event(request, "reviewed", attempt["id"], outcome_id=outcome["id"]), outcome

    def test_cli_restart_replay_reserves_once_and_reconciliation_stays_bounded(self):
        """Separate CLI processes prove persistence, not in-memory idempotence."""
        request = workflow.start(self.root, self.decision, self.packet, self.policy, "off")
        launch = Path(self.tmp.name) / "launch.json"
        launch.write_text(json.dumps({"id": "restart-launch", "type": "launching", "attempt_id": "attempt-1"}))
        first = self.cli("workflow-event", "--request", request["id"], "--input", str(launch), "--packet", self.packet_file())
        replay = self.cli("workflow-event", "--request", request["id"], "--input", str(launch), "--packet", self.packet_file())
        self.assertEqual(first, replay)
        self.assertEqual((replay["attempts"][0]["state"], len(replay["events"])), ("launching", 1))

        absent = Path(self.tmp.name) / "absent.json"
        absent.write_text(json.dumps({"id": "restart-absent", "type": "launch-not-started", "attempt_id": "attempt-1", "reason_code": "host-confirmed-absent"}))
        reset = self.cli("workflow-event", "--request", request["id"], "--input", str(absent))
        self.assertEqual(reset["attempts"][0]["state"], "planned")
        second_launch = Path(self.tmp.name) / "second-launch.json"
        second_launch.write_text(json.dumps({"id": "restart-launch-2", "type": "launching", "attempt_id": "attempt-1"}))
        self.cli("workflow-event", "--request", request["id"], "--input", str(second_launch), "--packet", self.packet_file())
        second_absent = Path(self.tmp.name) / "second-absent.json"
        second_absent.write_text(json.dumps({"id": "restart-absent-2", "type": "launch-not-started", "attempt_id": "attempt-1", "reason_code": "host-confirmed-absent"}))
        rejected = self.cli("workflow-event", "--request", request["id"], "--input", str(second_absent), expect=2)
        self.assertIn("launch-reconciliation-exhausted", rejected.stderr)

    def packet_file(self):
        path = Path(self.tmp.name) / "packet.json"
        if not path.exists():
            path.write_text(json.dumps(self.packet))
        return str(path)

    def test_rejection_waits_for_initial_comparison_before_repair(self):
        request = workflow.start(self.root, self.decision, self.packet, self.policy, "on")
        request, _ = self.review(self.complete(request, 0), 0, False)
        self.assertEqual([(a["kind"], a["state"]) for a in request["attempts"]], [("initial", "rejected"), ("comparison", "planned")])
        self.assertEqual([a["kind"] for a in workflow.next_actions(request)], ["comparison"])
        request, _ = self.review(self.complete(request, 1), 1, False)
        self.assertEqual(request["attempts"][-1]["kind"], "fallback")

    def test_replan_cannot_reset_an_exhausted_attempt_limit(self):
        policy = pilot.init_project(
            self.root / "limited", {"mode": "active", "share_summaries": True, "baseline_id": "candidate-2", "workflow": {"max_attempts": 1}}
        )
        decision = pilot.route_packet(self.packet, policy, live=True, call=pilot.synthetic_response, key="simulated")
        limited = self.root / "limited"
        pilot.write_new(limited / "decisions" / (decision["id"] + ".json"), decision)
        request = workflow.start(limited, decision, self.packet, policy, "off")
        request = workflow.event(limited, request["id"], {"id": "limit-launch", "type": "launching", "attempt_id": "attempt-1"}, packet=self.packet)
        request = workflow.event(limited, request["id"], {"id": "limit-fail", "type": "execution-failed", "attempt_id": "attempt-1", "reason_code": "simulated-failure"})
        self.assertEqual((request["state"], request["reason_code"]), ("coordinator-required", "attempt-limit"))

        fresh_packet = copy.deepcopy(self.packet)
        extra = copy.deepcopy(fresh_packet["candidates"][1])
        extra.update(id="candidate-new", model="new-model", model_revision="new-revision", effort="high")
        fresh_packet["candidates"].append(extra)
        fresh = pilot.route_packet(fresh_packet, policy, live=True, call=pilot.synthetic_response, key="simulated")
        pilot.write_new(limited / "decisions" / (fresh["id"] + ".json"), fresh)
        replanned = workflow.replan(limited, request["id"], fresh, fresh_packet, policy)
        self.assertEqual((replanned["state"], replanned["reason_code"], len(replanned["attempts"])), ("coordinator-required", "attempt-limit", 1))
        self.assertEqual(workflow.replan(limited, request["id"], fresh, fresh_packet, policy), replanned)

    def test_accepted_request_remains_terminal_across_cli_restart_and_replayed_review(self):
        request = workflow.start(self.root, self.decision, self.packet, self.policy, "on")
        request, outcome = self.review(self.complete(request, 0), 0, True)
        event = Path(self.tmp.name) / "review.json"
        event.write_text(json.dumps({"id": "simulated-4", "type": "reviewed", "attempt_id": "attempt-1", "outcome_id": outcome["id"]}))
        replayed = self.cli("workflow-event", "--request", request["id"], "--input", str(event))
        next_result = self.cli("workflow-next", "--request", request["id"], "--input", self.packet_file())
        self.assertEqual((replayed["state"], replayed["accepted_attempt_id"], next_result["actions"]), ("accepted", "attempt-1", []))

    def test_future_post_start_evidence_is_rejected_before_comparison_dispatch(self):
        """A future-dated same-request outcome must stop a new dispatch."""
        request = workflow.start(self.root, self.decision, self.packet, self.policy, "on")
        request, outcome = self.review(self.complete(request, 0), 0, False)
        outcome_path = self.root / "outcomes" / (outcome["id"] + ".json")
        row = json.loads(outcome_path.read_text())
        row["created_at"] = "2999-01-01T00:00:00+00:00"
        outcome_path.write_text(json.dumps(row))
        result = self.cli("workflow-next", "--request", request["id"], "--input", self.packet_file(), expect=2)
        self.assertIn("decision-evidence-changed", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
