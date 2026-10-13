"""Bounded deterministic agent coordination; no external actions or LLM scheduling."""
from collections import defaultdict
from datetime import date, timedelta
from .activity_manager import ActivityManager
from .dependency_planner import DependencyPlanner
from .resource_agents import LabourAllocationAgent, EquipmentAllocationAgent, MaterialRequirementAgent, baseline_conflicts
from .cost_agent import CostBudgetAgent
from .risk_agent import DelayRiskAgent


class AgenticCoordinator:
    HORIZON = 2000

    def plan(self, payload):
        p = ActivityManager().validate(payload)
        baseline = DependencyPlanner().analyze(p)
        resources = {r["id"]: r for r in p["resources"]}
        tasks = {t["id"]: t for t in p["tasks"]}
        labour, equipment, materials = LabourAllocationAgent(), EquipmentAllocationAgent(), MaterialRequirementAgent()
        usage, consumed = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(float))
        pending, scheduled, blocked = set(tasks), {}, {}
        trace = [{"agent": "Activity manager", "action": "Validate inputs", "detail": f"{len(tasks)} activities and {len(resources)} resource definitions passed validation."},
                 {"agent": "Dependency planner", "action": "Calculate CPM", "detail": f"Dependency baseline: {baseline['duration']} days; {len(baseline['critical_ids'])} zero-float activities."}]

        def rank(tid):
            t, b = tasks[tid], baseline["tasks"][tid]
            if p["strategy"] == "priority":
                return (-t["priority"], b["slack"], b["start"], tid)
            if p["strategy"] == "shortest":
                return (t["duration"], -t["priority"], b["slack"], tid)
            return (b["slack"], -t["priority"], b["start"], tid)

        while pending:
            ready = [tid for tid in pending if all(d in scheduled or d in blocked for d in tasks[tid]["dependencies"])]
            tid = min(ready, key=rank)
            pending.remove(tid)
            t = tasks[tid]
            bad_deps = [d for d in t["dependencies"] if d in blocked]
            if bad_deps:
                blocked[tid] = "Blocked predecessor: " + ", ".join(bad_deps)
                continue
            impossible = []
            for rid, qty in t["requirements"].items():
                r = resources[rid]
                if r["kind"] != "material" and qty > r["capacity"]:
                    impossible.append(f"{r['name']}: requires {qty:g}, capacity is {r['capacity']:g}")
                if r["kind"] == "material" and qty > r["stock"] + sum(d["quantity"] for d in r["deliveries"]):
                    impossible.append(f"{r['name']}: demand exceeds all entered supplies")
            if impossible:
                blocked[tid] = "; ".join(impossible)
                continue
            earliest = max([t["release_day"]] + [scheduled[d]["finish"] for d in t["dependencies"]])
            first_reasons = []
            for start in range(earliest, self.HORIZON - t["duration"] + 1):
                reasons = labour.check(t, start, resources, usage) + equipment.check(t, start, resources, usage) + materials.check(t, start, resources, consumed)
                if reasons:
                    if not first_reasons:
                        first_reasons = reasons
                    continue
                finish = start + t["duration"]
                scheduled[tid] = {"start": start, "finish": finish, "resource_delay": start - earliest,
                                  "reason": "; ".join(first_reasons) if first_reasons else "Dependencies and resource checks satisfied."}
                for rid, qty in t["requirements"].items():
                    if resources[rid]["kind"] == "material":
                        consumed[rid][start] += qty
                    else:
                        for day in range(start, finish):
                            usage[rid][day] += qty
                break
            if tid not in scheduled:
                blocked[tid] = "No feasible slot within 2000 days. " + "; ".join(first_reasons)
        duration = max((s["finish"] for s in scheduled.values()), default=0)
        origin = date.fromisoformat(p["start_date"])
        rows = []
        for t in p["tasks"]:
            tid = t["id"]
            b, s = baseline["tasks"][tid], scheduled.get(tid)
            rows.append({**t, "baseline_start": b["start"], "baseline_finish": b["finish"], "slack": b["slack"],
                         "critical": b["critical"], "status": "scheduled" if s else "blocked",
                         "start": s["start"] if s else None, "finish": s["finish"] if s else None,
                         "start_date": (origin + timedelta(days=s["start"])).isoformat() if s else None,
                         "finish_date": (origin + timedelta(days=s["finish"] - 1)).isoformat() if s else None,
                         "resource_delay": s["resource_delay"] if s else 0,
                         "shift": s["start"] - b["start"] if s else None,
                         "reason": s["reason"] if s else blocked[tid]})
        conflicts = baseline_conflicts(p, baseline)
        material_report = materials.report(p, consumed)
        cost = CostBudgetAgent().analyze(p, duration, baseline["duration"], scheduled)
        risk = DelayRiskAgent().analyze(p, rows, duration, cost, material_report)
        resource_report = []
        for r in p["resources"]:
            if r["kind"] == "material":
                continue
            daily = [usage[r["id"]].get(d, 0) for d in range(duration)]
            capacity_days = sum(0 if d in r["unavailable_days"] else r["capacity"] for d in range(duration))
            resource_report.append({"id": r["id"], "name": r["name"], "kind": r["kind"], "capacity": r["capacity"],
                                    "daily": daily, "unavailable_days": r["unavailable_days"], "peak": max(daily, default=0),
                                    "utilization": round(100 * sum(daily) / capacity_days, 1) if capacity_days else 0})
        for agent, detail in [("Labour allocation", "Daily worker capacities checked for every occupied activity day."),
                              ("Equipment allocation", "Shared equipment units and unavailable days checked."),
                              ("Material requirements", "Cumulative stock and deliveries checked at consumption events."),
                              ("Cost and budget", f"Resource quantities, durations, rates, fixed costs and overhead evaluated."),
                              ("Delay and risk", f"Rule-based risk level: {risk['level']}. Not a probability."),
                              ("Coordinator", f"Bounded plan complete: {len(scheduled)} scheduled, {len(blocked)} blocked. Human review required.")]:
            trace.append({"agent": agent, "action": "Evaluate plan", "detail": detail})
        return {"project": p, "tasks": rows, "baseline": baseline, "conflicts": conflicts,
                "resources": resource_report, "materials": material_report, "cost": cost, "risk": risk, "trace": trace,
                "summary": {"feasible": not blocked, "scheduled": len(scheduled), "blocked": len(blocked),
                            "duration": duration, "baseline_duration": baseline["duration"],
                            "extension": max(0, duration - baseline["duration"]),
                            "finish_date": (origin + timedelta(days=duration - 1)).isoformat() if duration else None,
                            "baseline_conflict_days": sum(len(c["days"]) for c in conflicts)}}
