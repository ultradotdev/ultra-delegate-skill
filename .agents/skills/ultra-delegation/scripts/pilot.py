#!/usr/bin/env python3
"""Project test drive: Jev v2 routing, outcome feedback and portable telemetry.

Workers execute through the coordinator's native host. This CLI never launches
another model CLI and never creates or modifies a credential-store entry.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_core as core
import pilot_questions as questions
import jev_transport as transport
from jev_contract import PRICE

INPUT_LIMIT = 2 * 1024 * 1024


def read_json(path):
    if str(path) == "-":
        data = sys.stdin.buffer.read(INPUT_LIMIT + 1)
    else:
        with Path(path).open("rb") as stream:
            data = stream.read(INPUT_LIMIT + 1)
    core.require(len(data) <= INPUT_LIMIT, "input-too-large")
    try:
        return json.loads(data, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise core.PilotError("invalid-json") from None


def write_new(path, value):
    data = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    # Exclusive creation rejects existing files and symlinks; private default permissions.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(data)
    except BaseException:
        Path(path).unlink(missing_ok=True)
        raise


def init_project(root, p=None):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if (root / "policy.json").exists():
        p = load_policy(root)  # Re-entry never resets a project or changes sharing.
    else:
        p = core.policy(p)
        write_new(root / "policy.json", p)
    ignore = root / '.gitignore'
    if not ignore.exists():
        fd = os.open(ignore, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write('*\n')
    for directory in ("decisions", "outcomes", "reports"):
        (root / directory).mkdir(exist_ok=True)
    return p


def load_policy(root):
    return core.policy(read_json(Path(root) / "policy.json"))


def load_records(root, kind, *, include_retracted=False):
    directory = Path(root) / kind
    records = []
    for path in sorted(directory.glob("*.json")):
        row = read_json(path)
        core.require(isinstance(row, dict) and row.get("schema") == f"ultra-pilot-{'decision' if kind == 'decisions' else 'outcome'}-v1", "invalid-ledger")
        core.require(path.stem == row.get("id"), "ledger-id-mismatch")
        records.append(row)
        core.require(len(records) <= 10000, "ledger-limit")
    if kind == "outcomes" and not include_retracted:
        import pilot_learning
        removed = {r['outcome_id'] for r in pilot_learning.retractions(root)}
        records = [r for r in records if r['id'] not in removed]
    return records


def get_decision(root, identifier):
    core.require(isinstance(identifier, str) and __import__("re").fullmatch(r"dec_[a-f0-9]{24}", identifier), "invalid-decision-id")
    decision = read_json(Path(root) / "decisions" / (identifier + ".json"))
    value = {k: v for k, v in decision.items() if k != "id"}
    core.require(identifier == "dec_" + core.digest(value)[:24], "decision-changed")
    return decision


def empty_usage():
    return {"attempts": 0, "latency_ms": 0, "cost_usd": 0, "cost_kind": "measured",
            "input_tokens": 0, "output_tokens": 0}


def ask(payload, p, call=None, key=None):
    """Return validated allowlisted answers and redacted, attributable telemetry."""
    usage = empty_usage()
    call_started = False
    started = time.monotonic()
    try:
        transport.encoded_payload(payload)
        if key is None:
            key, _ = transport.credential(p["credential_ref"], service=p["credential_service"])
        call_started = True
        usage.update(cost_usd=None, cost_kind="unknown", input_tokens=None, output_tokens=None)
        result, meta = (call or transport.request)(payload, key)
        core.require(type(meta.get("attempts")) is int and 1 <= meta["attempts"] <= 2, "invalid-transport-meta")
        core.require(transport.number(meta.get("latency_ms"), 0, 1e9), "invalid-transport-meta")
        usage.update(attempts=meta["attempts"], latency_ms=meta["latency_ms"])
        _, tokens = transport.validate_response(payload, result)
        usage.update(tokens)
        if payload["model"] == PRICE["model"] and meta["attempts"] == 1:
            usage.update(cost_usd=tokens["input_tokens"] * PRICE["input_per_million_usd"] / 1e6,
                         cost_kind="estimated", price_date=PRICE["date"])
        clean = {}
        for name, q in payload["questions"].items():
            a = result["answers"][name]
            keys = {"type", "noul"} if q["type"] == "noul" else {"type", "probabilities", "confidence", "choice" if q["type"] == "choice" else "score"}
            clean[name] = {k: copy.deepcopy(a[k]) for k in keys}
        return clean, usage, None
    except transport.ServiceError as error:
        usage.update(attempts=max(usage["attempts"], error.attempts), latency_ms=(time.monotonic()-started)*1000)
        if call_started:
            usage.update(cost_usd=None, cost_kind="unknown")
        return None, usage, error.code
    except Exception:
        usage["latency_ms"] = (time.monotonic()-started)*1000
        return None, usage, "inference-failed"


def route_packet(packet, p, outcomes=(), *, live=False, dry_run=False, call=None, key=None):
    p = core.policy(p)
    prepared = core.prepare(packet, p, outcomes)
    task = packet["task"]
    payload = questions.route_payload(task, prepared["cards"], p["model"])
    # A preview includes only explicitly supplied state. No credentials, ledger writes, or I/O.
    if dry_run:
        transport.encoded_payload(payload)
        return {"dry_run": True, "payload": payload, "candidates": prepared["rows"],
                "input_hash": core.digest(packet), "policy_hash": core.digest(p)}
    baseline = prepared["baseline"]
    baseline_id = baseline["configuration_id"] if baseline else None
    d = {"schema": "ultra-pilot-decision-v1", "created_at": core.now(),
         "task_id": packet["task_id"], "group_id": packet.get("group_id", packet["task_id"]),
         "scope_id": task["scope_id"], "operation": task["operation"], "risk": task["risk"],
         "work_kind": task["work_kind"], "complexity": task["complexity"], "acceptance_gates": task["acceptance_gates"],
         "synthetic": packet.get("synthetic", False), "mode": p["mode"], "status": "skipped",
         "action": "route" if baseline else "coordinator", "selected_configuration_id": baseline_id,
         "baseline_configuration_id": baseline_id, "recommended_action": "coordinator",
         "recommended_configuration_id": None, "nominated_configuration_ids": [], "alternative_configuration_ids": [],
         "reason_codes": [], "decision_policy_version": core.DECISION_POLICY_VERSION,
         "demand_profile": {}, "required_demands": [], "review_requirements": [], "candidate_assessments": [], "diagnostics": [],
         "question_version": questions.ROUTING_VERSION, "model": p["model"],
         "policy_hash": core.digest(p), "input_hash": core.digest(packet),
         "question_hash": core.digest(payload["questions"]), "payload_hash": core.digest(payload),
         "evidence_hash": core.digest(outcomes), "candidates": prepared["rows"], "signals": {}, "router": empty_usage(),
         "dispatch_authorized": False, "evidence_status": "observational",
         "configuration_metadata": {core.configuration_id(c): {k: c[k] for k in ("provider", "model_revision", "host", "adapter", "effort", "prompt_contract", "tool_policy", "prompt_version") if k in c} for c in packet["candidates"]}}
    if prepared["override_missing"]:
        d.update(action="coordinator", selected_configuration_id=None, reason_codes=["explicit-choice-unavailable"])
    elif prepared["override"]:
        selected = prepared["override"]["configuration_id"]
        d.update(action="route", selected_configuration_id=selected, recommended_action="route",
                 recommended_configuration_id=selected, reason_codes=["explicit-choice"])
    elif not prepared["shortlist"]:
        d["reason_codes"] = ["no-eligible-candidates"]
    elif p["mode"] == "off" or not live:
        d["reason_codes"] = ["routing-off" if p["mode"] == "off" else "live-not-requested"]
    elif not p["share_summaries"]:
        d.update(status="unavailable", reason_codes=["summary-sharing-disabled"])
    else:
        answers, usage, error = ask(payload, p, call=call, key=key)
        d["router"] = usage
        if error:
            d.update(status="unavailable", reason_codes=[error])
        else:
            rec = core.recommendation(packet, prepared, answers, p)
            d.update(status="ok" if rec["action"] in {"route", "experiment"} else "abstained", signals=answers,
                     recommended_action=rec["action"], recommended_configuration_id=rec["configuration_id"],
                     nominated_configuration_ids=rec["nominees"], alternative_configuration_ids=rec["alternatives"], reason_codes=rec["reason_codes"])
            for field in ("demand_profile", "required_demands", "review_requirements", "candidate_assessments", "diagnostics"):
                d[field] = rec[field]
            d["selection_basis"] = rec["selection_basis"]
            if p["mode"] == "active":
                d.update(action=rec["action"], selected_configuration_id=rec["configuration_id"])
                d["acceptance_gates"] = sorted(set(task["acceptance_gates"]) | set(rec["review_requirements"]))
    boundaries = task['boundaries']
    d.update(boundary_hash=core.digest(boundaries), security_sensitive=boundaries['security_sensitive'],
             security_requirements=[{'id':r['id'], 'requirement_hash':core.digest(r['requirement']), 'mandatory':r['mandatory']}
                                    for r in boundaries['security_requirements']['items']])
    boundary_gates = {'task-boundaries'} | {'security-req-'+core.digest(r['id'])[:12]
                      for r in d['security_requirements'] if r['mandatory']}
    d['acceptance_gates'] = sorted(set(d['acceptance_gates']) | boundary_gates)
    d["id"] = "dec_" + core.digest(d)[:24]
    return d


def security_assessment(packet, p, enabled, *, live=False, call=None, key=None):
    import pilot_security
    return pilot_security.evaluate(packet, p, enabled, live=live, call=call, key=key)


def observe(root, raw, *, security_input=None, security_check=False, security_findings=None, judge_input=None, live=False, call=None, key=None):
    p = load_policy(root)
    decision = get_decision(root, raw.get("decision_id"))
    outcome = core.assess_outcome(raw, decision, p)
    if raw.get("request_id"):
        import pilot_workflow
        pilot_workflow.validate_observation(root, raw)
    destination = Path(root) / "outcomes" / (outcome["id"] + ".json")
    # An OS-owned lock recovers after process death. A surviving pending marker
    # means paid evaluator completion is unknown, so resume without paying again.
    import pilot_workflow
    reservation = destination.with_suffix('.pending')
    with pilot_workflow._lock(destination.with_suffix('.lock')):
        if destination.exists():
            raise FileExistsError('outcome-already-recorded')
        if raw.get("request_id"):
            pilot_workflow.validate_observation(root, raw)
        import pilot_security
        security, metadata = pilot_security.complete(root, raw, decision, p, security_input, security_findings,
            enabled=security_check or p['security_check'], live=live and not reservation.exists(), call=call, key=key)
        if metadata is not None:
            raw = {**raw, 'security_review':metadata}
            outcome = core.assess_outcome(raw, decision, p)
        interrupted = reservation.exists()
        if interrupted and security.get('status') == 'unavailable':
            security.update(reason_codes=['interrupted-evaluation-not-repeated'], cost_usd=None, cost_kind='unknown')
        outcome['security'] = security
        core.require(not reservation.is_symlink(), 'invalid-outcome-reservation')
        fd = os.open(reservation, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        # Only independent findings change acceptance; Jev probabilities remain advisory.
        try:
            if interrupted:
                if judge_input is not None:
                    outcome['judge'] = {**empty_usage(), 'status':'unavailable', 'reason_codes':['interrupted-evaluation-not-repeated'], 'cost_usd':None, 'cost_kind':'unknown'}
            else:
                if judge_input is not None:
                    import pilot_judge
                    outcome["judge"] = pilot_judge.assess(judge_input, p, live=live, call=call, key=key)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(outcome, stream, sort_keys=True, indent=2, allow_nan=False)
                stream.write("\n")
                stream.flush(); os.fsync(stream.fileno())
            os.replace(reservation, destination)
        except BaseException:
            try: os.close(fd)
            except OSError: pass
            # Preserve reservation: a retry cannot know whether an external call
            # completed before interruption, even if its response was lost.
            raise
    return outcome


def recheck(root, identifier, packet):
    d = get_decision(root, identifier)
    p = load_policy(root)
    outcomes = load_records(root, "outcomes")
    core.require(not d["synthetic"], "synthetic-decision-not-executable")
    core.require(d.get("decision_policy_version") == core.DECISION_POLICY_VERSION, "decision-policy-changed")
    core.require(d["action"] == "route" and d["selected_configuration_id"] is not None, "decision-not-a-route")
    core.require(core.digest(packet) == d["input_hash"] and core.digest(p) == d["policy_hash"], "decision-inputs-changed")
    core.require(core.digest(outcomes) == d["evidence_hash"], "decision-evidence-changed")
    age = (dt.datetime.now(dt.timezone.utc)-core.timestamp(d["created_at"])).total_seconds()
    core.require(0 <= age <= p["capability_age_seconds"], "decision-expired")
    prepared = core.prepare(packet, p, outcomes)
    core.require(any(r["configuration_id"] == d["selected_configuration_id"] and r["eligible"] for r in prepared["rows"]), "candidate-no-longer-eligible")
    return {"decision_id": identifier, "configuration_id": d["selected_configuration_id"],
            "recheck": "passed", "execution": "coordinator-native-host", "expires_after_seconds": max(0, p["capability_age_seconds"]-age)}


def report(root, prefix=None, task_descriptions=None):
    import pilot_report
    prefix = Path(prefix) if prefix else Path(root) / "reports" / ("pilot-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    import pilot_workflow
    requests = [pilot_workflow.get(root, path.stem) for path in sorted((Path(root)/"workflows").glob("req_*.json"))]
    import pilot_security
    assessments = [pilot_security._read(path) for path in sorted((Path(root)/'security-assessments').glob('sec_*.json'))]
    value = pilot_report.build_report(load_records(root, "decisions"), load_records(root, "outcomes"), requests=requests, assessments=assessments)
    if task_descriptions is not None:
        value = pilot_report.with_task_descriptions(value, task_descriptions)
    html = pilot_report.render_html(value)
    json_path, html_path = Path(str(prefix)+".json"), Path(str(prefix)+".html")
    # Render and validate before writes. Exclusive outputs never overwrite user artifacts.
    json_path.parent.mkdir(parents=True, exist_ok=True)
    write_new(json_path, value)
    try:
        fd = os.open(html_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(html)
    except BaseException:
        json_path.unlink(missing_ok=True)
        raise
    return {"html": str(html_path.resolve()), "json": str(json_path.resolve())}


def fixture():
    import pilot_boundaries
    """Illustrative Yarn packet. Model availability/capacity must be replaced by discovery."""
    task = {"scope_id": "yarn.component-review", "summary": "Compare the GPT-6 and Fable 5.1 Yarn implementations of one component and propose a consolidation patch.",
            "requirements": ["Preserve the documented component behavior.", "Explain any incompatible interface and leave the final architecture decision to the coordinator."],
            "acceptance_gates": ["component-tests", "independent-review"], "boundaries": pilot_boundaries.example(),
            "worker_boundary": "One component comparison and patch proposal; no final architecture decision, repository mutation, or deployment.",
            "intended_use": "An isolated proposal reviewed before integration into the consolidated Yarn app.",
            "risk": "low", "work_kind": "coding", "operation": "patch-proposal", "complexity": "routine",
            "required_tools": ["read-files"], "required_modalities": ["text"], "input_tokens": 8000, "output_tokens": 4000}
    task['boundaries']['allowed_changes'] = {'items':['Produce a consolidation patch proposal for the assigned component; do not mutate the repository.'], 'not_applicable':None}
    task['boundaries']['allowed_actions'] = {'items':['Read the supplied component implementations and interfaces.'], 'not_applicable':None}
    task['boundaries']['protected_behavior'] = {'items':['Preserve documented component behavior and unrelated interfaces.'], 'not_applicable':None}
    candidates = []
    for i, role in enumerate(("economical", "specialist", "fallback", "challenger")):
        candidates.append({"id": "candidate-"+str(i), "provider": "openai", "model": "example-worker-"+str(i),
                           "model_revision": "example-worker-"+str(i)+"-revision", "host": "codex", "adapter": "codex-native", "effort": "medium",
                           "prompt_contract": "bounded-patch-v1", "prompt_version": "1", "tool_policy": "read-only-v1",
                           "capability_description": "Produces bounded component comparisons and independently reviewed patch proposals.",
                           "scope_envelope": "Localized component changes with supplied interfaces; final architecture and integration are outside scope.",
                           "available": True, "tools": ["read-files"], "modalities": ["text"], "context_window": 32000,
                           "max_output_tokens": 8000, "execution_location": "remote", "estimate_usd": [0.02, 0.06, 0.12, None][i], "roles": [role]})
    return {"schema": "ultra-pilot-task-v1", "task_id": "yarn-component-001", "group_id": "yarn-component-001", "synthetic": True,
            "task": task, "context": {"host": "codex", "provider": "openai", "observed_at": core.now(), "delegation_allowed": True}, "candidates": candidates}


def synthetic_response(payload, key):
    answers = {}
    for name, q in payload["questions"].items():
        if q["type"] == "noul":
            yes = 0.98 if name.startswith(("operation_match", "evidence_comparable", "reasoning_fit", "code_interaction_fit", "context_synthesis_fit", "sufficient_")) or name == "enough" else 0.02
            answers[name] = {"type": "noul", "noul": yes}
        elif q["type"] == "choice":
            answers[name] = {"type": "choice", "choice": "coding", "confidence": 1.0, "probabilities": {k: float(k == "coding") for k in q["criteria"]}}
        else:
            answers[name] = {"type": "score", "score": 1.0, "confidence": 1.0,
                             "probabilities": {str(i): float(i == 1) for i in range(len(q["criteria"]))},
                             "legend": {str(i): s for i, s in enumerate(q["criteria"])}}
    return {"model": payload["model"], "answers": answers, "usage": {"input_tokens": 1000, "output_tokens": 10}}, {"attempts": 1, "latency_ms": 15.0}


def outcome_fixture(d, cid, accepted=True):
    return {"decision_id": d["id"], "boundary_hash":d.get("boundary_hash"), "configuration_id": cid, "artifact_hash": core.digest({"demo": d["id"], "candidate": cid}),
            "reviewer_id": "synthetic-reviewer", "reviewer_kind": "synthetic", "worker_id": "synthetic-worker", "review_accepted": accepted,
            "gates": [{"id": k, "mandatory": True, "passed": accepted} for k in d["acceptance_gates"]],
            "scores": {k: 90 if accepted else 40 for k in core.DIMENSIONS},
            "costs": {k: {"usd": 0.02 if k == "worker" else 0.01 if k == "review" else 0, "kind": "estimated"} for k in core.COST_COMPONENTS},
            "latency_ms": 1500}


def outcome_template(decision, candidate_id):
    row = next((c for c in decision["candidates"] if c["id"] == candidate_id), None)
    core.require(row is not None and row["eligible"], "unknown-outcome-candidate")
    core.observation_role(decision, row["configuration_id"])
    raw = outcome_fixture(decision, row["configuration_id"])
    raw.update(artifact_hash=None, reviewer_id=None, worker_id=None, reviewer_kind="frontier", review_accepted=None,
               scores={k: None for k in core.DIMENSIONS}, latency_ms=None)
    raw["gates"] = [{"id": k, "mandatory": True, "passed": None} for k in decision["acceptance_gates"]]
    raw["costs"] = {k: {"usd": None, "kind": "unknown"} for k in core.COST_COMPONENTS}
    # The reviewer explicitly confirms exercised demands. Never copy predictions
    # into learning evidence, including in an otherwise passing active trial.
    raw["reviewed_demands"] = []
    raw["critical_defects"] = []
    return raw


def demo(root):
    p = init_project(root, {"mode": "active", "share_summaries": True, "share_artifacts": True, "baseline_id": "candidate-2"})
    for i in range(12):
        packet = fixture()
        packet["task_id"] = packet["group_id"] = "yarn-demo-"+str(i)
        outcomes = load_records(root, "outcomes")
        d = route_packet(packet, p, outcomes, live=True, call=synthetic_response, key="synthetic")
        write_new(Path(root)/"decisions"/(d["id"]+".json"), d)
        for c in (packet["candidates"][0], packet["candidates"][2]):
            if (d["action"] == "route" and core.configuration_id(c) != d["selected_configuration_id"]):
                continue  # Comparisons belong to nominated trials, not an unrelated active route.
            raw = outcome_fixture(d, core.configuration_id(c), accepted=not (i == 1 and c["id"] == "candidate-2"))
            raw["costs"]["worker"]["usd"] = c["estimate_usd"]
            observe(root, raw, security_check=(i == 2))  # demonstrates unavailable advisory without blocking recording
    pending = fixture(); pending["task_id"] = pending["group_id"] = "yarn-demo-pending"
    d = route_packet(pending, p, load_records(root, "outcomes"), live=True, call=synthetic_response, key="synthetic")
    write_new(Path(root)/"decisions"/(d["id"]+".json"), d)
    return report(root)


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "error: invalid-cli-arguments\n")


def main(argv=None):
    parser = SafeParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(".ultra-delegation/pilot"))
    sub = parser.add_subparsers(dest="command", required=True, parser_class=SafeParser)
    init = sub.add_parser("init")
    init.add_argument("--mode", choices=("off", "active"), default="active")
    init.add_argument("--baseline-id")
    init.add_argument("--selection-preference", choices=("efficiency_hints", "strongest_fit"), default="efficiency_hints")
    init.add_argument("--bakeoff", choices=("auto", "on", "off"), default="auto")
    configure = sub.add_parser("configure")
    configure.add_argument("--selection-preference", choices=("efficiency_hints", "strongest_fit"))
    configure.add_argument("--bakeoff", choices=("auto", "on", "off"))
    configure.add_argument("--mode", choices=("off", "active"))
    for name in ("share-summaries", "share-artifacts", "security-check", "allow-host-managed-output"):
        configure.add_argument("--"+name, action=argparse.BooleanOptionalAction, default=None)
    configure.add_argument("--credential-service")
    configure.add_argument("--credential-ref")
    for band in ("investigate", "strong", "sufficient"):
        configure.add_argument("--security-"+band, type=float)
    for key in ("share-summaries", "share-artifacts", "security-check"):
        init.add_argument("--"+key, action="store_true")
    init.add_argument("--allow-host-managed-output", action="store_true")
    init.add_argument("--credential-service", default=transport.SERVICE)
    init.add_argument("--credential-ref", default="default")
    auth = sub.add_parser("auth", help="Read existing credential status or verify access using a synthetic request")
    auth.add_argument("action", choices=("status", "check"))
    route = sub.add_parser("route")
    route.add_argument("--input", required=True)
    route.add_argument("--dry-run", action="store_true")
    route.add_argument("--live", action="store_true")
    record = sub.add_parser("observe")
    record.add_argument("--input", required=True)
    record.add_argument("--security-check", action="store_true")
    record.add_argument("--security-input")
    record.add_argument("--security-findings")
    record.add_argument("--judge-input")
    record.add_argument("--live", action="store_true")
    check = sub.add_parser("recheck")
    check.add_argument("--decision", required=True)
    check.add_argument("--input", required=True)
    summary = sub.add_parser("report")
    summary.add_argument("--output-prefix", type=Path)
    summary.add_argument("--task-descriptions", help="Explicit local-only JSON task-id to description mapping")
    sub.add_parser("demo")
    sub.add_parser("catalog")
    example = sub.add_parser("example")
    example.add_argument("--output", type=Path, required=True)
    template = sub.add_parser("outcome-template")
    template.add_argument("--decision", required=True)
    template.add_argument("--candidate", required=True)
    template.add_argument("--output", type=Path, required=True)
    template.add_argument("--request")
    template.add_argument("--attempt")
    workflow_start = sub.add_parser("workflow-start")
    workflow_start.add_argument("--decision", required=True)
    workflow_start.add_argument("--input", required=True)
    workflow_start.add_argument("--bakeoff", choices=("auto", "on", "off"))
    workflow_next = sub.add_parser("workflow-next")
    workflow_next.add_argument("--request", required=True)
    workflow_next.add_argument("--input", required=True)
    workflow_replan = sub.add_parser("workflow-replan")
    workflow_replan.add_argument("--request", required=True)
    workflow_replan.add_argument("--decision", required=True)
    workflow_replan.add_argument("--input", required=True)
    workflow_event = sub.add_parser("workflow-event")
    workflow_event.add_argument("--request", required=True)
    source = workflow_event.add_mutually_exclusive_group(required=True)
    source.add_argument("--input")
    source.add_argument("--type", choices=("launching", "dispatched", "completed", "artifact-corrected", "execution-failed", "launch-not-started", "cancel", "reviewed"))
    workflow_event.add_argument("--attempt")
    for name in ("run-id", "configuration-id", "checkout-hash", "base-revision", "artifact-hash", "outcome-id", "reason-code", "findings-hash", "configuration-source"):
        workflow_event.add_argument("--"+name)
    workflow_event.add_argument("--repairable", action="store_true", default=None)
    workflow_event.add_argument("--artifact-file", type=Path, help="Hash the actual artifact file locally; do not transcribe a hash")
    status = sub.add_parser("workflow-status")
    status.add_argument("--request", required=True)
    form = sub.add_parser("workflow-review-template")
    form.add_argument("--request", required=True)
    form.add_argument("--attempt", required=True)
    form.add_argument("--output", type=Path, required=True)
    security = sub.add_parser("workflow-security")
    security.add_argument("--request", required=True)
    security.add_argument("--attempt", required=True)
    security.add_argument("--input")
    security.add_argument("--live", action="store_true")
    security.add_argument("--dry-run", action="store_true")
    review = sub.add_parser("workflow-review")
    review.add_argument("--request", required=True)
    review.add_argument("--attempt", required=True)
    review.add_argument("--input", required=True)
    review.add_argument("--security-check", action="store_true")
    review.add_argument("--security-input")
    review.add_argument("--security-findings")
    review.add_argument("--judge-input")
    review.add_argument("--live", action="store_true")
    review.add_argument("--repairable", action="store_true", default=None)
    review.add_argument("--findings-hash")
    workflow_event.add_argument("--packet")
    learning = sub.add_parser("learning")
    learning.add_argument("operation", choices=("audit", "export", "import", "retract"))
    learning.add_argument("--input")
    learning.add_argument("--output", type=Path)
    learning.add_argument("--outcome")
    learning.add_argument("--reason")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            p = {k: getattr(args, k) for k in ("mode", "baseline_id", "share_summaries", "share_artifacts", "security_check", "credential_service", "credential_ref", "allow_host_managed_output", "selection_preference", "bakeoff")}
            existing = (args.root / "policy.json").exists()
            p = init_project(args.root, p)
            result = {"initialized": True, "existing_policy_preserved": existing, "mode": p["mode"],
                      "security": "advisory" if p["security_check"] else "off", "selection_preference": p["selection_preference"], "bakeoff": p["bakeoff"]}
        elif args.command == "configure":
            import pilot_workflow, tempfile
            with pilot_workflow._lock(args.root / ".policy.lock"):
                p = load_policy(args.root)
                updates = {k: v for k, v in vars(args).items() if k not in {"root", "command"} and v is not None}
                band_updates = {band: updates.pop('security_'+band) for band in ('investigate','strong','sufficient') if 'security_'+band in updates}
                if band_updates: updates['security_thresholds'] = {**p['security_thresholds'], **band_updates}
                p = core.policy({**p, **updates})
                fd, temp = tempfile.mkstemp(prefix=".policy-", dir=args.root)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as stream:
                        json.dump(p, stream, indent=2, sort_keys=True, allow_nan=False)
                        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
                    os.replace(temp, args.root / "policy.json")
                finally:
                    Path(temp).unlink(missing_ok=True)
            result = {"configured": True, "policy_hash": core.digest(p), "changed_fields": sorted(updates), "reevaluate_existing_decisions": True}
        elif args.command == "auth":
            p = load_policy(args.root)
            result = transport.auth(args.action, p["credential_ref"], p["model"], service=p["credential_service"])
        elif args.command == "example":
            write_new(args.output, fixture())
            result = {"example": str(args.output), "synthetic": True, "discovery_required": True}
        elif args.command == "catalog":
            result = read_json(Path(__file__).resolve().parent.parent / "assets/pilot-catalog.json")
        elif args.command == "outcome-template":
            raw = outcome_template(get_decision(args.root, args.decision), args.candidate)
            if args.request or args.attempt:
                import pilot_workflow
                request = pilot_workflow.get(args.root, args.request)
                attempt = pilot_workflow._attempt(request, args.attempt)
                core.require(request['decision_id'] == args.decision and attempt['configuration_id'] == raw['configuration_id'], 'outcome-attempt-mismatch')
                core.require(attempt['state'] == 'completed', 'attempt-not-completed')
                raw.update(request_id=args.request, attempt_id=args.attempt, attempt_kind=attempt['kind'],
                           worker_id=attempt['run_id'], artifact_hash=attempt['artifact_hash'])
            write_new(args.output, raw)
            result = {"template": str(args.output), "independent_assessment_required": True}
        elif args.command == "learning":
            import pilot_learning
            if args.operation == 'audit':
                result = {'outcomes': load_records(args.root, 'outcomes', include_retracted=True), 'retractions': pilot_learning.retractions(args.root)}
            elif args.operation == 'retract': result = pilot_learning.retract(args.root, args.outcome, args.reason)
            elif args.operation == 'import': result = pilot_learning.import_bundle(args.root, read_json(args.input))
            else:
                core.require(args.output is not None, 'output-required')
                write_new(args.output, pilot_learning.export(args.root)); result = {'export': str(args.output)}
        elif args.command.startswith("workflow-"):
            import pilot_workflow
            import pilot_convenience
            if args.command == "workflow-status":
                result = pilot_convenience.status(args.root, args.request)
            elif args.command == "workflow-review-template":
                write_new(args.output, pilot_convenience.review_template(args.root, args.request, args.attempt))
                result = {"template": str(args.output), "independent_assessment_required": True}
            elif args.command == "workflow-security":
                import pilot_security
                result = pilot_security.workflow_security(args.root, args.request, args.attempt,
                    read_json(args.input) if args.input else None, live=args.live, dry_run=args.dry_run)
            elif args.command == "workflow-review":
                result = pilot_convenience.review(args.root, args.request, args.attempt, read_json(args.input),
                    security_input=read_json(args.security_input) if args.security_input else None,
                    security_findings=read_json(args.security_findings) if args.security_findings else None,
                    security_check=args.security_check, judge_input=read_json(args.judge_input) if args.judge_input else None, live=args.live,
                    repairable=args.repairable, findings_hash=args.findings_hash)
            elif args.command == "workflow-start":
                result = pilot_workflow.start(args.root, get_decision(args.root, args.decision), read_json(args.input), load_policy(args.root), args.bakeoff or load_policy(args.root)["bakeoff"])
            elif args.command == "workflow-replan":
                result = pilot_workflow.replan(args.root, args.request, get_decision(args.root, args.decision), read_json(args.input), load_policy(args.root))
            elif args.command == "workflow-next":
                request = pilot_workflow.get(args.root, args.request)
                result = {"request_id": args.request, "state": request['state'], "actions": pilot_workflow.next_actions(request)}
                for action in result['actions']:
                    if action['action'] == 'dispatch':
                        action['check'] = pilot_workflow.recheck(args.root, args.request, action['attempt_id'], read_json(args.input))
            else:
                packet = read_json(args.packet) if args.packet else None
                core.require(not (args.input and args.artifact_file), "invalid-artifact-file-option")
                if args.input:
                    result = pilot_workflow.event(args.root, args.request, read_json(args.input), packet=packet)
                else:
                    names = ("run_id", "configuration_id", "checkout_hash", "base_revision", "artifact_hash", "outcome_id", "reason_code", "findings_hash", "configuration_source", "repairable")
                    if args.artifact_file:
                        core.require(args.artifact_hash is None and args.type in {"completed", "artifact-corrected"}, "invalid-artifact-file-option")
                        args.artifact_hash = pilot_convenience.file_hash(args.artifact_file)
                    result = pilot_convenience.event(args.root, args.request, args.attempt, args.type,
                        packet=packet, **{name: getattr(args, name) for name in names})
        elif args.command == "demo":
            result = demo(args.root)
        elif args.command == "report":
            result = report(args.root, args.output_prefix, read_json(args.task_descriptions) if args.task_descriptions else None)
        elif args.command == "recheck":
            result = recheck(args.root, args.decision, read_json(args.input))
        elif args.command == "route":
            packet = read_json(args.input)
            p = load_policy(args.root)
            if not args.dry_run:
                # Test writability before a potentially paid inference call.
                probe = args.root / "decisions" / (".preflight-" + os.urandom(8).hex())
                fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.close(fd); probe.unlink()
            result = route_packet(packet, p, load_records(args.root, "outcomes"), live=args.live, dry_run=args.dry_run)
            if not args.dry_run:
                write_new(args.root / "decisions" / (result["id"]+".json"), result)
        else:
            raw = read_json(args.input)
            security = None
            if args.security_input:
                try: security = read_json(args.security_input)
                except (OSError, ValueError): security = None
            judge = read_json(args.judge_input) if args.judge_input else None
            result = observe(args.root, raw, security_input=security, security_check=args.security_check, security_findings=read_json(args.security_findings) if args.security_findings else None, judge_input=judge, live=args.live)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (core.PilotError, transport.ServiceError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
    except OSError:
        print('{"error":"filesystem-error"}', file=sys.stderr)
    except (ValueError, TypeError, KeyError, AttributeError):
        print('{"error":"invalid-input"}', file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
