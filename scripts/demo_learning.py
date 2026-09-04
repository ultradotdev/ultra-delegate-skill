#!/usr/bin/env python3
"""Reproducible simulated learning lifecycle; no model calls or global writes.

Run: python3 scripts/demo_learning.py [--output-dir DIRECTORY]
All quality scores and acceptance results are synthetic fixtures. They demonstrate
bookkeeping behavior only and establish no model quality, savings, or performance.
Each invocation creates a unique directory and retains its demonstration artifacts.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import tempfile

REPOSITORY = Path(__file__).resolve().parents[1]
HELPER = REPOSITORY / ".agents/skills/ultra-delegation/scripts/ultra_delegation.py"
SPEC = importlib.util.spec_from_file_location("demo_helper", HELPER)
ud = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ud)
DISCLAIMER = ("SIMULATION: all scores, gates and outcomes are synthetic fixtures. "
              "No models were invoked; cost, savings and runtime performance are unavailable. "
              "These artifacts are not model recommendations or live qualification evidence.")


def run(output_dir=None):
    if output_dir:
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="ultra-delegation-simulation-", dir=output_dir))
    profile = {
        "task_family": "python-edit", "provider": "openai", "model": "demo-model",
        "model_revision": "demo-model", "host": "codex", "execution_location": "remote",
        "thinking": {"normalized": "medium", "native": "medium"},
        "prompt_profile": "simulation-v1", "tool_policy": "simulation-v1",
    }
    task = {"task_family": "python-edit", "operation": "refactor", "language": "python",
            "framework": "stdlib", "framework_major": "3", "risk": "low", "coupling": "low",
            "validation": "unittest", "tools": "shell"}
    context = {"host": "codex", "provider": "openai", "available_models": ["demo-model"],
               "thinking_settings": {"demo-model": ["medium"]}}
    roots = {name: output / name / ".ultra-delegation" for name in ("source", "verified", "quarantined")}
    for root in roots.values():
        ud.write_json(ud.policy_path(root), {"global_catalog": False, "local_execution": {"mode": "disabled"}})

    def outcome(run_id, passed=True):
        return {"run_id": run_id, "profile": profile, "task_signature": task,
                "accepted": passed, "gates": [{"name": "synthetic-check", "mandatory": True, "passed": passed}],
                "metrics": {"quality_score": 90 if passed else 20}, "cost_kind": "unavailable"}

    def rank(root):
        return ud.cmd_rank(argparse.Namespace(root=str(root), context=json.dumps(context),
                           task=json.dumps(task), candidates=json.dumps([profile]), records=None))["ranked"][0]

    for number in range(3):
        ud.cmd_record(argparse.Namespace(root=str(roots["source"]), record=json.dumps(outcome(f"simulated-source-{number + 1}"))))
    source_rank = rank(roots["source"])
    bundle = output / "simulated-ultra-delegation-learning-v1.json"
    ud.cmd_export(argparse.Namespace(root=str(roots["source"]), records=None, output=str(bundle)))
    ud.write_json(bundle, {**ud.read_json(bundle), "simulation": True, "disclaimer": DISCLAIMER})
    imports = {}
    for name in ("verified", "quarantined"):
        imports[name] = ud.cmd_import(argparse.Namespace(root=str(roots[name]), input=str(bundle),
                            task=json.dumps(task), context=json.dumps(context), apply=True))
        imported_path = ud.evidence_path(roots[name])
        imported_records = ud.read_jsonl(imported_path)
        for record in imported_records:
            record["run_id"] = f"simulated-import-{name}"
        ud.write_text(imported_path, "".join(json.dumps(record) + "\n" for record in imported_records))
    pending_rank = rank(roots["verified"])
    pid = ud.profile_id(profile)
    verified = ud.cmd_verify_import(argparse.Namespace(root=str(roots["verified"]), profile_id=pid,
                            result=json.dumps(outcome("simulated-local-confirmation")),
                            validation_strength="strong", comparison_run_id=None))
    verified_rank = rank(roots["verified"])
    failed = ud.cmd_verify_import(argparse.Namespace(root=str(roots["quarantined"]), profile_id=pid,
                            result=json.dumps(outcome("simulated-local-failure", False)),
                            validation_strength="strong", comparison_run_id=None))
    failed_rank = rank(roots["quarantined"])
    checks = {"normal_promotion": source_rank["tier"] == 3,
              "import_pending": pending_rank["status"] == "imported-prior-pending-verification",
              "local_confirmation": verified["status"] == verified_rank["status"] == "locally-verified",
              "failure_quarantined": failed["status"] == "quarantined" and not failed_rank["eligible"],
              "failure_requests_bakeoff": failed["next_action"] == "trigger host-native bakeoff"}
    reports = []
    for root in roots.values():
        report = ud.cmd_report(argparse.Namespace(root=str(root), report_kind="project", run_id=None, records=None, write=True))
        # Prefix every generated Markdown report so a detached artifact stays clear.
        md_path = Path(report["paths"][1])
        ud.write_text(md_path, DISCLAIMER + "\n\n" + md_path.read_text())
        json_path = Path(report["paths"][0])
        ud.write_json(json_path, {"simulation": True, "disclaimer": DISCLAIMER, **report["data"]})
        reports.extend(report["paths"])
    result = {"simulation": True, "disclaimer": DISCLAIMER, "passed": all(checks.values()),
              "checks": checks, "model_invocations": 0, "cost": "unavailable", "savings": "unavailable",
              "output_dir": str(output), "bundle": str(bundle), "reports": reports,
              "source_route": source_rank, "pending_route": pending_rank,
              "verified_route": verified_rank, "quarantined_route": failed_rank}
    ud.write_json(output / "simulation-report.json", result)
    ud.write_text(output / "simulation-report.md", "# Ultra Delegation lifecycle simulation\n\n" + DISCLAIMER + "\n\n" +
                  "\n".join(f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    result = run(args.output_dir)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
