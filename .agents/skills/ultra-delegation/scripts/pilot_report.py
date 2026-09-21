#!/usr/bin/env python3
"""Render a privacy-preserving, standalone report for Jev pilot telemetry.

This module intentionally projects event ledgers into a small public report.  It
never serializes packet text, provider bodies, or unknown event fields.
"""
from __future__ import annotations

import html
import json
import math
import re
from collections import Counter, defaultdict
from typing import Any


DECISION_SCHEMA = "ultra-pilot-decision-v1"
OUTCOME_SCHEMA = "ultra-pilot-outcome-v1"


def _value(value: Any, default: Any = None) -> Any:
    return default if value is None else value


def _number(value: Any, default: Any = None) -> Any:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else default


def _label(value: Any, default: str = "-") -> str:
    return value if isinstance(value, str) and value else default


def _labels(value: Any) -> list[str]:
    return [x for x in value if isinstance(x, str)] if isinstance(value, list) else []


def _metadata_label(value):
    return (isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:+/-]{1,128}", value)
            and not re.search(r"(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{20,})", value))


def _cost(value: Any) -> dict[str, Any]:
    value = value if isinstance(value, dict) else {}
    amount = _number(value.get("usd"))
    kind = value.get("kind") if value.get("kind") in ("measured", "estimated", "unknown") else "unknown"
    return {"usd": amount, "kind": kind}


def _question_answer(value: Any) -> dict[str, Any] | None:
    """Accept only typed, compact answers; never copy arbitrary answer metadata."""
    if not isinstance(value, dict) or value.get("type") not in ("noul", "choice", "score"):
        return None
    answer: dict[str, Any] = {"type": value["type"]}
    if value["type"] == "noul":
        probability = _number(value.get("noul"))
        if probability is None or not 0 <= probability <= 1: return None
        answer["yes"] = probability
    elif value["type"] == "choice":
        options = ("coding", "research", "writing", "data", "planning", "mixed", "other")
        probabilities = value.get("probabilities")
        if (value.get("choice") not in options or not isinstance(probabilities, dict)
                or set(probabilities) != set(options) or any(_number(v) is None or not 0 <= v <= 1 for v in probabilities.values())):
            return None
        confidence = _number(value.get("confidence"))
        if confidence is None or not 0 <= confidence <= 1: return None
        answer.update(choice=value["choice"], confidence=confidence, probabilities={k: probabilities[k] for k in options})
    else:
        probabilities = value.get("probabilities")
        if (not isinstance(probabilities, dict) or set(probabilities) != {"0", "1", "2", "3"}
                or any(_number(v) is None or not 0 <= v <= 1 for v in probabilities.values())):
            return None
        score, confidence = _number(value.get("score")), _number(value.get("confidence"))
        if score is None or not 0 <= score <= 3 or confidence is None or not 0 <= confidence <= 1: return None
        answer.update(score=score, confidence=confidence, probabilities={k: probabilities[k] for k in ("0", "1", "2", "3")})
    return answer


