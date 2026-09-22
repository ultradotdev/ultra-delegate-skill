"""Local conveniences over the existing pilot ledger and native workflow."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pilot
import pilot_core as core
import pilot_workflow as workflow


def file_hash(path):
    path = Path(path)
    core.require(path.is_file(), "artifact-file-required")
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def event(root, request_id, attempt_id, event_type, *, packet=None, **details):
    request = workflow.get(root, request_id)
    attempt = workflow._attempt(request, attempt_id)
    value = {"type": event_type, "attempt_id": attempt_id,
             **{k: v for k, v in details.items() if v is not None}}
    if event_type == "artifact-corrected":
        correction = attempt.get("artifact_correction", {})
        value["previous_artifact_hash"] = correction.get("previous_artifact_hash", attempt.get("artifact_hash"))
    # Repeating a CLI invocation is idempotent. A host-confirmed absent launch
    # permits one new reservation, with a distinct event identity.
    generation = attempt.get("launch_reconciliations", 0) if event_type == "launching" else 0
    value["id"] = "event-" + core.digest([request_id, value, generation])[:24]
    return workflow.event(root, request_id, value, packet=packet)


def status(root, request_id):
    request = copy.deepcopy(workflow.get(root, request_id, _check_elapsed=False))
    actions = workflow.next_actions(request)
    instructions = {
        "planned": "Run workflow-next with the current packet; reserve launching immediately before the native call.",
        "launching": "Reconcile with the native host. Do not launch again unless the host confirms absence.",
        "running": "Wait for the recorded native run; record completion or execution-failed.",
        "completed": "Create a workflow-review-template, independently review, then submit workflow-review.",
        "accepted": "Deliver the independently accepted artifact; integrate only within the user's task scope.",
        "rejected": "Retain the failed result and follow the request's comparison or recovery actions.",
        "failed": "Retain the failure and follow the request's comparison or recovery actions.",
        "canceled": "No further execution is required for this canceled attempt.",
    }
    reports = sorted((Path(root) / "reports").glob("*.html"), key=lambda p: p.stat().st_mtime)
    return {"request_id": request_id, "task_id": request["task_id"], "state": request["state"],
            "reason_code": request.get("reason_code"), "accepted_attempt_id": request["accepted_attempt_id"],
            "actions": actions, "dispatch_authorized": False,
            "attempts": [{**{k: a[k] for k in ("id", "kind", "state", "configuration_id", "run_id", "artifact_hash", "outcome_id") if k in a},
                          "next_step": instructions.get(a["state"], "Coordinator review required.")}
                         for a in request["attempts"]],
            "report": str(reports[-1].resolve()) if reports else None,
            "report_scope": "project-ledger"}


def review_template(root, request_id, attempt_id):
    request = workflow.get(root, request_id)
    attempt = workflow._attempt(request, attempt_id)
    core.require(attempt["state"] == "completed", "attempt-not-completed")
    decision = pilot.get_decision(root, attempt["decision_id"])
    candidate = next(c for c in decision["candidates"] if c["configuration_id"] == attempt["configuration_id"])
    raw = pilot.outcome_template(decision, candidate["id"])
    raw.update(request_id=request_id, attempt_id=attempt_id, attempt_kind=attempt["kind"],
               worker_id=attempt["run_id"], artifact_hash=attempt["artifact_hash"])
    return raw


def review(root, request_id, attempt_id, raw, *, repairable=None, findings_hash=None, **evaluation):
    core.label(attempt_id)
    path = workflow._path(root, request_id).with_suffix('.review-' + attempt_id + '.lock')
    with workflow._lock(path):
        return _review(root, request_id, attempt_id, raw, repairable=repairable, findings_hash=findings_hash, **evaluation)


def _review(root, request_id, attempt_id, raw, *, repairable=None, findings_hash=None, **evaluation):
    request = workflow.get(root, request_id)
    attempt = workflow._attempt(request, attempt_id)
    core.require(attempt["state"] in {"completed", "accepted", "rejected"}, "attempt-not-completed")
    expected = {"request_id": request_id, "attempt_id": attempt_id, "attempt_kind": attempt["kind"],
                "decision_id": attempt["decision_id"], "configuration_id": attempt["configuration_id"],
                "worker_id": attempt["run_id"], "artifact_hash": attempt["artifact_hash"]}
    core.require(isinstance(raw, dict), "invalid-review")
    core.require(all(k not in raw or raw[k] == v for k, v in expected.items()), "outcome-attempt-mismatch")
    bound = {**raw, **expected}
    decision = pilot.get_decision(root, attempt["decision_id"])
    assessed = core.assess_outcome(bound, decision, pilot.load_policy(root))
    destination = Path(root) / "outcomes" / (assessed["id"] + ".json")
    if not destination.exists():
        try:
            pilot.observe(root, bound, **evaluation)
        except FileExistsError:
            # Another invocation may have completed the same immutable review.
            core.require(destination.exists(), "outcome-publication-failed")
    persisted = pilot.read_json(destination)
    core.require(all(persisted.get(k) == v for k, v in assessed.items() if k != "created_at"), "outcome-changed")
    return event(root, request_id, attempt_id, "reviewed", outcome_id=assessed["id"], repairable=repairable, findings_hash=findings_hash)