def _project_decision(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or raw.get("schema") != DECISION_SCHEMA:
        return None
    candidates = []
    for item in raw.get("candidates", []) if isinstance(raw.get("candidates"), list) else []:
        if not isinstance(item, dict):
            continue
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        candidates.append({
            "id": _label(item.get("id")), "configuration_id": _label(item.get("configuration_id")),
            "model": _label(item.get("model")), "effort": _label(item.get("effort")),
            "eligible": item.get("eligible") is True, "reasons": _labels(item.get("reasons")),
            "shortlisted": item.get("shortlisted") is True, "estimate_usd": _number(item.get("estimate_usd")),
            "evidence": {"groups": _number(evidence.get("groups"), 0), "passed_groups": _number(evidence.get("passed_groups"), 0),
                         "failed_groups": _number(evidence.get("failed_groups"), 0), "lower_bound": _number(evidence.get("lower_bound")),
                         "qualified": evidence.get("qualified") is True},
        })
    signals = {}
    if isinstance(raw.get("signals"), dict):
        for key, answer in raw["signals"].items():
            if isinstance(key, str) and len(key) <= 128:
                clean = _question_answer(answer)
                if clean is not None:
                    signals[key] = clean
    router = raw.get("router") if isinstance(raw.get("router"), dict) else {}
    return {
        "id": _label(raw.get("id")), "created_at": _label(raw.get("created_at")), "task_id": _label(raw.get("task_id")),
        "scope_id": _label(raw.get("scope_id")), "group_id": _label(raw.get("group_id")), "synthetic": raw.get("synthetic") is True,
        "mode": raw.get("mode") if raw.get("mode") in ("off", "shadow", "active") else "off",
        "status": raw.get("status") if raw.get("status") in ("ok", "unavailable", "abstained", "skipped") else "skipped",
        "action": raw.get("action") if raw.get("action") in ("route", "experiment", "coordinator", "clarify", "repackage") else "coordinator",
        "selected_configuration_id": raw.get("selected_configuration_id") if isinstance(raw.get("selected_configuration_id"), str) else None,
        "baseline_configuration_id": raw.get("baseline_configuration_id") if isinstance(raw.get("baseline_configuration_id"), str) else None,
        "recommended_action": _label(raw.get("recommended_action")),
        "recommended_configuration_id": raw.get("recommended_configuration_id") if isinstance(raw.get("recommended_configuration_id"), str) else None,
        "nominated_configuration_ids": _labels(raw.get("nominated_configuration_ids")), "reason_codes": _labels(raw.get("reason_codes")),
        "question_version": _label(raw.get("question_version")), "model": _label(raw.get("model")),
        "policy_hash": _label(raw.get("policy_hash")), "input_hash": _label(raw.get("input_hash")), "question_hash": _label(raw.get("question_hash")),
        "payload_hash": _label(raw.get("payload_hash")), "evidence_hash": _label(raw.get("evidence_hash")),
        "configuration_metadata": {k: {field: v[field] for field in
            ("provider", "model_revision", "host", "adapter", "effort", "prompt_contract", "tool_policy", "prompt_version") if _metadata_label(v.get(field))}
            for k, v in (raw.get("configuration_metadata") or {}).items() if k in {c["configuration_id"] for c in candidates} and _metadata_label(k) and isinstance(v, dict)},
        "candidates": candidates, "signals": signals,
        "router": {"attempts": _number(router.get("attempts"), 0), "latency_ms": _number(router.get("latency_ms"), 0),
                   "cost_usd": _number(router.get("cost_usd")), "cost_kind": router.get("cost_kind") if router.get("cost_kind") in ("measured", "estimated", "unknown") else "unknown",
                   "input_tokens": _number(router.get("input_tokens")), "output_tokens": _number(router.get("output_tokens"))},
    }


def _project_outcome(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or raw.get("schema") != OUTCOME_SCHEMA:
        return None
    gates = []
    for gate in raw.get("gates", []) if isinstance(raw.get("gates"), list) else []:
        if isinstance(gate, dict): gates.append({"id": _label(gate.get("id")), "mandatory": gate.get("mandatory") is True, "passed": gate.get("passed") is True})
    scores = raw.get("scores") if isinstance(raw.get("scores"), dict) else {}
    costs = raw.get("costs") if isinstance(raw.get("costs"), dict) else {}
    security = raw.get("security") if isinstance(raw.get("security"), dict) else {}
    return {
        "id": _label(raw.get("id")), "decision_id": _label(raw.get("decision_id")), "task_id": _label(raw.get("task_id")),
        "group_id": _label(raw.get("group_id")), "scope_id": _label(raw.get("scope_id")), "configuration_id": _label(raw.get("configuration_id")),
        "created_at": _label(raw.get("created_at")), "synthetic": raw.get("synthetic") is True, "artifact_hash": _label(raw.get("artifact_hash")),
        "reviewer_kind": raw.get("reviewer_kind") if raw.get("reviewer_kind") in ("human", "frontier", "synthetic") else "synthetic",
        "reviewer_id": _label(raw.get("reviewer_id")), "accepted": raw.get("accepted") is True, "gates": gates,
        "scores": {key: _number(scores.get(key)) for key in ("coverage", "correctness", "maintainability", "clarity")},
        "costs": {key: _cost(costs.get(key)) for key in ("preparation", "worker", "review", "retry", "fallback")},
        "latency_ms": _number(raw.get("latency_ms")),
        "security": {"mode": security.get("mode") if security.get("mode") in ("off", "advisory") else "off",
                     "status": security.get("status") if security.get("status") in ("not_checked", "pass", "fail", "indeterminate", "unavailable") else "not_checked",
                     "reason_codes": _labels(security.get("reason_codes")), "latency_ms": _number(security.get("latency_ms"), 0),
                     "cost_usd": _number(security.get("cost_usd")), "cost_kind": security.get("cost_kind") if security.get("cost_kind") in ("measured", "estimated", "unknown") else "unknown",
                     "attempts": _number(security.get("attempts"), 0),
                     "model": _label(security.get("model")), "question_version": _label(security.get("question_version")),
                     "input_hash": _label(security.get("input_hash")), "question_hash": _label(security.get("question_hash"))},
    }


def _total_cost(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {"usd": None, "coverage": "0/0", "complete": False, "kind": "unknown"}
    amounts = [x["usd"] for x in items]
    known = [x for x in amounts if x is not None]
    kinds = {x.get("kind", "unknown") for x in items}
    kind = next(iter(kinds)) if len(kinds) == 1 else "mixed"
    if len(known) != len(amounts): return {"usd": sum(known) if known else None, "coverage": f"{len(known)}/{len(amounts)}", "complete": False, "kind": kind}
    return {"usd": sum(known), "coverage": f"{len(known)}/{len(amounts)}", "complete": True, "kind": kind}


def build_report(decisions: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a pure data report from the two append-only ledgers."""
    ds = [x for x in (_project_decision(d) for d in decisions if isinstance(d, dict)) if x]
    os = [x for x in (_project_outcome(o) for o in outcomes if isinstance(o, dict)) if x]
    outcomes_by_decision: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for outcome in os: outcomes_by_decision[outcome["decision_id"]].append(outcome)
    selected_by_decision = {d["id"]: d["selected_configuration_id"] for d in ds}
    selected_outcomes = [o for o in os if selected_by_decision.get(o["decision_id"]) == o["configuration_id"]]
    selected_by_id = {o["decision_id"]: o for o in selected_outcomes}
    routed = [d for d in ds if d["action"] == "route"]
    pending_selected = [d for d in routed if not d["selected_configuration_id"] or d["id"] not in selected_by_id]
    pending_experiments = [d for d in ds if d["action"] == "experiment" and not outcomes_by_decision[d["id"]]]
    all_costs, experiment_costs = [], []
    for outcome in os:
        costs = [outcome["costs"][key] for key in ("preparation", "worker", "review", "retry", "fallback")]
        costs.append({"usd": outcome["security"]["cost_usd"], "kind": outcome["security"]["cost_kind"]})
        all_costs.extend(costs)
        if outcome["decision_id"] in {d["id"] for d in ds if d["action"] == "experiment"}: experiment_costs.extend(costs)
    router_costs = [{"usd": d["router"]["cost_usd"], "kind": d["router"]["cost_kind"]} for d in ds]
    all_costs.extend(router_costs)
    # Include experiments and comparator spend in the workload denominator.
    # A trial outcome does not establish that the coordinator's task is done.
    workload_costs = list(all_costs)
    unresolved_tasks = len(pending_selected) + sum(d["action"] != "route" for d in ds)
    workload_costs.extend({"usd": None, "kind": "unknown"} for _ in range(unresolved_tasks))
    accepted = sum(o["accepted"] for o in selected_outcomes)
    mandatory = [g for o in os for g in o["gates"] if g["mandatory"]]
    workload_total = _total_cost(workload_costs)
    if not workload_total["complete"]:
        # A partial total is useful for diagnostics, but is not the cost of the
        # whole workload while an effective execution/fallback is unobserved.
        workload_total["known_usd"] = workload_total["usd"]
        workload_total["usd"] = None
    inferred = [d for d in ds if d["status"] in {"ok", "abstained"} and d["router"]["attempts"] > 0]
    suggestions = [d for d in inferred if d["recommended_action"] == "route" and d["recommended_configuration_id"]]
    pairs = Counter()
    reviewed_recommendations = []
    for d in suggestions:
        by_configuration = {o["configuration_id"]: o for o in outcomes_by_decision[d["id"]]}
        recommended = by_configuration.get(d["recommended_configuration_id"])
        baseline = by_configuration.get(d["baseline_configuration_id"])
        if recommended is not None:
            reviewed_recommendations.append(recommended)
        if recommended is not None and baseline is not None and d["recommended_configuration_id"] != d["baseline_configuration_id"]:
            key = ("both_accepted" if recommended["accepted"] and baseline["accepted"] else
                   "recommendation_only_accepted" if recommended["accepted"] else
                   "baseline_only_accepted" if baseline["accepted"] else "neither_accepted")
            pairs[key] += 1
    routing = {"inference_decisions": len(inferred), "route_recommendations": len(suggestions),
               "abstentions": sum(d["status"] == "abstained" for d in inferred),
               "experiment_proposals": sum(d["recommended_action"] == "experiment" for d in inferred),
               "recommended_outcomes_observed": len(reviewed_recommendations),
               "recommended_outcomes_accepted": sum(o["accepted"] for o in reviewed_recommendations),
               "recommended_outcomes_pending": len(suggestions)-len(reviewed_recommendations),
               "baseline_disagreements": sum(d["recommended_configuration_id"] != d["baseline_configuration_id"] for d in suggestions if d["baseline_configuration_id"]),
               "paired_comparisons": dict(pairs), "paired_comparisons_total": sum(pairs.values())}
    return {
        "schema": "ultra-pilot-report-v1",
        "summary": {"routing": routing, "decisions": len(ds), "outcomes": len(os), "pending_decisions": sum(not outcomes_by_decision[d["id"]] for d in ds),
                    "pending_selected_outcomes": len(pending_selected), "pending_experiments": len(pending_experiments),
                    "synthetic_decisions": sum(d["synthetic"] for d in ds), "accepted_outcomes": accepted,
                    "acceptance": {"passed": accepted, "total": len(selected_outcomes)}, "mandatory_gates": {"passed": sum(g["passed"] for g in mandatory), "total": len(mandatory)},
                    "cost": _total_cost(all_costs), "whole_workload_cost": workload_total, "experiment_cost": _total_cost(experiment_costs),
                    "cost_note": "Known logged spend may mix measured and estimated values. Complete workload cost stays unknown while a selected route, fallback, or final coordinator outcome is unobserved; no savings are claimed."},
        "decisions": ds, "outcomes": os,
    }


def _e(value: Any) -> str: return html.escape(str(_value(value, "-")), quote=True)
def _money(cost: dict[str, Any]) -> str: return "unknown" if cost["usd"] is None else f"${cost['usd']:.4f} ({cost.get('kind', 'unknown')})"
def _pill(value: str) -> str: return f'<span class="pill">{_e(value)}</span>'


def render_html(report: dict[str, Any]) -> str:
    """Render an offline responsive report. All text is escaped before insertion."""
    summary, decisions, outcomes = report.get("summary", {}), report.get("decisions", []), report.get("outcomes", [])
    outcome_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for outcome in outcomes: outcome_map[outcome["decision_id"]].append(outcome)
    routing = summary.get("routing", {})
    feedback = (f"<p class=note>Jev route recommendations: {_e(routing.get('route_recommendations', 0))}; "
                f"independently accepted: {_e(routing.get('recommended_outcomes_accepted', 0))}/"
                f"{_e(routing.get('recommended_outcomes_observed', 0))} observed; "
                f"pending: {_e(routing.get('recommended_outcomes_pending', 0))}. "
                f"Baseline disagreements: {_e(routing.get('baseline_disagreements', 0))}; "
                f"actual paired comparisons: {_e(routing.get('paired_comparisons_total', 0))}. "
                f"Pair outcomes: {_e(routing.get('paired_comparisons', {}))}. "
                "These are descriptive counts, not calibrated success probabilities.</p>")
    cards = []
    for d in decisions:
        rows = outcome_map[d["id"]]
        selected_pending = d["action"] == "route" and d["selected_configuration_id"] and not any(o["configuration_id"] == d["selected_configuration_id"] for o in rows)
        experiment_pending = d["action"] == "experiment" and not rows
        choices = f"selected {_e(d['selected_configuration_id'])} · baseline {_e(d['baseline_configuration_id'])} · recommended {_e(d['recommended_configuration_id'])}"
        candidate_rows = "".join(f"<tr><td>{_e(c['configuration_id'])}</td><td>{_e(c['model'])} / {_e(c['effort'])}</td><td>{'eligible' if c['eligible'] else 'ineligible'}</td><td>{c['evidence']['passed_groups']}/{c['evidence']['groups']} groups; lower bound {_e(c['evidence']['lower_bound'])}; {'qualified' if c['evidence']['qualified'] else 'pending qualification'}</td></tr>" for c in d["candidates"])
        outcome_rows = "".join(f"<tr><td>{_e(o['configuration_id'])}</td><td>{'accepted' if o['accepted'] else 'not accepted'}</td><td>{_e(o['scores'])}</td><td>prep {_money(o['costs']['preparation'])}; worker {_money(o['costs']['worker'])}; review {_money(o['costs']['review'])}; retry {_money(o['costs']['retry'])}; fallback {_money(o['costs']['fallback'])}</td><td>{'advisory ' + _e(o['security']['status']) + '; ' + _money({'usd': o['security']['cost_usd'], 'kind': o['security']['cost_kind']}) if o['security']['mode'] == 'advisory' else 'off'}</td></tr>" for o in rows) or "<tr><td colspan=5>Pending - no outcome recorded.</td></tr>"
        signals = " ".join(f"{_pill(k + ': ' + json.dumps(v, separators=(',', ':')))}" for k, v in d["signals"].items()) or "No validated question probabilities recorded."
        synthetic = '<p class="warning">Synthetic telemetry - pending qualification; it does not establish live routing evidence.</p>' if d["synthetic"] else ""
        pending = '<p class="warning">Selected worker outcome pending - comparator outcomes do not establish selected-worker acceptance.</p>' if selected_pending else ('<p class="warning">Experiment pending - no routine acceptance conclusion is available.</p>' if experiment_pending else '')
        cards.append(f'''<article class="decision" data-scope="{_e(d['scope_id'])}" data-action="{_e(d['action'])}"><header><div><h2>{_e(d['task_id'])}</h2><p>{_pill(d['mode'])} {_pill(d['status'])} {_pill(d['action'])} <span>{_e(d['created_at'])}</span></p></div></header>{synthetic}{pending}<p><b>Routing choice:</b> {choices}</p><p><b>Decision trace:</b> {_e(', '.join(d['reason_codes']) or 'No reason codes')} · model {_e(d['model'])} · {d['router']['attempts']} attempt(s), {_e(d['router']['latency_ms'])} ms, {_money({'usd': d['router']['cost_usd'], 'kind': d['router']['cost_kind']})}</p><p><b>Question probabilities:</b> {signals}</p><h3>Candidate evidence</h3><table><thead><tr><th>Configuration</th><th>Worker</th><th>Eligibility</th><th>Evidence confidence</th></tr></thead><tbody>{candidate_rows or '<tr><td colspan=4>No candidates recorded.</td></tr>'}</tbody></table><h3>Observed outcomes</h3><table><thead><tr><th>Configuration</th><th>Acceptance</th><th>Quality</th><th>Cost breakdown</th><th>Security</th></tr></thead><tbody>{outcome_rows}</tbody></table></article>''')
    scopes = sorted({_label(d.get("scope_id")) for d in decisions})
    actions = sorted({_label(d.get("action")) for d in decisions})
    safe_json = (json.dumps(report, ensure_ascii=False, separators=(",", ":"))
                 .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
                 .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Jev pilot telemetry</title><style>:root{{color-scheme:light dark;--bg:#f6f7fb;--card:#fff;--ink:#172033;--muted:#62708a;--line:#dbe1eb;--accent:#5b4bdb;--warn:#9b5c00}}@media(prefers-color-scheme:dark){{:root{{--bg:#121521;--card:#1b2030;--ink:#edf1f8;--muted:#aeb8cb;--line:#31394c;--accent:#a99cff;--warn:#ffca70}}}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 ui-sans-serif,system-ui,sans-serif}}main{{max-width:1200px;margin:auto;padding:32px 20px 72px}}h1{{margin:0;font-size:clamp(1.7rem,4vw,2.6rem)}}h2{{margin:0;font-size:1.12rem}}h3{{font-size:.9rem;margin:24px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}}.lede,.note{{color:var(--muted)}}.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:24px 0}}.metric,.decision{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}}.metric b{{display:block;font-size:1.5rem}}.filters{{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}}select{{padding:8px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink)}}.decision{{margin:16px 0;overflow:auto}}.decision header{{display:flex;justify-content:space-between;gap:12px}}.decision p{{margin:9px 0}}.pill{{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:1px 7px;font-size:.78em;color:var(--muted)}}.warning{{color:var(--warn);font-weight:650}}table{{width:100%;border-collapse:collapse;min-width:620px}}th,td{{text-align:left;vertical-align:top;padding:8px;border-top:1px solid var(--line)}}th{{color:var(--muted);font-size:.82em}}.hidden{{display:none}}</style></head><body><main><h1>Jev pilot telemetry</h1><p class="lede">Routing choices and observed worker outcomes. Comparator results are shown only when outcomes share a decision; the report makes no realized-savings claim.</p><section class="metrics"><div class="metric"><b>{_e(summary.get('decisions', 0))}</b>decisions</div><div class="metric"><b>{_e(summary.get('pending_selected_outcomes', 0))}</b>selected outcomes pending</div><div class="metric"><b>{_e(summary.get('pending_experiments', 0))}</b>experiments pending</div><div class="metric"><b>{_e(summary.get('accepted_outcomes', 0))}/{_e(summary.get('acceptance', {}).get('total', 0))}</b>selected-worker acceptance</div><div class="metric"><b>{_e(summary.get('mandatory_gates', {}).get('passed', 0))}/{_e(summary.get('mandatory_gates', {}).get('total', 0))}</b>mandatory gates passed</div><div class="metric"><b>{_money(summary.get('cost', {'usd': None}))}</b>known logged spend · coverage {_e(summary.get('cost', {}).get('coverage', '0/0'))}</div><div class="metric"><b>{_money(summary.get('whole_workload_cost', {'usd': None}))}</b>complete workload cost · coverage {_e(summary.get('whole_workload_cost', {}).get('coverage', '0/0'))}</div><div class="metric"><b>{_money(summary.get('experiment_cost', {'usd': None}))}</b>experiment spend</div></section><p class="note">{_e(summary.get('cost_note', ''))} Security results are advisory and never change acceptance.</p>{feedback}<div class="filters"><label>Scope <select id="scope"><option value="">All scopes</option>{''.join(f'<option>{_e(x)}</option>' for x in scopes)}</select></label><label>Action <select id="action"><option value="">All actions</option>{''.join(f'<option>{_e(x)}</option>' for x in actions)}</select></label></div><section id="decisions">{''.join(cards) or '<article class="decision">No allowlisted pilot telemetry is available yet.</article>'}</section></main><script type="application/json" id="pilot-data">{safe_json}</script><script>const s=document.querySelector('#scope'),a=document.querySelector('#action');function f(){{document.querySelectorAll('.decision').forEach(x=>x.classList.toggle('hidden',(s.value&&x.dataset.scope!==s.value)||(a.value&&x.dataset.action!==a.value)))}}s.onchange=a.onchange=f;</script></body></html>'''
